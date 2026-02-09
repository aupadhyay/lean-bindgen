"""
mapper.py — Map C types to Lean 4 FFI types.

The mapping from C types to Lean types is the heart of the transpiler.
Keeping it in one place means we can extend it (add struct support, pointer
types, etc.) without touching the parser or code generator.

Each entry maps a *canonical* clang TypeKind to:
  - lean_type:  the Lean type to use in `@[extern]` declarations
  - c_ffi_type: the C type to use in the glue layer (must match Lean's ABI)

If a C type doesn't have a mapping, the transpiler will skip it and warn,
rather than generating broken code.
"""

from dataclasses import dataclass
from typing import Optional

from .parser import CParam, CFuncDecl


@dataclass
class LeanTypeMapping:
    """How a single C type maps to Lean + its C FFI counterpart."""

    lean_type: str  # e.g. "UInt32"
    c_ffi_type: str  # e.g. "uint32_t"


# ---------------------------------------------------------------------------
# The mapping table
# ---------------------------------------------------------------------------
# Keys are clang canonical TypeKind names (strings).
# We map by *kind* rather than spelling so "int", "int32_t", "signed int"
# all resolve to the same entry.

TYPE_MAP: dict[str, LeanTypeMapping] = {
    # --- integers ---
    "SCHAR": LeanTypeMapping("UInt8", "uint8_t"),
    "UCHAR": LeanTypeMapping("UInt8", "uint8_t"),
    "CHAR_S": LeanTypeMapping("UInt8", "uint8_t"),  # 'char' (signed on most platforms)
    "SHORT": LeanTypeMapping("UInt16", "uint16_t"),
    "USHORT": LeanTypeMapping("UInt16", "uint16_t"),
    "INT": LeanTypeMapping("UInt32", "uint32_t"),
    "UINT": LeanTypeMapping("UInt32", "uint32_t"),
    "LONG": LeanTypeMapping("UInt64", "uint64_t"),
    "ULONG": LeanTypeMapping("UInt64", "uint64_t"),
    "LONGLONG": LeanTypeMapping("UInt64", "uint64_t"),
    "ULONGLONG": LeanTypeMapping("UInt64", "uint64_t"),
    # --- floating point ---
    "FLOAT": LeanTypeMapping("Float", "double"),  # Lean Float is 64-bit; we widen
    "DOUBLE": LeanTypeMapping("Float", "double"),
    # --- void (only valid as return type) ---
    "VOID": LeanTypeMapping("Unit", "void"),
}


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def map_type(type_kind: str) -> Optional[LeanTypeMapping]:
    """
    Look up the Lean mapping for a clang TypeKind name.
    Returns None if the type isn't supported yet.
    """
    return TYPE_MAP.get(type_kind)


@dataclass
class MappedParam:
    """A function parameter after type mapping."""

    name: str
    c_type: str  # original C type spelling
    lean_type: str  # mapped Lean type
    c_ffi_type: str  # C type for the glue layer


@dataclass
class MappedFunc:
    """A fully mapped function ready for code generation."""

    c_name: str  # original C name, e.g. "add"
    lean_name: str  # Lean name, e.g. "add"
    extern_symbol: str  # symbol for @[extern], e.g. "lean_simple_math_add"
    return_lean_type: str  # e.g. "UInt32"
    return_c_ffi_type: str  # e.g. "uint32_t"
    return_c_type: str  # original C return type
    params: list[MappedParam]
    is_void: bool  # True if return type is void


def map_function(func: CFuncDecl, module_prefix: str) -> Optional[MappedFunc]:
    """
    Map a parsed C function to its Lean equivalent.

    Parameters
    ----------
    func           : the parsed C function declaration
    module_prefix  : prefix for the extern symbol, e.g. "simple_math"
                     The symbol becomes "lean_{prefix}_{name}"

    Returns None if any parameter or the return type can't be mapped.
    """
    # Map return type
    ret_mapping = map_type(func.return_type_kind)
    if ret_mapping is None:
        return None

    # Map each parameter
    mapped_params = []
    for p in func.params:
        p_mapping = map_type(p.type_kind)
        if p_mapping is None:
            return None
        mapped_params.append(
            MappedParam(
                name=p.name,
                c_type=p.c_type,
                lean_type=p_mapping.lean_type,
                c_ffi_type=p_mapping.c_ffi_type,
            )
        )

    is_void = func.return_type_kind == "VOID"

    return MappedFunc(
        c_name=func.name,
        lean_name=func.name,
        extern_symbol=f"lean_{module_prefix}_{func.name}",
        return_lean_type=ret_mapping.lean_type,
        return_c_ffi_type=ret_mapping.c_ffi_type,
        return_c_type=func.return_type,
        params=mapped_params,
        is_void=is_void,
    )
