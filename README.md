# lean-bindgen

Automatically generate [Lean 4](https://lean-lang.org/) FFI bindings from C header files.

Given a `.h` file, `lean-bindgen` produces:

1. **A `.lean` file** with `@[extern]` opaque declarations and correct type signatures
2. **A `.c` glue file** with thin wrappers that adapt C types to Lean's FFI ABI


We use Python to parse the C header files using `libclang`. Ideally, this would be done in Lean, but it seems efforts to [build a C parser in Lean](https://github.com/opencompl/C-parsing-for-Lean4) have been paused.

## Status

**This project is a work in progress.** Contributions are welcome. See [ROADMAP.md](ROADMAP.md).

The current implementation handles trivial functions with scalar types. We're incrementally adding support for strings, opaque pointers, enums, callbacks, and structs.

## Setup

```bash
# Install dependencies (using uv)
uv sync

# Or with pip
pip install -e .
```

## Running Tests

The test suite currently uses snapshot testing. For every `.h` file in `tests/headers/`, the pipeline runs and compares the generated output against expected files in `tests/expected/<header_stem>/`.

```bash
# Run tests
uv run pytest

# To update golden files after an intentional change
UPDATE_EXPECTED=1 uv run pytest
```

## Project Structure

```
bindgen/
  __main__.py      # CLI entry point
  parser.py        # C header parsing via libclang
  type_mapper.py   # C type → Lean type mapping
  ir.py            # Intermediate representation layer
  ir_builder.py    # Build IR from parsed AST
  ir_printer.py    # Debug printing for IR
  codegen.py       # .lean and .c code generation

tests/
  headers/         # Test input headers
  expected/        # Golden files for snapshot tests
  test_snapshot.py # Snapshot tests
  test_build_time.py # Build time tests
  e2e/             # End-to-end tests with actual Lean project

```
