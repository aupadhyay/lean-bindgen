# lean-bindgen

Automatically generate [Lean 4](https://lean-lang.org/) FFI bindings from C header files.

Given a `.h` file, `lean-bindgen` produces:

1. **A `.lean` file** with `@[extern]` opaque declarations and correct type signatures
2. **A `.c` glue file** with thin wrappers that adapt C types to Lean's FFI ABI


## Disclaimer

**This project is a work in progress. Contributions are welcome.** Still need to define a proper IR, support structs/enums/typedefs/opaque pointers, handle callbacks, etc.

The current implementation only handles simple functions with scalar types (`int`, `float`, `double`, etc.).

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
  __main__.py   # CLI entry point
  parser.py     # C header parsing via libclang
  mapper.py     # C type → Lean type mapping
  codegen.py    # .lean and .c code generation
tests/
  headers/      # Test input headers
  expected/     # Golden files for snapshot tests
  test_snapshot.py
```
