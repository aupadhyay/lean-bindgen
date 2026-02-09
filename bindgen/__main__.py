"""
__main__.py — CLI entry point for lean-bindgen.

Usage:
    python -m bindgen path/to/header.h [-o output_dir] [--module Name]

This is the single command that does everything:
  1. Parses the C header with libclang
  2. Dumps the intermediate JSON AST (for debugging)
  3. Maps C types to Lean FFI types
  4. Generates the .lean binding file
  5. Generates the .c glue file
"""

import argparse
import sys
from pathlib import Path

from .parser import parse_header, dump_ast_json
from .mapper import map_function
from .codegen import gen_lean, gen_c_glue, write_output


def _header_to_module_name(header_path: Path) -> str:
    """
    Derive a Lean module name from the header filename.
    e.g. "simple_math.h" → "SimpleMath"
    """
    stem = header_path.stem  # "simple_math"
    # Convert snake_case to PascalCase
    return "".join(part.capitalize() for part in stem.split("_"))


def _header_to_prefix(header_path: Path) -> str:
    """
    Derive the C symbol prefix from the header filename.
    e.g. "simple_math.h" → "simple_math"
    """
    return header_path.stem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lean-bindgen",
        description="Generate Lean 4 FFI bindings from a C header.",
    )
    parser.add_argument(
        "header",
        type=Path,
        help="Path to the C header file (.h)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("generated"),
        help="Output directory (default: generated/)",
    )
    parser.add_argument(
        "--module",
        type=str,
        default=None,
        help="Lean module name (default: derived from header filename)",
    )
    parser.add_argument(
        "-I",
        action="append",
        default=[],
        dest="includes",
        help="Additional include directories for the C parser",
    )
    args = parser.parse_args(argv)

    header: Path = args.header.resolve()
    out_dir: Path = args.output
    module_name: str = args.module or _header_to_module_name(header)
    prefix: str = _header_to_prefix(header)

    # ── Step 1: Parse ─────────────────────────────────────────────────────
    print(f"[1/4] Parsing {header.name} ...")
    clang_args = []
    for inc in args.includes:
        clang_args.extend(["-I", inc])
    ast = parse_header(header, extra_args=clang_args or None)
    print(f"      Found {len(ast.functions)} function(s)")

    # ── Step 2: Dump JSON AST ─────────────────────────────────────────────
    json_path = dump_ast_json(ast, out_dir / "ast.json")
    print(f"[2/4] AST written to {json_path}")

    # ── Step 3: Map types ─────────────────────────────────────────────────
    print(f"[3/4] Mapping C types → Lean types ...")
    mapped = []
    skipped = []
    for func in ast.functions:
        result = map_function(func, prefix)
        if result is not None:
            mapped.append(result)
        else:
            skipped.append(func.name)

    if skipped:
        for name in skipped:
            print(f"      ⚠ Skipped '{name}' (unsupported types)")
    print(f"      Mapped {len(mapped)}/{len(ast.functions)} function(s)")

    if not mapped:
        print("Nothing to generate. Exiting.")
        return 1

    # ── Step 4: Generate code ─────────────────────────────────────────────
    print(f"[4/4] Generating code ...")

    lean_code = gen_lean(module_name, mapped, header.name)
    lean_path = write_output(lean_code, out_dir / f"{module_name}.lean")
    print(f"      Lean bindings → {lean_path}")

    c_code = gen_c_glue(mapped, header.name)
    c_path = write_output(c_code, out_dir / "ffi.c")
    print(f"      C glue code   → {c_path}")

    print()
    print(f"Done! Generated {len(mapped)} binding(s).")
    print(f"Next steps:")
    print(f"  1. Copy {lean_path} into your Lean project")
    print(f"  2. Copy {c_path} into your c/ directory")
    print(f"  3. Update lakefile.lean to compile the new C file")
    print(f"  4. Run `lake build`")

    return 0


if __name__ == "__main__":
    sys.exit(main())
