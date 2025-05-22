#!/usr/bin/env python3
"""
Test script to verify the STDOUT/STDERR separation fixes.
This validates that the fixed code properly separates query results and messages.
"""

import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, Mock
import io
from contextlib import redirect_stdout, redirect_stderr


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
#7=IFCWALL('wall-guid-001',$,$,'TestWall-001',$,$,$,$,$);
#8=IFCWALL('wall-guid-002',$,$,'TestWall-002',$,$,$,$,$);
#9=IFCDOOR('door-guid-001',$,$,'TestDoor-001',$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;"""
    )
    temp_file.close()
    return Path(temp_file.name)


def test_query_execution_stdout_stderr():
    """Test that query execution sends results to STDOUT and messages to STDERR."""
    print("🧪 Testing query execution STDOUT/STDERR separation...")

    ifc_file = create_test_ifc_file()

    try:
        # Add the src directory to path and test the shell directly
        test_script = f"""
import sys
sys.path.insert(0, 'src')

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

# Mock ifcopenshell to avoid dependency issues
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.by_type.return_value = []
    mock_open.return_value = mock_model
    
    # Mock selector to return test results
    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_wall = Mock()
        mock_wall.__str__ = Mock(return_value="#7=IFCWALL('wall-guid-001',$,$,'TestWall-001',$,$,$,$,$);")
        mock_filter.return_value = [mock_wall]
        
        shell = IfcPeek("{str(ifc_file)}")
        shell._execute_query("IfcWall")
"""

        # Run the test script and capture stdout/stderr separately
        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        stdout_lines = (
            result.stdout.strip().split("\n") if result.stdout.strip() else []
        )
        stderr_lines = (
            result.stderr.strip().split("\n") if result.stderr.strip() else []
        )

        print(f"📊 STDOUT lines: {len(stdout_lines)}")
        print(f"📊 STDERR lines: {len(stderr_lines)}")

        # Check that query results are in STDOUT
        query_results_in_stdout = any(
            "#7=IFCWALL('wall-guid-001'" in line for line in stdout_lines
        )

        # Check that debug messages are in STDERR
        debug_messages_in_stderr = any("DEBUG:" in line for line in stderr_lines)

        # Check that no query results are in STDERR
        query_results_in_stderr = any(
            "#7=IFCWALL('wall-guid-001'" in line for line in stderr_lines
        )

        success = (
            query_results_in_stdout
            and debug_messages_in_stderr
            and not query_results_in_stderr
        )

        if success:
            print("✅ Query execution STDOUT/STDERR separation working correctly")
            print(f"   ✓ Query results in STDOUT: {query_results_in_stdout}")
            print(f"   ✓ Debug messages in STDERR: {debug_messages_in_stderr}")
            print(f"   ✓ No query results in STDERR: {not query_results_in_stderr}")
        else:
            print("❌ Query execution STDOUT/STDERR separation failed")
            print(f"   - Query results in STDOUT: {query_results_in_stdout}")
            print(f"   - Debug messages in STDERR: {debug_messages_in_stderr}")
            print(f"   - Query results leaked to STDERR: {query_results_in_stderr}")
            print("\n📋 STDOUT content:")
            for i, line in enumerate(stdout_lines[:5]):  # Show first 5 lines
                print(f"  {i+1}: {line}")
            print("\n📋 STDERR content:")
            for i, line in enumerate(stderr_lines[:10]):  # Show first 10 lines
                print(f"  {i+1}: {line}")

        return success

    finally:
        ifc_file.unlink()


def test_help_command_stderr():
    """Test that help command output goes to STDERR."""
    print("\n🧪 Testing help command STDERR routing...")

    ifc_file = create_test_ifc_file()

    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

# Mock ifcopenshell
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.by_type.return_value = []
    mock_open.return_value = mock_model
    
    shell = IfcPeek("{str(ifc_file)}")
    shell._show_help()
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        # Help content should be in STDERR
        help_in_stderr = "IfcPeek - Interactive IFC Model Query Tool" in result.stderr
        help_not_in_stdout = (
            "IfcPeek - Interactive IFC Model Query Tool" not in result.stdout
        )

        success = help_in_stderr and help_not_in_stdout

        if success:
            print("✅ Help command correctly routed to STDERR")
        else:
            print("❌ Help command not properly routed")
            print(f"   - Help in STDERR: {help_in_stderr}")
            print(f"   - Help not in STDOUT: {help_not_in_stdout}")

        return success

    finally:
        ifc_file.unlink()


def test_main_error_messages_stderr():
    """Test that main function error messages go to STDERR."""
    print("\n🧪 Testing main function error routing...")

    # Test with nonexistent file
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
sys.path.insert(0, 'src')
try:
    from ifcpeek.__main__ import main
    sys.argv = ['ifcpeek', 'nonexistent.ifc']
    main()
except SystemExit:
    pass
""",
        ],
        capture_output=True,
        text=True,
    )

    # Error messages should be in STDERR
    error_in_stderr = "not found" in result.stderr or "Error:" in result.stderr
    no_error_in_stdout = (
        "not found" not in result.stdout and "Error:" not in result.stdout
    )

    success = error_in_stderr and no_error_in_stdout

    if success:
        print("✅ Main function errors correctly sent to STDERR")
    else:
        print("❌ Main function errors not properly separated")
        print(f"   - Error in STDERR: {error_in_stderr}")
        print(f"   - No error in STDOUT: {no_error_in_stdout}")
        if result.stdout:
            print(f"   - Unexpected STDOUT: {result.stdout[:100]}...")

    return success


def test_signal_handler_messages_stderr():
    """Test that signal handler messages go to STDERR."""
    print("\n🧪 Testing signal handler message routing...")

    ifc_file = create_test_ifc_file()

    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock
import signal

# Mock ifcopenshell
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.by_type.return_value = []
    mock_open.return_value = mock_model
    
    shell = IfcPeek("{str(ifc_file)}")
    
    # Get and test the SIGINT handler
    with patch("signal.signal") as mock_signal:
        shell._setup_signal_handlers()
        
        # Find the SIGINT handler
        sigint_handler = None
        for call in mock_signal.call_args_list:
            if call[0][0] == signal.SIGINT:
                sigint_handler = call[0][1]
                break
        
        if sigint_handler:
            # Test the handler
            sigint_handler(signal.SIGINT, None)
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        # Signal handler message should be in STDERR
        signal_msg_in_stderr = "(Use Ctrl-D to exit" in result.stderr
        signal_msg_not_in_stdout = "(Use Ctrl-D to exit" not in result.stdout

        success = signal_msg_in_stderr and signal_msg_not_in_stdout

        if success:
            print("✅ Signal handler messages correctly routed to STDERR")
        else:
            print("❌ Signal handler messages not properly routed")
            print(f"   - Signal message in STDERR: {signal_msg_in_stderr}")
            print(f"   - Signal message not in STDOUT: {signal_msg_not_in_stdout}")

        return success

    finally:
        ifc_file.unlink()


def test_query_error_messages_stderr():
    """Test that query error messages go to STDERR."""
    print("\n🧪 Testing query error message routing...")

    ifc_file = create_test_ifc_file()

    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

# Mock ifcopenshell
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.by_type.return_value = []
    mock_open.return_value = mock_model
    
    # Mock selector to raise error
    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_filter.side_effect = Exception("Invalid selector syntax")
        
        shell = IfcPeek("{str(ifc_file)}")
        shell._execute_query("InvalidQuery[")
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        # Error messages should be in STDERR
        error_header_in_stderr = "IFC QUERY EXECUTION ERROR" in result.stderr
        error_not_in_stdout = "IFC QUERY EXECUTION ERROR" not in result.stdout
        traceback_in_stderr = "FULL PYTHON TRACEBACK:" in result.stderr

        success = error_header_in_stderr and error_not_in_stdout and traceback_in_stderr

        if success:
            print("✅ Query error messages correctly routed to STDERR")
        else:
            print("❌ Query error messages not properly routed")
            print(f"   - Error header in STDERR: {error_header_in_stderr}")
            print(f"   - Error not in STDOUT: {error_not_in_stdout}")
            print(f"   - Traceback in STDERR: {traceback_in_stderr}")

        return success

    finally:
        ifc_file.unlink()


def test_empty_query_results():
    """Test that empty query results produce no STDOUT output."""
    print("\n🧪 Testing empty query results...")

    ifc_file = create_test_ifc_file()

    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

# Mock ifcopenshell
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.by_type.return_value = []
    mock_open.return_value = mock_model
    
    # Mock selector to return empty results
    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_filter.return_value = []  # Empty results
        
        shell = IfcPeek("{str(ifc_file)}")
        shell._execute_query("IfcNonExistentType")
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        # STDOUT should be empty for empty results
        stdout_empty = len(result.stdout.strip()) == 0
        # STDERR should contain debug info
        debug_in_stderr = "DEBUG:" in result.stderr

        success = stdout_empty and debug_in_stderr

        if success:
            print("✅ Empty query results correctly produce no STDOUT output")
        else:
            print("❌ Empty query results handling failed")
            print(f"   - STDOUT empty: {stdout_empty}")
            print(f"   - Debug in STDERR: {debug_in_stderr}")
            if result.stdout.strip():
                print(f"   - Unexpected STDOUT: '{result.stdout}'")

        return success

    finally:
        ifc_file.unlink()


def test_multiple_query_results():
    """Test that multiple query results all go to STDOUT."""
    print("\n🧪 Testing multiple query results...")

    ifc_file = create_test_ifc_file()

    try:
        test_script = f"""
import sys
sys.path.insert(0, 'src')

from ifcpeek.shell import IfcPeek
from unittest.mock import patch, Mock

# Mock ifcopenshell
with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
    mock_model = Mock()
    mock_model.schema = "IFC4"
    mock_model.by_type.return_value = []
    mock_open.return_value = mock_model
    
    # Mock selector to return multiple results
    with patch("ifcpeek.shell.ifcopenshell.util.selector.filter_elements") as mock_filter:
        mock_wall1 = Mock()
        mock_wall1.__str__ = Mock(return_value="#7=IFCWALL('wall-guid-001',$,$,'TestWall-001',$,$,$,$,$);")
        mock_wall2 = Mock()
        mock_wall2.__str__ = Mock(return_value="#8=IFCWALL('wall-guid-002',$,$,'TestWall-002',$,$,$,$,$);")
        mock_filter.return_value = [mock_wall1, mock_wall2]
        
        shell = IfcPeek("{str(ifc_file)}")
        shell._execute_query("IfcWall")
"""

        result = subprocess.run(
            [sys.executable, "-c", test_script], capture_output=True, text=True
        )

        stdout_lines = (
            result.stdout.strip().split("\n") if result.stdout.strip() else []
        )

        # Should have exactly 2 lines in STDOUT
        correct_stdout_count = len(stdout_lines) == 2
        wall1_in_stdout = any("wall-guid-001" in line for line in stdout_lines)
        wall2_in_stdout = any("wall-guid-002" in line for line in stdout_lines)

        # No results should be in STDERR
        no_results_in_stderr = not any(
            "wall-guid" in line for line in result.stderr.split("\n")
        )

        success = (
            correct_stdout_count
            and wall1_in_stdout
            and wall2_in_stdout
            and no_results_in_stderr
        )

        if success:
            print("✅ Multiple query results correctly sent to STDOUT")
            print(f"   ✓ Correct STDOUT line count: {len(stdout_lines)}")
            print(f"   ✓ Both results in STDOUT: {wall1_in_stdout and wall2_in_stdout}")
            print(f"   ✓ No results in STDERR: {no_results_in_stderr}")
        else:
            print("❌ Multiple query results handling failed")
            print(f"   - STDOUT line count: {len(stdout_lines)} (expected 2)")
            print(f"   - Wall1 in STDOUT: {wall1_in_stdout}")
            print(f"   - Wall2 in STDOUT: {wall2_in_stdout}")
            print(f"   - No results in STDERR: {no_results_in_stderr}")

        return success

    finally:
        ifc_file.unlink()


def main():
    """Run all STDOUT/STDERR separation tests."""
    print("=" * 70)
    print("IFCPEEK STDOUT/STDERR SEPARATION VALIDATION")
    print("=" * 70)
    print("Testing the fixed code to ensure proper stream separation...")
    print()

    tests = [
        ("Query Execution STDOUT/STDERR", test_query_execution_stdout_stderr),
        ("Help Command STDERR Routing", test_help_command_stderr),
        ("Main Error Messages STDERR", test_main_error_messages_stderr),
        ("Signal Handler Messages STDERR", test_signal_handler_messages_stderr),
        ("Query Error Messages STDERR", test_query_error_messages_stderr),
        ("Empty Query Results", test_empty_query_results),
        ("Multiple Query Results", test_multiple_query_results),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    print("\n" + "=" * 70)
    print("📊 VALIDATION RESULTS")
    print("=" * 70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")

    print(f"\n📈 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 ALL STDOUT/STDERR SEPARATION TESTS PASSED!")
        print("✅ Query results properly go to STDOUT")
        print("✅ All messages/errors properly go to STDERR")
        print("✅ The fixed code should resolve the failing integration tests")
        print("\n🔧 Key fixes implemented:")
        print("   • Query results: print() without file= → STDOUT")
        print("   • Debug messages: print(..., file=sys.stderr) → STDERR")
        print("   • Error messages: print(..., file=sys.stderr) → STDERR")
        print("   • Help text: print(..., file=sys.stderr) → STDERR")
        print("   • Tracebacks: traceback.print_exc(file=sys.stderr) → STDERR")
        return True
    else:
        print(f"\n⚠️ {total - passed} tests still failing")
        print("Additional fixes may be needed for complete STDOUT/STDERR separation.")

        failed_tests = [name for name, success in results if not success]
        print("\n❌ Failed tests:")
        for test_name in failed_tests:
            print(f"   • {test_name}")

        return False


if __name__ == "__main__":
    print("🚀 Starting STDOUT/STDERR separation validation...")
    success = main()

    if success:
        print("\n✅ VALIDATION COMPLETE: All fixes working correctly!")
        print("🎯 The failing integration tests should now pass.")
    else:
        print("\n⚠️ VALIDATION INCOMPLETE: Some issues remain.")
        print("🔍 Check the failed tests above for details.")

    sys.exit(0 if success else 1)
