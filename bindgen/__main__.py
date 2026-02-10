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
from .ir import BindgenConfig
from .ir_builder import IRBuilder
from .type_mapper import TypeMapper
from .codegen import CodeGenerator, write_output


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

    # Step 1: PARSE
    print(f"[1/5] Parsing {header.name} ...")
    clang_args = []
    for inc in args.includes:
        clang_args.extend(["-I", inc])
    ast = parse_header(header, extra_args=clang_args or None)
    print(f"\tFound {len(ast.functions)} function(s)")

    # Step 2: Dump JSON AST
    json_path = dump_ast_json(ast, out_dir / "ast.json")
    print(f"[2/5] AST written to {json_path}")

    # Step 3: BUILD IR
    print(f"[3/5] Building IR ...")
    config = BindgenConfig(
        module_name=module_name, module_prefix=prefix, header_name=header.name
    )
    ir_builder = IRBuilder(config)
    ir_ctx = ir_builder.build(ast)
    print(
        f"\tBuilt IR with {len(ir_ctx.all_types())} type(s), {len(ir_ctx.all_functions())} function(s)"
    )

    # Step 4: ANALYZE (type mapping)
    print(f"[4/5] Analyzing types ...")
    type_mapper = TypeMapper(ir_ctx)

    # Determine which functions are supported
    skipped = []
    for func in ir_ctx.all_functions():
        # Check if return type is supported
        ret_mapping = type_mapper.map_type(func.return_type)
        if ret_mapping is None:
            skipped.append(func.c_name)
            continue

        # Check if all parameters are supported
        all_params_ok = True
        for param in func.params:
            param_mapping = type_mapper.map_type(param.type_id)
            if param_mapping is None:
                all_params_ok = False
                break

        if all_params_ok:
            ir_ctx.mark_function_supported(func.id)
        else:
            skipped.append(func.c_name)

    if skipped:
        for name in skipped:
            print(f"\tWarning: Skipped '{name}' (unsupported types)")

    supported_count = len(ir_ctx.get_supported_functions())
    total_count = len(ir_ctx.all_functions())
    print(f"\tMapped {supported_count}/{total_count} function(s)")

    if supported_count == 0:
        print("Nothing to generate. Exiting.")
        return 1

    # Step 5: CODEGEN
    print(f"[5/5] Generating code ...")
    codegen = CodeGenerator(ir_ctx, type_mapper)

    lean_code = codegen.generate_lean()
    lean_path = write_output(lean_code, out_dir / f"{module_name}.lean")
    print(f"\tLean bindings → {lean_path}")

    c_code = codegen.generate_c_glue()
    c_path = write_output(c_code, out_dir / "ffi.c")
    print(f"\tC glue code → {c_path}")

    print()
    print(f"Done! Generated {supported_count} binding(s).")
    print(f"Next steps:")
    print(f" 1. Copy {lean_path} into your Lean project")
    print(f" 2. Copy {c_path} into your c/ directory")
    print(f" 3. Update lakefile.lean to compile the new C file")
    print(f" 4. Run `lake build`")

    return 0


if __name__ == "__main__":
    sys.exit(main())
