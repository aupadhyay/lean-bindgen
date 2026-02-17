"""
type_mapper.py — Map IR types to Lean FFI types

This module analyzes IR types and determines how they map to Lean's FFI.
It handles:
  - Primitive type mappings (int, float, void)
  - Type compatibility checking
  - Future: pointer semantics, structs, enums

"""

from dataclasses import dataclass
from typing import Optional, Dict

from .ir import (
    IRContext,
    TypeId,
    Type,
    IntType,
    FloatType,
    VoidType,
    PointerType,
    PointerKind,
    IntKind,
    FloatKind,
)


@dataclass
class LeanTypeInfo:
    """
    How an IR type maps to Lean.

    Fields
    ------
    lean_type       : The Lean type to use in @[extern] declarations
    c_ffi_type      : The C type to use in the glue layer (must match Lean's ABI)
    needs_conversion: Whether conversion code is needed in glue
    is_opaque       : Whether this is an opaque handle type
    """

    lean_type: str
    c_ffi_type: str
    needs_conversion: bool = False
    is_opaque: bool = False


class TypeMapper:
    """
    Maps IR types to Lean FFI equivalents.

    Maintains a cache of mappings and determines which types are supported.
    """

    def __init__(self, ctx: IRContext):
        self.ctx = ctx
        self._cache: Dict[TypeId, Optional[LeanTypeInfo]] = {}

    def map_type(self, type_id: TypeId) -> Optional[LeanTypeInfo]:
        """
        Map an IR type to its Lean equivalent.

        Parameters
        ----------
        type_id : The IR type to map

        Returns
        -------
        LeanTypeInfo if the type is supported, None otherwise

        Caches results for efficiency.
        """
        # Check cache first
        if type_id in self._cache:
            return self._cache[type_id]

        # Resolve to canonical type
        canonical_id = self.ctx.resolve_canonical_type(type_id)
        typ = self.ctx.get_type(canonical_id)

        if typ is None:
            self._cache[type_id] = None
            return None

        # Map based on type kind
        result = self._map_type_kind(typ)

        # Cache the result
        self._cache[type_id] = result
        return result

    def _map_type_kind(self, typ: Type) -> Optional[LeanTypeInfo]:
        """
        Map a specific type kind to Lean.

        This is where the actual mapping logic lives.
        """
        kind = typ.kind

        # Integer types
        if isinstance(kind, IntType):
            return self._map_int(kind)

        # Float types
        if isinstance(kind, FloatType):
            return self._map_float(kind)

        # Void type
        if isinstance(kind, VoidType):
            return self._map_void()

        # Pointer types
        if isinstance(kind, PointerType):
            return self._map_pointer(kind, typ)

        # Unknown type
        return None

    def _map_int(self, int_type: IntType) -> LeanTypeInfo:
        """
        Map integer types to Lean unsigned integers.

        Strategy:
          - Map by size, not signedness (Lean FFI uses UIntN)
          - CHAR/SHORT -> UInt8/UInt16
          - INT -> UInt32
          - LONG/LONGLONG -> UInt64
        """
        kind = int_type.kind

        if kind in (IntKind.CHAR, IntKind.SCHAR, IntKind.UCHAR):
            return LeanTypeInfo(lean_type="UInt8", c_ffi_type="uint8_t")

        if kind in (IntKind.SHORT, IntKind.USHORT):
            return LeanTypeInfo(lean_type="UInt16", c_ffi_type="uint16_t")

        if kind in (IntKind.INT, IntKind.UINT):
            return LeanTypeInfo(lean_type="UInt32", c_ffi_type="uint32_t")

        if kind in (IntKind.LONG, IntKind.ULONG, IntKind.LONGLONG, IntKind.ULONGLONG):
            return LeanTypeInfo(lean_type="UInt64", c_ffi_type="uint64_t")

        # Shouldn't reach here, but be safe
        return LeanTypeInfo(lean_type="UInt32", c_ffi_type="uint32_t")

    def _map_float(self, float_type: FloatType) -> LeanTypeInfo:
        """
        Map float types to Lean Float (which is always 64-bit).

        Both float and double map to Float with double in C FFI.
        """
        # Lean's Float is always 64-bit, so we widen float to double
        return LeanTypeInfo(
            lean_type="Float",
            c_ffi_type="double",
            needs_conversion=(float_type.kind == FloatKind.FLOAT),
        )

    def _map_void(self) -> LeanTypeInfo:
        """
        Map void type.

        Void is only valid as a return type and maps to Unit in Lean.
        """
        return LeanTypeInfo(lean_type="Unit", c_ffi_type="void")

    def _map_pointer(self, ptr_type: PointerType, typ: Type) -> Optional[LeanTypeInfo]:
        """Map pointer types based on their kind."""
        if ptr_type.kind == PointerKind.OPAQUE:
            pointee = self.ctx.get_type(ptr_type.pointee)
            if pointee is None:
                return None
            lean_name = self._to_lean_opaque_name(pointee.c_spelling)
            return LeanTypeInfo(
                lean_type=lean_name,
                c_ffi_type="lean_object*",
                needs_conversion=True,
                is_opaque=True,
            )

        if ptr_type.kind == PointerKind.STRING:
            return LeanTypeInfo(
                lean_type="String",
                c_ffi_type="lean_object*",
                needs_conversion=True,
            )

        return None

    @staticmethod
    def _to_lean_opaque_name(c_name: str) -> str:
        """Convert a C struct name to a Lean opaque type name.

        e.g. "my_handle" -> "MyHandleRef", "sqlite3" -> "Sqlite3Ref"
        """
        # Remove "struct " prefix if present
        name = c_name.removeprefix("struct ")
        # Split on underscores and capitalize each part
        parts = name.split("_")
        pascal = "".join(p.capitalize() for p in parts if p)
        return f"{pascal}Ref"
