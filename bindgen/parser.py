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


@dataclass
class CFuncDecl:
    """A C function declaration extracted from a header."""

    name: str  # e.g. "add"
    return_type: str  # e.g. "int"
    return_type_kind: str  # e.g. "INT"
    params: list[CParam] = field(default_factory=list)
    source_file: Optional[str] = None


@dataclass
class CHeaderAST:
    """The full parsed result for one header file."""

    header_path: str
    functions: list[CFuncDecl] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing logic
# ---------------------------------------------------------------------------


def _resolve_type(clang_type) -> tuple[str, str]:
    """
    Get a clean (spelling, kind_name) pair from a clang Type.
    Follows typedefs to their canonical form so we map the *real* type.
    """
    canonical = clang_type.get_canonical()
    spelling = clang_type.spelling  # keep the user-facing name
    kind_name = canonical.kind.name  # but use the canonical kind for mapping
    return spelling, kind_name


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

        if cursor.kind == CursorKind.FUNCTION_DECL:  # type: ignore[attr-defined]
            ret_spelling, ret_kind = _resolve_type(cursor.result_type)

            params = []
            for i, arg in enumerate(cursor.get_arguments()):
                p_spelling, p_kind = _resolve_type(arg.type)
                params.append(
                    CParam(
                        name=arg.spelling or f"arg{i}",
                        c_type=p_spelling,
                        type_kind=p_kind,
                    )
                )

            ast.functions.append(
                CFuncDecl(
                    name=cursor.spelling,
                    return_type=ret_spelling,
                    return_type_kind=ret_kind,
                    params=params,
                    source_file=str(header_path),
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
