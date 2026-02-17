"""
ir_builder.py — Build IR from parsed Clang AST

This module converts the Clang-specific parser output (CHeaderAST) into
the language-agnostic IR. It:
  - Maps Clang type kinds to IR type representations
  - Creates Type and Function nodes
  - Populates the IRContext
  - Caches type conversions for efficiency

"""

from typing import Optional, Dict, Set

from .ir import (
    IRContext,
    BindgenConfig,
    TypeId,
    FunctionId,
    IntType,
    FloatType,
    VoidType,
    PointerType,
    PointerKind,
    TypeKind,
    Function,
    Param,
    clang_kind_to_int_kind,
    clang_kind_to_float_kind,
    is_signed_int,
)
from .parser import CHeaderAST, CFuncDecl, CParam


class IRBuilder:
    """
    Converts parsed AST to IR.

    Strategy:
      1. Process typedefs to discover opaque struct names
      2. Process each function declaration
      3. Convert return types and parameters to IR types
      4. Cache type conversions to avoid duplicates
      5. Populate IRContext with all IR nodes
    """

    def __init__(self, config: BindgenConfig):
        self.ctx = IRContext(config)

        # Cache: Clang type string -> IR TypeId
        # Key format: "{type_kind}:{c_spelling}"
        self._clang_type_cache: Dict[str, TypeId] = {}

        # Set of struct names that have a typedef (opaque types)
        self._opaque_names: Set[str] = set()

        # Cache: opaque name -> TypeId for the opaque pointee type
        self._opaque_type_cache: Dict[str, TypeId] = {}

    def build(self, ast: CHeaderAST) -> IRContext:
        """
        Build complete IR from parsed AST.

        Parameters
        ----------
        ast : The parsed C header AST from parser.py

        Returns
        -------
        Populated IRContext ready for analysis
        """
        # Process typedefs first to register opaque names
        for td in ast.typedefs:
            if td.is_struct_typedef:
                self._opaque_names.add(td.name)

        # Convert each function
        for func_decl in ast.functions:
            self._convert_function(func_decl)

        return self.ctx

    def _convert_function(self, func: CFuncDecl) -> Optional[FunctionId]:
        """
        Convert a parsed function declaration to IR.

        Returns None if the function uses unsupported types.
        """
        # Convert return type
        ret_type_id = self._convert_clang_type(
            func.return_type_kind,
            func.return_type,
            pointee_spelling=func.ret_pointee_spelling,
            pointee_kind=func.ret_pointee_kind,
            is_const_pointee=func.ret_is_const_pointee,
        )
        if ret_type_id is None:
            return None

        # Convert parameters
        params = []
        for p in func.params:
            p_type_id = self._convert_clang_type(
                p.type_kind,
                p.c_type,
                pointee_spelling=p.pointee_spelling,
                pointee_kind=p.pointee_kind,
                is_const_pointee=p.is_const_pointee,
            )
            if p_type_id is None:
                return None
            params.append(Param(name=p.name, type_id=p_type_id))

        # Create IR function
        ir_func = Function(
            id=FunctionId(0),  # Will be set by add_function
            c_name=func.name,
            return_type=ret_type_id,
            params=params,
            is_variadic=False,
            source_location=func.source_file,
            comment=None,
        )

        return self.ctx.add_function(ir_func)

    def _convert_clang_type(
        self,
        type_kind: str,
        c_spelling: str,
        pointee_spelling: Optional[str] = None,
        pointee_kind: Optional[str] = None,
        is_const_pointee: bool = False,
    ) -> Optional[TypeId]:
        """
        Convert a Clang type to an IR type.

        Parameters
        ----------
        type_kind         : Clang canonical TypeKind name (e.g., "INT", "POINTER")
        c_spelling        : Original C type spelling (e.g., "int", "my_handle *")
        pointee_spelling  : Spelling of the pointee type (for pointers)
        pointee_kind      : TypeKind of the pointee (for pointers)
        is_const_pointee  : Whether the pointee is const-qualified

        Returns
        -------
        TypeId for the IR type, or None if unsupported
        """
        # Check cache first
        cache_key = f"{type_kind}:{c_spelling}"
        if cache_key in self._clang_type_cache:
            return self._clang_type_cache[cache_key]

        # Convert based on type kind
        ir_kind: Optional[TypeKind] = None

        # Try integer types
        int_kind = clang_kind_to_int_kind(type_kind)
        if int_kind is not None:
            ir_kind = IntType(kind=int_kind, is_signed=is_signed_int(int_kind))

        # Try float types
        if ir_kind is None:
            float_kind = clang_kind_to_float_kind(type_kind)
            if float_kind is not None:
                ir_kind = FloatType(kind=float_kind)

        # Try void
        if ir_kind is None and type_kind == "VOID":
            ir_kind = VoidType()

        # Try pointer types
        if ir_kind is None and type_kind == "POINTER":
            return self._convert_pointer_type(
                c_spelling, pointee_spelling, pointee_kind, is_const_pointee, cache_key
            )

        # If we still don't have a type, it's unsupported
        if ir_kind is None:
            return None

        # Add to IR
        type_id = self.ctx.add_type(
            kind=ir_kind,
            c_spelling=c_spelling,
            canonical=None,
            layout=None,
        )

        # Cache it
        self._clang_type_cache[cache_key] = type_id

        return type_id

    def _convert_pointer_type(
        self,
        c_spelling: str,
        pointee_spelling: Optional[str],
        pointee_kind: Optional[str],
        is_const_pointee: bool,
        cache_key: str,
    ) -> Optional[TypeId]:
        """Convert a pointer type to IR, classifying it by kind."""
        ptr_kind = self._classify_pointer(
            pointee_spelling, pointee_kind, is_const_pointee
        )
        if ptr_kind is None:
            return None

        # Get or create the pointee type in IR
        pointee_type_id = self._get_or_create_opaque_type(pointee_spelling or "void")

        ir_kind = PointerType(
            pointee=pointee_type_id,
            kind=ptr_kind,
            is_const=is_const_pointee,
        )

        type_id = self.ctx.add_type(
            kind=ir_kind,
            c_spelling=c_spelling,
        )

        self._clang_type_cache[cache_key] = type_id
        return type_id

    def _classify_pointer(
        self,
        pointee_spelling: Optional[str],
        pointee_kind: Optional[str],
        is_const_pointee: bool,
    ) -> Optional[PointerKind]:
        """
        Classify a pointer by its kind.

        Returns None for unsupported pointer types (void*, function pointers, etc.)
        """
        if pointee_kind is None:
            return None

        # const char* -> STRING
        if pointee_kind == "CHAR_S" and is_const_pointee:
            return PointerKind.STRING

        # Pointer to a known opaque struct -> OPAQUE
        if pointee_kind == "RECORD" and pointee_spelling:
            # Extract the struct name (remove "struct " prefix if present)
            name = pointee_spelling.removeprefix("struct ")
            if name in self._opaque_names:
                return PointerKind.OPAQUE

        # Unsupported pointer types (void*, non-const char*, unknown structs, etc.)
        return None

    def _get_or_create_opaque_type(self, name: str) -> TypeId:
        """Get or create a placeholder type for an opaque pointee."""
        if name in self._opaque_type_cache:
            return self._opaque_type_cache[name]

        type_id = self.ctx.add_type(
            kind=VoidType(),  # Placeholder — the pointee is opaque
            c_spelling=name,
        )
        self._opaque_type_cache[name] = type_id
        return type_id
