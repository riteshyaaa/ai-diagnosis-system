#!/usr/bin/env python3
"""Run backend test modules in separate processes to bound ML test memory."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"
OPTUNA_TEST_FILE = Path("tests/unit/test_tabular_models.py")
OPTUNA_TEST_NAME = "test_optuna_tabular_tuner"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "test_files",
        nargs="*",
        help="Optional test files relative to the repository root; defaults to all tests.",
    )
    args = parser.parse_args()

    if args.test_files:
        test_files = []
        for value in args.test_files:
            path = (ROOT / value).resolve()
            try:
                path.relative_to(TEST_ROOT.resolve())
            except ValueError:
                parser.error(f"test path must be inside {TEST_ROOT.relative_to(ROOT)}: {value}")
            if not path.is_file() or not path.name.startswith("test_") or path.suffix != ".py":
                parser.error(f"not a pytest test file: {value}")
            test_files.append(path)
    else:
        test_files = sorted(TEST_ROOT.rglob("test_*.py"))

    if not test_files:
        print("No backend test files found.", file=sys.stderr)
        return 2

    env = os.environ.copy()
    python_path = [str(ROOT / "backend"), str(ROOT)]
    if env.get("PYTHONPATH"):
        python_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    optuna_available = importlib.util.find_spec("optuna") is not None

    failures: list[str] = []
    for test_file in test_files:
        relative_path = test_file.relative_to(ROOT)
        command = [sys.executable, "-m", "pytest", "-q", str(relative_path)]
        if relative_path == OPTUNA_TEST_FILE and not optuna_available:
            command.extend(["-k", f"not {OPTUNA_TEST_NAME}"])
            print(f"Optuna unavailable; deselecting {OPTUNA_TEST_NAME}.", flush=True)

        print(f"\n===== {relative_path} =====", flush=True)
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if result.returncode != 0:
            failures.append(f"{relative_path} (exit {result.returncode})")

    print(
        f"\nBackend test modules: {len(test_files)}; "
        f"failing modules: {len(failures)}."
    )
    if failures:
        print("Failed modules:\n- " + "\n- ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
