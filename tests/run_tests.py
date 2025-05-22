"""Test runner script with comprehensive coverage."""
import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run all tests with comprehensive options."""
    test_dir = Path(__file__).parent

    # Basic test command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--strict-markers",  # Fail on unknown markers
        "--strict-config",  # Fail on unknown config options
    ]

    # Add coverage if available
    try:
        import pytest_cov

        cmd.extend(
            [
                "--cov=ifcpeek",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
                "--cov-fail-under=90",  # Require 90% coverage
            ]
        )
    except ImportError:
        print("pytest-cov not available, running without coverage")

    # Run tests
    print("Running IfcPeek tests...")
    print("Command:", " ".join(cmd))
    print("-" * 60)

    result = subprocess.run(cmd)
    return result.returncode


def run_specific_test_suite(suite_name):
    """Run a specific test suite."""
    test_files = {
        "config": "test_config.py",
        "exceptions": "test_exceptions.py",
        "integration": "test_integration.py",
        "main": "test_main.py",
        "structure": "test_package_structure.py",
        "imports": "test_main_imports.py",
    }

    if suite_name not in test_files:
        print(f"Unknown test suite: {suite_name}")
        print(f"Available suites: {', '.join(test_files.keys())}")
        return 1

    test_dir = Path(__file__).parent
    test_file = test_dir / test_files[suite_name]

    cmd = [sys.executable, "-m", "pytest", str(test_file), "-v"]

    print(f"Running {suite_name} tests...")
    print("Command:", " ".join(cmd))
    print("-" * 60)

    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    if len(sys.argv) > 1:
        suite = sys.argv[1]
        exit_code = run_specific_test_suite(suite)
    else:
        exit_code = run_tests()

    sys.exit(exit_code)
