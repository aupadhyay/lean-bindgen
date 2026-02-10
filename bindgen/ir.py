"""
ir.py — Intermediate Representation for lean-bindgen

This module defines the IR layer that sits between parsing and code generation.
It provides a language-agnostic representation of C constructs that can be
analyzed and transformed before generating Lean bindings.

Architecture inspired by rust-bindgen's Item-based IR graph design.

The IR consists of:
  - Typed IDs for type-safe references between IR nodes
  - A rich type system with discriminated unions
  - Functions with typed parameters
  - IRContext that manages the entire IR graph
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import NewType, Optional, Dict, List, Union


# ---------------------------------------------------------------------------
# Typed IDs for type-safe references
# ---------------------------------------------------------------------------

TypeId = NewType("TypeId", int)
FunctionId = NewType("FunctionId", int)
ItemId = NewType("ItemId", int)


# ---------------------------------------------------------------------------
# Type system enums
# ---------------------------------------------------------------------------


class IntKind(Enum):
    """Integer type variants."""

    CHAR = auto()
    SCHAR = auto()
    UCHAR = auto()
    SHORT = auto()
    USHORT = auto()
    INT = auto()
    UINT = auto()
    LONG = auto()
    ULONG = auto()
    LONGLONG = auto()
    ULONGLONG = auto()


class FloatKind(Enum):
    """Floating point type variants."""

    FLOAT = auto()
    DOUBLE = auto()
    LONGDOUBLE = auto()


class PointerKind(Enum):
    """Semantic classification of pointer usage."""

    OPAQUE = auto()  # Opaque handle like sqlite3*
    STRING = auto()  # const char* string
    BUFFER = auto()  # void* + length buffer
    OUT_PARAM = auto()  # Output parameter like int*
    FUNCTION = auto()  # Function pointer (callback)
    TYPED = auto()  # Regular typed pointer


class ItemKind(Enum):
    """Discriminator for Item union."""

    TYPE = auto()
    FUNCTION = auto()
    CONSTANT = auto()
    GLOBAL_VAR = auto()


# ---------------------------------------------------------------------------
# Type system
# ---------------------------------------------------------------------------


@dataclass
class IntType:
    """Integer type with signedness."""

    kind: IntKind
    is_signed: bool


@dataclass
class FloatType:
    """Floating point type."""

    kind: FloatKind


@dataclass
class PointerType:
    """Pointer with semantic classification."""

    pointee: TypeId
    kind: PointerKind
    is_const: bool


@dataclass
class VoidType:
    """The void type (only valid as return type)."""

    pass


@dataclass
class TypeAlias:
    """A typedef pointing to another type."""

    alias_name: str
    aliased_type: TypeId


@dataclass
class Layout:
    """Memory layout information for a type."""

    size: int  # in bytes
    align: int  # in bytes


# TypeKind is a discriminated union of all type variants
TypeKind = Union[IntType, FloatType, PointerType, VoidType, TypeAlias]


@dataclass
class Type:
    """A type in the IR."""

    id: TypeId
    kind: TypeKind
    canonical: Optional[TypeId]  # For typedef resolution
    c_spelling: str  # Original C type spelling
    layout: Optional[Layout] = None


# ---------------------------------------------------------------------------
# Function representation
# ---------------------------------------------------------------------------


@dataclass
class Param:
    """A function parameter."""

    name: str
    type_id: TypeId


@dataclass
class Function:
    """A function in the IR."""

    id: FunctionId
    c_name: str
    return_type: TypeId
    params: List[Param]
    is_variadic: bool = False
    source_location: Optional[str] = None
    comment: Optional[str] = None


# ---------------------------------------------------------------------------
# Item graph
# ---------------------------------------------------------------------------


@dataclass
class Constant:
    """A constant value (e.g., from #define or enum)."""

    name: str
    value: Union[int, float, str]
    type_id: Optional[TypeId] = None


@dataclass
class GlobalVar:
    """A global variable."""

    name: str
    type_id: TypeId
    is_const: bool = False


# ItemData is a discriminated union based on ItemKind
ItemData = Union[Type, Function, Constant, GlobalVar]


@dataclass
class Item:
    """A node in the IR graph."""

    id: ItemId
    kind: ItemKind
    data: ItemData
    canonical_name: str
    comment: Optional[str] = None
    is_allowlisted: bool = True


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class BindgenConfig:
    """Configuration for bindgen IR construction."""

    module_name: str
    module_prefix: str
    header_name: str


# ---------------------------------------------------------------------------
# IR Context - the central graph manager
# ---------------------------------------------------------------------------


class IRContext:
    """
    Central context that holds the entire IR graph.

    Manages:
      - All types with typed lookup
      - All functions
      - All items
      - Configuration
    """

    def __init__(self, config: BindgenConfig):
        self.config = config

        # Storage
        self._types: Dict[TypeId, Type] = {}
        self._functions: Dict[FunctionId, Function] = {}
        self._items: Dict[ItemId, Item] = {}

        # ID generators
        self._next_type_id = 0
        self._next_function_id = 0
        self._next_item_id = 0

        # Tracking
        self._supported_functions: List[FunctionId] = []

    def add_type(
        self,
        kind: TypeKind,
        c_spelling: str,
        canonical: Optional[TypeId] = None,
        layout: Optional[Layout] = None,
    ) -> TypeId:
        """Add a type to the IR and return its ID."""
        type_id = TypeId(self._next_type_id)
        self._next_type_id += 1

        typ = Type(
            id=type_id,
            kind=kind,
            canonical=canonical,
            c_spelling=c_spelling,
            layout=layout,
        )
        self._types[type_id] = typ
        return type_id

    def add_function(self, func: Function) -> FunctionId:
        """Add a function to the IR and return its ID."""
        func_id = FunctionId(self._next_function_id)
        self._next_function_id += 1

        # Update the function's ID
        func.id = func_id
        self._functions[func_id] = func
        return func_id

    def add_item(
        self,
        kind: ItemKind,
        data: ItemData,
        canonical_name: str,
        comment: Optional[str] = None,
        is_allowlisted: bool = True,
    ) -> ItemId:
        """Add an item to the IR and return its ID."""
        item_id = ItemId(self._next_item_id)
        self._next_item_id += 1

        item = Item(
            id=item_id,
            kind=kind,
            data=data,
            canonical_name=canonical_name,
            comment=comment,
            is_allowlisted=is_allowlisted,
        )
        self._items[item_id] = item
        return item_id

    def get_type(self, type_id: TypeId) -> Optional[Type]:
        """Look up a type by ID."""
        return self._types.get(type_id)

    def get_function(self, func_id: FunctionId) -> Optional[Function]:
        """Look up a function by ID."""
        return self._functions.get(func_id)

    def get_item(self, item_id: ItemId) -> Optional[Item]:
        """Look up an item by ID."""
        return self._items.get(item_id)

    def resolve_canonical_type(self, type_id: TypeId) -> TypeId:
        """
        Follow typedef chains to get the canonical type ID.
        Returns the input ID if it's already canonical.
        """
        typ = self.get_type(type_id)
        if typ is None:
            return type_id

        if typ.canonical is not None:
            # Follow the chain recursively
            return self.resolve_canonical_type(typ.canonical)

        return type_id

    def all_types(self) -> List[Type]:
        """Get all types in the IR."""
        return list(self._types.values())

    def all_functions(self) -> List[Function]:
        """Get all functions in the IR."""
        return list(self._functions.values())

    def all_items(self) -> List[Item]:
        """Get all items in the IR."""
        return list(self._items.values())

    def mark_function_supported(self, func_id: FunctionId):
        """Mark a function as supported for code generation."""
        if func_id not in self._supported_functions:
            self._supported_functions.append(func_id)

    def get_supported_functions(self) -> List[FunctionId]:
        """Get list of function IDs that are supported."""
        return self._supported_functions


# ---------------------------------------------------------------------------
# Helper functions for type system
# ---------------------------------------------------------------------------


def clang_kind_to_int_kind(clang_kind: str) -> Optional[IntKind]:
    """Convert Clang TypeKind string to IntKind enum."""
    mapping = {
        "CHAR_S": IntKind.CHAR,
        "SCHAR": IntKind.SCHAR,
        "UCHAR": IntKind.UCHAR,
        "SHORT": IntKind.SHORT,
        "USHORT": IntKind.USHORT,
        "INT": IntKind.INT,
        "UINT": IntKind.UINT,
        "LONG": IntKind.LONG,
        "ULONG": IntKind.ULONG,
        "LONGLONG": IntKind.LONGLONG,
        "ULONGLONG": IntKind.ULONGLONG,
    }
    return mapping.get(clang_kind)


def clang_kind_to_float_kind(clang_kind: str) -> Optional[FloatKind]:
    """Convert Clang TypeKind string to FloatKind enum."""
    mapping = {
        "FLOAT": FloatKind.FLOAT,
        "DOUBLE": FloatKind.DOUBLE,
        "LONGDOUBLE": FloatKind.LONGDOUBLE,
    }
    return mapping.get(clang_kind)


def is_signed_int(kind: IntKind) -> bool:
    """Check if an integer kind is signed."""
    unsigned_kinds = {
        IntKind.UCHAR,
        IntKind.USHORT,
        IntKind.UINT,
        IntKind.ULONG,
        IntKind.ULONGLONG,
    }
    return kind not in unsigned_kinds
