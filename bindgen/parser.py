"""
parser.py — Extract function declarations from C headers using libclang.

WHY LIBCLANG:
We use libclang (the official Clang C API) rather than regex or a hand-rolled
parser because C headers are surprisingly complex — macros, typedefs, platform
ifdefs, etc.  Libclang gives us the same AST that a real C compiler sees,
so we never mis-parse a declaration.

The parser produces a list of `CFuncDecl` and `CTypedefDecl` dataclasses that
the rest of the pipeline consumes.  It can also dump the intermediate
representation as JSON for debugging.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from clang.cindex import (
    Index,
    CursorKind,
    TypeKind,
    TranslationUnit,
)


# ---------------------------------------------------------------------------
# Data classes — the structured representation of what we parsed
# ---------------------------------------------------------------------------


@dataclass
class CParam:
    """A single function parameter."""

    name: str
    c_type: str  # e.g. "int", "double", "const char *"
    type_kind: str  # clang TypeKind name, e.g. "INT", "DOUBLE", "POINTER"
    pointee_spelling: Optional[str] = None  # e.g. "my_handle" for my_handle*
    pointee_kind: Optional[str] = None  # e.g. "RECORD" for struct pointers
    is_const_pointee: bool = False


@dataclass
class CFuncDecl:
    """A C function declaration extracted from a header."""

    name: str  # e.g. "add"
    return_type: str  # e.g. "int"
    return_type_kind: str  # e.g. "INT"
    params: list[CParam] = field(default_factory=list)
    source_file: Optional[str] = None
    ret_pointee_spelling: Optional[str] = None
    ret_pointee_kind: Optional[str] = None
    ret_is_const_pointee: bool = False


@dataclass
class CTypedefDecl:
    """A typedef declaration extracted from a header."""

    name: str  # e.g. "my_handle"
    underlying_type: str  # e.g. "struct my_handle"
    underlying_kind: str  # e.g. "RECORD"
    is_struct_typedef: bool = False  # True for `typedef struct X X;`


@dataclass
class CHeaderAST:
    """The full parsed result for one header file."""

    header_path: str
    functions: list[CFuncDecl] = field(default_factory=list)
    typedefs: list[CTypedefDecl] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing logic
# ---------------------------------------------------------------------------


@dataclass
class _ResolvedType:
    """Internal result from _resolve_type."""

    spelling: str
    kind_name: str
    pointee_spelling: Optional[str] = None
    pointee_kind: Optional[str] = None
    is_const_pointee: bool = False


def _resolve_type(clang_type) -> _ResolvedType:
    """
    Get type info from a clang Type.
    Follows typedefs to canonical form and extracts pointee info for pointers.
    """
    canonical = clang_type.get_canonical()
    spelling = clang_type.spelling
    kind_name = canonical.kind.name

    pointee_spelling = None
    pointee_kind = None
    is_const_pointee = False

    if canonical.kind == TypeKind.POINTER:
        pointee = canonical.get_pointee()
        pointee_canonical = pointee.get_canonical()
        pointee_spelling = pointee_canonical.spelling
        pointee_kind = pointee_canonical.kind.name
        is_const_pointee = pointee.is_const_qualified()

    return _ResolvedType(
        spelling=spelling,
        kind_name=kind_name,
        pointee_spelling=pointee_spelling,
        pointee_kind=pointee_kind,
        is_const_pointee=is_const_pointee,
    )


def parse_header(
    header_path: str | Path, extra_args: list[str] | None = None
) -> CHeaderAST:
    """
    Parse a C header file and return its structured AST.

    Parameters
    ----------
    header_path : path to the .h file
    extra_args  : optional extra clang arguments, e.g. ["-I", "include/"]

    Returns
    -------
    CHeaderAST with all function declarations found in the header.
    """
    header_path = Path(header_path).resolve()
    if not header_path.exists():
        raise FileNotFoundError(f"Header not found: {header_path}")

    index = Index.create()
    args = extra_args or []
    tu = index.parse(
        str(header_path),
        args=args,
        options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
    )

    ast = CHeaderAST(header_path=str(header_path))

    for cursor in tu.cursor.get_children():
        # Only look at declarations that actually come from our header,
        # not from system includes.
        if cursor.location.file and cursor.location.file.name != str(header_path):
            continue

        if cursor.kind == CursorKind.TYPEDEF_DECL:
            underlying = cursor.underlying_typedef_type
            canonical = underlying.get_canonical()
            is_struct = canonical.kind == TypeKind.RECORD
            ast.typedefs.append(
                CTypedefDecl(
                    name=cursor.spelling,
                    underlying_type=underlying.spelling,
                    underlying_kind=canonical.kind.name,
                    is_struct_typedef=is_struct,
                )
            )

        elif cursor.kind == CursorKind.FUNCTION_DECL:
            ret = _resolve_type(cursor.result_type)

            params = []
            for i, arg in enumerate(cursor.get_arguments()):
                p = _resolve_type(arg.type)
                params.append(
                    CParam(
                        name=arg.spelling or f"arg{i}",
                        c_type=p.spelling,
                        type_kind=p.kind_name,
                        pointee_spelling=p.pointee_spelling,
                        pointee_kind=p.pointee_kind,
                        is_const_pointee=p.is_const_pointee,
                    )
                )

            ast.functions.append(
                CFuncDecl(
                    name=cursor.spelling,
                    return_type=ret.spelling,
                    return_type_kind=ret.kind_name,
                    params=params,
                    source_file=str(header_path),
                    ret_pointee_spelling=ret.pointee_spelling,
                    ret_pointee_kind=ret.pointee_kind,
                    ret_is_const_pointee=ret.is_const_pointee,
                )
            )

    return ast


# ---------------------------------------------------------------------------
# JSON serialisation (intermediate file for debugging)
# ---------------------------------------------------------------------------


def ast_to_json(ast: CHeaderAST, pretty: bool = True) -> str:
    """Serialize the parsed AST to JSON."""
    return json.dumps(asdict(ast), indent=2 if pretty else None)


def dump_ast_json(ast: CHeaderAST, out_path: str | Path) -> Path:
    """Write the AST JSON to a file and return the path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(ast_to_json(ast))
    return out_path
