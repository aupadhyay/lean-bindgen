"""
Snapshot tests for lean-bindgen.

For every .h file in tests/headers/, we run the bindgen pipeline and compare
the generated .lean and .c output against golden files in tests/expected/<stem>/.

To add a new test:  drop a header in tests/headers/ and the expected output in
tests/expected/<header_stem>/<Module>.lean + ffi.c.

To update golden files after an intentional change:
    UPDATE_EXPECTED=1 pytest tests/test_snapshot.py
"""

import difflib
import os
from pathlib import Path

import pytest

from bindgen.parser import parse_header
from bindgen.mapper import map_function
from bindgen.codegen import gen_lean, gen_c_glue

TESTS_DIR = Path(__file__).resolve().parent
HEADERS_DIR = TESTS_DIR / "headers"
EXPECTED_DIR = TESTS_DIR / "expected"


def _header_to_module_name(header_path: Path) -> str:
    """e.g. 'simple_math.h' -> 'SimpleMath'"""
    return "".join(part.capitalize() for part in header_path.stem.split("_"))


def _header_to_prefix(header_path: Path) -> str:
    """e.g. 'simple_math.h' -> 'simple_math'"""
    return header_path.stem


def _run_bindgen(header: Path) -> dict[str, str]:
    """Run the full parse -> map -> codegen pipeline, return {filename: content}."""
    module_name = _header_to_module_name(header)
    prefix = _header_to_prefix(header)

    ast = parse_header(header)

    mapped = []
    for func in ast.functions:
        result = map_function(func, prefix)
        if result is not None:
            mapped.append(result)

    outputs: dict[str, str] = {}

    if mapped:
        outputs[f"{module_name}.lean"] = gen_lean(module_name, mapped, header.name)
        outputs["ffi.c"] = gen_c_glue(mapped, header.name)

    return outputs


def _unified_diff(expected: str, actual: str, filename: str) -> str:
    """Return a unified diff string, or empty if identical."""
    if expected == actual:
        return ""
    diff_lines = difflib.unified_diff(
        expected.splitlines(keepends=True),
        actual.splitlines(keepends=True),
        fromfile=f"expected/{filename}",
        tofile=f"actual/{filename}",
    )
    return "".join(diff_lines)


# Discover all test headers
_headers = sorted(HEADERS_DIR.glob("*.h")) if HEADERS_DIR.exists() else []


@pytest.mark.parametrize(
    "header",
    _headers,
    ids=[h.stem for h in _headers],
)
def test_snapshot(header: Path):
    """Run bindgen on a header and compare output to golden files."""
    stem = header.stem
    expected_dir = EXPECTED_DIR / stem
    update = os.environ.get("UPDATE_EXPECTED", "") == "1"

    assert expected_dir.exists(), (
        f"No expected output directory: {expected_dir}\n"
        f"Run with UPDATE_EXPECTED=1 to create it."
    )

    generated = _run_bindgen(header)
    assert generated, f"bindgen produced no output for {header.name}"

    mismatches: list[str] = []

    for filename, actual_content in generated.items():
        expected_file = expected_dir / filename

        if update:
            expected_dir.mkdir(parents=True, exist_ok=True)
            expected_file.write_text(actual_content)
            continue

        assert expected_file.exists(), (
            f"Missing expected file: {expected_file}\n"
            f"Run with UPDATE_EXPECTED=1 to create it."
        )

        expected_content = expected_file.read_text()
        diff = _unified_diff(expected_content, actual_content, filename)
        if diff:
            mismatches.append(diff)

    if mismatches:
        full_diff = "\n".join(mismatches)
        pytest.fail(
            f"Snapshot mismatch for {header.name}:\n\n{full_diff}\n\n"
            f"Run with UPDATE_EXPECTED=1 to update golden files."
        )
