"""
ir_builder.py — Build IR from parsed Clang AST

This module converts the Clang-specific parser output (CHeaderAST) into
the language-agnostic IR. It:
  - Maps Clang type kinds to IR type representations
  - Creates Type and Function nodes
  - Populates the IRContext
  - Caches type conversions for efficiency

"""

from typing import Optional, Dict

from .ir import (
    IRContext,
    BindgenConfig,
    TypeId,
    FunctionId,
    IntType,
    FloatType,
    VoidType,
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
      1. Process each function declaration
      2. Convert return types and parameters to IR types
      3. Cache type conversions to avoid duplicates
      4. Populate IRContext with all IR nodes
    """

    def __init__(self, config: BindgenConfig):
        self.ctx = IRContext(config)

        # Cache: Clang type string -> IR TypeId
        # Key format: "{type_kind}:{c_spelling}"
        self._clang_type_cache: Dict[str, TypeId] = {}

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
        # Convert each function
        for func_decl in ast.functions:
            func_id = self._convert_function(func_decl)
            # Note: functions that fail conversion return None and are skipped

        return self.ctx

    def _convert_function(self, func: CFuncDecl) -> Optional[FunctionId]:
        """
        Convert a parsed function declaration to IR.

        Returns None if the function uses unsupported types.
        """
        # Convert return type
        ret_type_id = self._convert_clang_type(func.return_type_kind, func.return_type)
        if ret_type_id is None:
            # Unsupported return type - skip this function
            return None

        # Convert parameters
        params = []
        for p in func.params:
            p_type_id = self._convert_clang_type(p.type_kind, p.c_type)
            if p_type_id is None:
                # Unsupported parameter type - skip this function
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

    def _convert_clang_type(self, type_kind: str, c_spelling: str) -> Optional[TypeId]:
        """
        Convert a Clang type to an IR type.

        Parameters
        ----------
        type_kind   : Clang canonical TypeKind name (e.g., "INT", "FLOAT")
        c_spelling  : Original C type spelling (e.g., "int", "uint32_t")

        Returns
        -------
        TypeId for the IR type, or None if unsupported

        Caches conversions to avoid duplicate types in the IR.
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

        # If we still don't have a type, it's unsupported
        if ir_kind is None:
            return None

        # Add to IR
        type_id = self.ctx.add_type(
            kind=ir_kind,
            c_spelling=c_spelling,
            canonical=None,  # No typedef resolution yet
            layout=None,  # Layout info not needed for primitives
        )

        # Cache it
        self._clang_type_cache[cache_key] = type_id

        return type_id
