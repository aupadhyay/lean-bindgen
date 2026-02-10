"""
Build-time integration test for lean-bindgen.

Copies the self-contained Lake project in tests/e2e/ to a temp directory,
runs `lake build`, and verifies the resulting binary works.  This proves
that lean-bindgen can run at `lake build` time via a custom Lake target --
no pre-generated files required.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
E2E_DIR = TESTS_DIR / "e2e"


@pytest.fixture
def e2e_project(tmp_path):
    """Copy the e2e project to a temp directory so we don't pollute the repo."""
    project = tmp_path / "e2e"
    shutil.copytree(E2E_DIR, project)
    return project


def test_build_time_bindgen(e2e_project):
    """lake run bindgen + lake build should produce a working binary."""

    # Ensure the bindgen package is importable by python3 inside lake build.
    # In a real consumer project, lean-bindgen would be pip-installed.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    # Step 1: Generate bindings
    gen = subprocess.run(
        ["lake", "run", "bindgen"],
        capture_output=True,
        text=True,
        cwd=e2e_project,
        env=env,
    )
    assert gen.returncode == 0, (
        f"lake run bindgen failed:\nstdout:\n{gen.stdout}\nstderr:\n{gen.stderr}"
    )

    # Step 2: Build the project
    build = subprocess.run(
        ["lake", "build"],
        capture_output=True,
        text=True,
        cwd=e2e_project,
        env=env,
    )
    assert build.returncode == 0, (
        f"lake build failed:\nstdout:\n{build.stdout}\nstderr:\n{build.stderr}"
    )

    # Verify generated files were created
    assert (e2e_project / "generated" / "SimpleMath.lean").exists(), (
        "bindgen target did not produce generated/SimpleMath.lean"
    )
    assert (e2e_project / "generated" / "ffi.c").exists(), (
        "bindgen target did not produce generated/ffi.c"
    )

    # Run the built binary
    binary = e2e_project / ".lake" / "build" / "bin" / "test"
    assert binary.exists(), f"binary not found at {binary}"

    run = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, f"binary crashed:\n{run.stderr}"
    assert "add(5, 3) = 8" in run.stdout, (
        f"unexpected output:\n{run.stdout}"
    )
