#!/usr/bin/env python3
"""
Test to verify the integration error message fixes.
"""

import tempfile
import sys
from pathlib import Path
from unittest.mock import patch, Mock
import io
from contextlib import redirect_stdout, redirect_stderr
import pytest

# Add the source directory to Python path for testing
sys.path.insert(0, "src")

try:
    from ifcpeek.shell import IfcPeek
    from ifcpeek.__main__ import main

    print("✅ Successfully imported modules")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)


def create_test_ifc_file():
    """Create a test IFC file."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ifc", delete=False)
    temp_file.write(
        """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('test_model.ifc','2024-01-01T00:00:00',('Test Author'),('Test Organization'),'IfcOpenShell','IfcOpenShell','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('0u4wgLe6n0ABVaiXyikbkA',$,'Test Project',$,$,$,$,(#2),#3);
#2=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#4,$);
#3=IFCUNITASSIGNMENT((#5));
#4=IFCAXIS2PLACEMENT3D(#6,$,$);
#5=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#6=IFCCARTESIANPOINT((0.,0.,0.));
ENDSEC;
END-ISO-10303-21;"""
    )
    temp_file.close()
    return Path(temp_file.name)


def test_main_error_message_format():
    """Test that main function error messages go to stderr with correct format."""
    print("\n🧪 Testing main error message format...")

    mock_ifc_file = create_test_ifc_file()

    try:
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
                # Mock IfcPeek to raise an error
                with patch(
                    "ifcpeek.__main__.IfcPeek",
                    side_effect=RuntimeError("Session creation failed"),
                ):
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 1

        stderr_output = stderr_buffer.getvalue()

        # Check for the expected error message format
        if "Unexpected error: Session creation failed" in stderr_output:
            print("✅ Main error message format is correct")
            return True
        else:
            print("❌ Main error message format is incorrect")
            print("stderr output:")
            print(stderr_output)
            return False

    finally:
        mock_ifc_file.unlink()


def test_shell_run_error_format():
    """Test shell.run() error format."""
    print("\n🧪 Testing shell.run() error format...")

    mock_ifc_file = create_test_ifc_file()

    try:
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            with patch("sys.argv", ["ifcpeek", str(mock_ifc_file)]):
                with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                    mock_model = Mock()
                    mock_open.return_value = mock_model

                    # Mock shell.run() to raise an error
                    with patch.object(
                        IfcPeek, "run", side_effect=RuntimeError("Run failed")
                    ):
                        try:
                            main()
                        except SystemExit as e:
                            assert e.code == 1

        stderr_output = stderr_buffer.getvalue()

        if "Unexpected error: Run failed" in stderr_output:
            print("✅ Shell run error message format is correct")
            return True
        else:
            print("❌ Shell run error message format is incorrect")
            print("stderr output:")
            print(stderr_output)
            return False

    finally:
        mock_ifc_file.unlink()


def test_keyboard_interrupt_message():
    """Test KeyboardInterrupt message format."""
    print("\n🧪 Testing KeyboardInterrupt message format...")

    mock_ifc_file = create_test_ifc_file()

    try:
        stdout_buffer = io.StringIO()

        with redirect_stdout(stdout_buffer):
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                shell = IfcPeek(str(mock_ifc_file))

                # Mock session to simulate KeyboardInterrupt
                with patch.object(shell, "session") as mock_session:
                    mock_session.prompt.side_effect = [
                        KeyboardInterrupt,  # First Ctrl-C
                        EOFError,  # Exit
                    ]

                    shell.run()

        stdout_output = stdout_buffer.getvalue()

        if "(Use Ctrl-D to exit, or type /exit)" in stdout_output:
            print("✅ KeyboardInterrupt message format is correct")
            return True
        else:
            print("❌ KeyboardInterrupt message not found")
            print("stdout output:")
            print(stdout_output)
            return False

    finally:
        mock_ifc_file.unlink()


def test_session_error_message():
    """Test session error message format."""
    print("\n🧪 Testing session error message format...")

    mock_ifc_file = create_test_ifc_file()

    try:
        stdout_buffer = io.StringIO()

        with redirect_stdout(stdout_buffer):
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                shell = IfcPeek(str(mock_ifc_file))

                # Mock session to simulate session error
                with patch.object(shell, "session") as mock_session:
                    mock_session.prompt.side_effect = [
                        RuntimeError("Session error"),  # Session error
                        EOFError,  # Exit
                    ]

                    shell.run()

        stdout_output = stdout_buffer.getvalue()

        if "Error: Session error" in stdout_output:
            print("✅ Session error message format is correct")
            return True
        else:
            print("❌ Session error message format is incorrect")
            print("stdout output:")
            print(stdout_output)
            return False

    finally:
        mock_ifc_file.unlink()


def main_test():
    """Run all integration fix tests."""
    print("🔧 Integration Error Message Fixes Test")
    print("=" * 45)

    tests = [
        ("Main Error Message Format", test_main_error_message_format),
        ("Shell Run Error Format", test_shell_run_error_format),
        ("KeyboardInterrupt Message", test_keyboard_interrupt_message),
        ("Session Error Message", test_session_error_message),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 45)
    print("📊 RESULTS SUMMARY")
    print("=" * 45)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 All integration fixes verified successfully!")
        print("The failing integration tests should now pass.")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests still failing - additional fixes needed.")
        return False


if __name__ == "__main__":
    success = main_test()
    sys.exit(0 if success else 1)
