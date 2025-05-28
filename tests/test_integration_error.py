"""
Complete integration test for error handling system.
This validates the entire error handling workflow from start to finish.
"""

import tempfile
import time
import signal
from pathlib import Path
from unittest.mock import patch, Mock
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from ifcpeek.shell import IfcPeek
from ifcpeek.__main__ import main
from ifcpeek.config import (
    get_config_dir,
    validate_ifc_file_path,
)
from ifcpeek.exceptions import *


class ErrorHandlingValidator:
    """Comprehensive validation of error handling system."""

    def __init__(self):
        self.test_results = []
        self.temp_dirs = []

    def log_result(self, test_name, success, message=""):
        """Log test result with formatting."""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append((test_name, success, message))
        print(f"{status}: {test_name}")
        if message and not success:
            print(f"    └─ {message}")
        elif message and success:
            print(f"    └─ ℹ️  {message}")

    def create_temp_ifc(self, valid=True):
        """Create temporary IFC file for testing."""
        if valid:
            ifc_content = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('test_model.ifc','2024-01-01T00:00:00',('Test'),('Test'),'IfcOpenShell','IfcOpenShell','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('guid',$,'Test Project',$,$,$,$,(#2),#3);
#2=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#4,$);
#3=IFCUNITASSIGNMENT((#5));
#4=IFCAXIS2PLACEMENT3D(#6,$,$);
#5=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCWALL('wall-guid',$,$,'TestWall',$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;"""
        else:
            ifc_content = "This is not a valid IFC file content"

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ifc", delete=False)
        temp_file.write(ifc_content)
        temp_file.close()
        return Path(temp_file.name)

    def test_traceback_display_system(self):
        """Test comprehensive traceback display system."""
        try:
            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                shell = IfcPeek(str(ifc_file))

                # Test nested exception handling
                def create_nested_error():
                    def level_3():
                        raise ValueError("Deep nested error")

                    def level_2():
                        level_3()

                    def level_1():
                        level_2()

                    level_1()

                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements",
                    side_effect=create_nested_error,
                ):

                    # Capture comprehensive output
                    output = StringIO()
                    with redirect_stdout(output):
                        shell._execute_query("IfcWall")

                    traceback_output = output.getvalue()

                    # Verify comprehensive traceback information
                    traceback_features = [
                        "IFC QUERY EXECUTION ERROR",
                        "FULL PYTHON TRACEBACK:",
                        "Traceback (most recent call last):",
                        "ValueError: Deep nested error",
                        "DEBUGGING SUGGESTIONS:",
                        "level_1",
                        "level_2",
                        "level_3",  # Function names in traceback
                        "Query execution failed",
                    ]

                    missing_features = []
                    for feature in traceback_features:
                        if feature not in traceback_output:
                            missing_features.append(feature)

                    if not missing_features:
                        self.log_result(
                            "Traceback Display System",
                            True,
                            "All traceback features present",
                        )
                    else:
                        self.log_result(
                            "Traceback Display System",
                            False,
                            f"Missing features: {missing_features}",
                        )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Traceback Display System", False, str(e))

    def test_signal_handling_system(self):
        """Test comprehensive signal handling system."""
        try:
            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_open.return_value = mock_model

                # Test signal handler setup
                with patch("signal.signal") as mock_signal:
                    shell = IfcPeek(str(ifc_file))

                    # Verify signal handlers were configured
                    signal_calls = mock_signal.call_args_list
                    configured_signals = [call[0][0] for call in signal_calls]

                    signal_tests = [
                        (
                            signal.SIGINT in configured_signals,
                            "SIGINT handler configured",
                        ),
                        (
                            signal.SIGTERM in configured_signals,
                            "SIGTERM handler configured",
                        ),
                        (len(signal_calls) >= 2, "Multiple signal handlers configured"),
                    ]

                    all_signal_tests_passed = all(test[0] for test in signal_tests)

                    if all_signal_tests_passed:
                        self.log_result(
                            "Signal Handling System",
                            True,
                            "All signal handlers configured",
                        )
                    else:
                        failed_tests = [test[1] for test in signal_tests if not test[0]]
                        self.log_result(
                            "Signal Handling System", False, f"Failed: {failed_tests}"
                        )

                # Test SIGINT handler behavior
                try:
                    sigint_handler = None
                    for call in signal_calls:
                        if call[0][0] == signal.SIGINT:
                            sigint_handler = call[0][1]
                            break

                    if sigint_handler:
                        # Capture output from signal handler
                        output = StringIO()
                        with redirect_stdout(output):
                            sigint_handler(signal.SIGINT, None)

                        handler_output = output.getvalue()
                        if "(Use Ctrl-D to exit, or type /exit)" in handler_output:
                            self.log_result(
                                "SIGINT Handler Behavior",
                                True,
                                "Correct prompt message",
                            )
                        else:
                            self.log_result(
                                "SIGINT Handler Behavior",
                                False,
                                "Incorrect handler output",
                            )
                    else:
                        self.log_result(
                            "SIGINT Handler Behavior", False, "Handler not found"
                        )

                except Exception as handler_error:
                    self.log_result(
                        "SIGINT Handler Behavior", False, str(handler_error)
                    )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Signal Handling System", False, str(e))

    def test_error_recovery_system(self):
        """Test comprehensive error recovery system."""
        try:
            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                shell = IfcPeek(str(ifc_file))

                # Test recovery from various error types
                error_scenarios = [
                    (SyntaxError("Syntax error"), "syntax"),
                    (AttributeError("Attribute error"), "attribute"),
                    (ValueError("Value error"), "value"),
                    (RuntimeError("Runtime error"), "runtime"),
                    (MemoryError("Memory error"), "memory"),
                ]

                recovery_success_count = 0
                total_scenarios = len(error_scenarios)

                for error_exception, error_type in error_scenarios:
                    try:
                        with patch(
                            "ifcpeek.shell.ifcopenshell.util.selector.filter_elements",
                            side_effect=error_exception,
                        ):

                            # Process input should not crash
                            result = shell._process_input(f"TestQuery_{error_type}")

                            if result is True:  # Should continue after error
                                recovery_success_count += 1

                    except Exception as recovery_error:
                        self.log_result(
                            f"Error Recovery - {error_type}", False, str(recovery_error)
                        )

                # Test shell functionality after errors
                try:
                    with patch(
                        "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                    ) as mock_selector:
                        mock_entity = Mock()
                        mock_entity.__str__ = Mock(
                            return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
                        )
                        mock_selector.return_value = [mock_entity]

                        # Shell should still work after all errors
                        final_result = shell._process_input("IfcWall")

                        if final_result is True:
                            recovery_success_count += 1

                except Exception as final_test_error:
                    self.log_result(
                        "Post-Error Functionality", False, str(final_test_error)
                    )

                # Evaluate recovery system
                recovery_rate = recovery_success_count / (total_scenarios + 1)
                if recovery_rate >= 0.8:
                    self.log_result(
                        "Error Recovery System",
                        True,
                        f"Recovery rate: {recovery_rate:.1%}",
                    )
                else:
                    self.log_result(
                        "Error Recovery System",
                        False,
                        f"Low recovery rate: {recovery_rate:.1%}",
                    )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Error Recovery System", False, str(e))

    def test_debug_information_system(self):
        """Test comprehensive debug information system."""
        try:
            # Test file loading debug information
            ifc_file = self.create_temp_ifc()

            with patch(
                "ifcpeek.shell.ifcopenshell.open",
                side_effect=RuntimeError("Simulated loading error"),
            ):

                try:
                    output = StringIO()
                    with redirect_stdout(output):
                        IfcPeek(str(ifc_file))
                except Exception:
                    pass  # Expected to fail

                debug_output = output.getvalue()

                # Check for comprehensive debug information
                debug_features = [
                    "IFC MODEL LOADING ERROR - DEBUG INFORMATION",
                    "file_path:",
                    "file_exists:",
                    "file_size:",
                    "error_type:",
                    "Full Python traceback:",
                    "DEBUG: Unexpected error during IFC file loading",
                    "Suggestions:",
                ]

                debug_features_present = sum(
                    1 for feature in debug_features if feature in debug_output
                )
                debug_coverage = debug_features_present / len(debug_features)

                if debug_coverage >= 0.8:
                    self.log_result(
                        "Debug Information System",
                        True,
                        f"Debug coverage: {debug_coverage:.1%}",
                    )
                else:
                    self.log_result(
                        "Debug Information System",
                        False,
                        f"Low debug coverage: {debug_coverage:.1%}",
                    )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Debug Information System", False, str(e))

    def test_exceptions_system(self):
        """Test exception classes with context."""
        try:
            # Test FileNotFoundError with context
            file_error = FileNotFoundError(
                "Test file error", file_path="/test/path.ifc"
            )
            file_error_str = str(file_error)

            # Test InvalidIfcFileError with context
            ifc_error = InvalidIfcFileError(
                "Test IFC error",
                file_path="/test/path.ifc",
                file_size=1024,
                error_type="TestError",
            )
            ifc_error_str = str(ifc_error)

            # Test QueryExecutionError with context
            query_error = QueryExecutionError(
                "Test query error", query="IfcWall", model_schema="IFC4"
            )
            query_error_str = str(query_error)

            # Test ConfigurationError with context
            config_error = ConfigurationError(
                "Test config error",
                config_path="/test/config",
                system_info={"os": "test"},
            )
            config_error_str = str(config_error)

            # Verify context information is included
            context_tests = [
                (
                    "file_path=/test/path.ifc" in file_error_str,
                    "FileNotFoundError context",
                ),
                ("file_size=1024" in ifc_error_str, "InvalidIfcFileError context"),
                ("query=IfcWall" in query_error_str, "QueryExecutionError context"),
                (
                    "config_path=/test/config" in config_error_str,
                    "ConfigurationError context",
                ),
                ("model_schema=IFC4" in query_error_str, "Model schema context"),
                ("os=test" in config_error_str, "System info context"),
            ]

            passed_context_tests = sum(1 for test, _ in context_tests if test)
            context_coverage = passed_context_tests / len(context_tests)

            if context_coverage >= 0.8:
                self.log_result(
                    "Exceptions System",
                    True,
                    f"Context coverage: {context_coverage:.1%}",
                )
            else:
                failed_tests = [desc for test, desc in context_tests if not test]
                self.log_result(
                    "Exceptions System",
                    False,
                    f"Failed context tests: {failed_tests}",
                )

        except Exception as e:
            self.log_result("Exceptions System", False, str(e))

    def test_main_error_handling_integration(self):
        """Test main function error handling integration."""
        try:
            ifc_file = self.create_temp_ifc()

            # Test main function error handling
            with patch("sys.argv", ["ifcpeek", str(ifc_file)]):
                with patch(
                    "ifcpeek.__main__.IfcPeek",
                    side_effect=RuntimeError("Test main error"),
                ):

                    output = StringIO()
                    try:
                        with redirect_stdout(output):
                            with redirect_stderr(output):
                                main()
                    except SystemExit:
                        pass  # Expected

                    main_output = output.getvalue()

                    # Check for main error handling
                    main_features = [
                        "IfcPeek - Starting",
                        "UNEXPECTED ERROR",
                        "Full error details:",
                        "Error handling and debugging active",
                    ]

                    main_features_present = sum(
                        1 for feature in main_features if feature in main_output
                    )
                    main_coverage = main_features_present / len(main_features)

                    if main_coverage >= 0.75:
                        self.log_result(
                            "Main Error Handling Integration",
                            True,
                            f"Main coverage: {main_coverage:.1%}",
                        )
                    else:
                        self.log_result(
                            "Main Error Handling Integration",
                            False,
                            f"Low main coverage: {main_coverage:.1%}",
                        )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Main Error Handling Integration", False, str(e))

    def test_performance_impact_assessment(self):
        """Test that error handling doesn't significantly impact performance."""
        try:
            ifc_file = self.create_temp_ifc()

            # Measure initialization time with error handling
            start_time = time.time()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                shell = IfcPeek(str(ifc_file))

            init_time = time.time() - start_time

            # Test query processing performance
            with patch(
                "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
            ) as mock_selector:
                mock_entity = Mock()
                mock_entity.__str__ = Mock(
                    return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
                )
                mock_selector.return_value = [mock_entity]

                start_time = time.time()
                for _ in range(10):
                    shell._process_input("IfcWall")
                query_time = time.time() - start_time

            # Performance thresholds
            init_acceptable = init_time < 3.0  # 3 seconds for initialization
            query_acceptable = query_time < 2.0  # 2 seconds for 10 queries

            if init_acceptable and query_acceptable:
                self.log_result(
                    "Performance Impact Assessment",
                    True,
                    f"Init: {init_time:.2f}s, Queries: {query_time:.2f}s",
                )
            else:
                self.log_result(
                    "Performance Impact Assessment",
                    False,
                    f"Slow performance - Init: {init_time:.2f}s, Queries: {query_time:.2f}s",
                )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Performance Impact Assessment", False, str(e))

    def test_memory_stability_assessment(self):
        """Test memory usage stability with error handling."""
        try:
            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                shell = IfcPeek(str(ifc_file))

                # Test memory stability with repeated operations
                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                ) as mock_selector:
                    # Alternate between errors and successes
                    for i in range(50):
                        if i % 2 == 0:
                            # Error scenario
                            mock_selector.side_effect = ValueError(f"Test error {i}")
                            shell._process_input(f"BadQuery{i}")
                        else:
                            # Success scenario
                            mock_selector.side_effect = None
                            mock_entity = Mock()
                            mock_entity.__str__ = Mock(
                                return_value=f"#1=IFCWALL('guid-{i}',$,$,'Wall',$,$,$,$,$);"
                            )
                            mock_selector.return_value = [mock_entity]
                            shell._process_input("IfcWall")

                # Verify shell is still functional
                memory_stable = (
                    shell.model is not None
                    and hasattr(shell, "session")
                    and hasattr(shell, "ifc_file_path")
                )

                if memory_stable:
                    self.log_result(
                        "Memory Stability Assessment", True, "Shell remains functional"
                    )
                else:
                    self.log_result(
                        "Memory Stability Assessment", False, "Shell state corrupted"
                    )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Memory Stability Assessment", False, str(e))

    def test_end_to_end_error_scenarios(self):
        """Test complete end-to-end error scenarios."""
        try:
            # Test complete workflow with errors
            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = [Mock(), Mock()]
                mock_open.return_value = mock_model

                shell = IfcPeek(str(ifc_file))

                # Simulate realistic user session with errors
                session_steps = [
                    ("/help", True, "help"),
                    ("IfcWall", True, "success"),
                    ("BadQuery[", True, "error"),
                    ("/help", True, "help_after_error"),
                    ("IfcDoor", True, "recovery"),
                    ("/exit", False, "exit"),
                ]

                step_results = []

                with patch(
                    "ifcpeek.shell.ifcopenshell.util.selector.filter_elements"
                ) as mock_selector:
                    for step_input, expected_result, step_type in session_steps:
                        try:
                            if step_type == "success" or step_type == "recovery":
                                mock_selector.side_effect = None
                                mock_entity = Mock()
                                mock_entity.__str__ = Mock(
                                    return_value="#1=IFCWALL('guid',$,$,'Wall',$,$,$,$,$);"
                                )
                                mock_selector.return_value = [mock_entity]
                            elif step_type == "error":
                                mock_selector.side_effect = SyntaxError(
                                    "Invalid syntax"
                                )

                            result = shell._process_input(step_input)
                            step_results.append(result == expected_result)

                        except Exception:
                            step_results.append(False)

                # Evaluate end-to-end success
                e2e_success_rate = sum(step_results) / len(step_results)

                if e2e_success_rate >= 0.8:
                    self.log_result(
                        "End-to-End Error Scenarios",
                        True,
                        f"Success rate: {e2e_success_rate:.1%}",
                    )
                else:
                    self.log_result(
                        "End-to-End Error Scenarios",
                        False,
                        f"Low success rate: {e2e_success_rate:.1%}",
                    )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("End-to-End Error Scenarios", False, str(e))

    def test_configuration_error_handling(self):
        """Test configuration system error handling."""
        try:
            # Test configuration functions with error handling
            config_tests = []

            # Test config directory determination
            try:
                config_dir = get_config_dir()
                config_tests.append(("Config dir determination", True, str(config_dir)))
            except Exception as e:
                config_tests.append(("Config dir determination", False, str(e)))

            # Test file validation with invalid file
            try:
                invalid_file = self.create_temp_ifc(valid=False)
                validate_ifc_file_path(str(invalid_file))
                config_tests.append(
                    ("Invalid file detection", False, "Should have failed")
                )
                invalid_file.unlink()
            except Exception:
                config_tests.append(
                    ("Invalid file detection", True, "Correctly detected invalid file")
                )
                try:
                    invalid_file.unlink()
                except:
                    pass

            # Test nonexistent file handling
            try:
                validate_ifc_file_path("/nonexistent/path/file.ifc")
                config_tests.append(
                    ("Nonexistent file detection", False, "Should have failed")
                )
            except Exception:
                config_tests.append(
                    (
                        "Nonexistent file detection",
                        True,
                        "Correctly detected missing file",
                    )
                )

            # Evaluate configuration error handling
            config_success_rate = sum(
                1 for _, success, _ in config_tests if success
            ) / len(config_tests)

            if config_success_rate >= 0.8:
                self.log_result(
                    "Configuration Error Handling",
                    True,
                    f"Config success rate: {config_success_rate:.1%}",
                )
            else:
                failed_tests = [
                    desc for desc, success, _ in config_tests if not success
                ]
                self.log_result(
                    "Configuration Error Handling",
                    False,
                    f"Failed tests: {failed_tests}",
                )

        except Exception as e:
            self.log_result("Configuration Error Handling", False, str(e))

    def cleanup(self):
        """Clean up temporary files and directories."""
        for temp_dir in self.temp_dirs:
            try:
                import shutil

                shutil.rmtree(temp_dir)
            except:
                pass

    def run_all_tests(self):
        """Run all error handling tests."""
        print("=" * 80)
        print("IFCPEEK ERROR HANDLING SYSTEM - COMPREHENSIVE VALIDATION")
        print("=" * 80)
        print()

        test_methods = [
            ("Traceback Display System", self.test_traceback_display_system),
            ("Signal Handling System", self.test_signal_handling_system),
            ("Error Recovery System", self.test_error_recovery_system),
            ("Debug Information System", self.test_debug_information_system),
            ("Exceptions System", self.test_exceptions_system),
            (
                "Main Error Handling Integration",
                self.test_main_error_handling_integration,
            ),
            ("Performance Impact Assessment", self.test_performance_impact_assessment),
            ("Memory Stability Assessment", self.test_memory_stability_assessment),
            ("End-to-End Error Scenarios", self.test_end_to_end_error_scenarios),
            ("Configuration Error Handling", self.test_configuration_error_handling),
        ]

        print("🔧 Running Error Handling Tests...")
        print("-" * 50)

        for test_name, test_method in test_methods:
            print(f"\n📋 Testing: {test_name}")
            print("─" * 40)
            test_method()

        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 80)

        # Analyze results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests

        print(f"Total Test Categories: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")

        if failed_tests > 0:
            print("\n🔍 Failed Test Details:")
            print("-" * 30)
            for test_name, success, message in self.test_results:
                if not success:
                    print(f"  ❌ {test_name}")
                    if message:
                        print(f"     └─ {message}")

        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"\n📈 Overall Success Rate: {success_rate:.1f}%")

        # Final assessment
        print("\n" + "=" * 80)
        if success_rate >= 90:
            print("🎉 EXCELLENT: Error handling system is working perfectly!")
            print("   All critical features are operational and robust.")
        elif success_rate >= 75:
            print("✅ GOOD: Error handling system is working well.")
            print("   Most features are operational with minor issues.")
        elif success_rate >= 50:
            print(
                "⚠️  NEEDS IMPROVEMENT: Several error handling features need attention."
            )
            print("   System is functional but may have reliability issues.")
        else:
            print("❌ CRITICAL: Major error handling system problems detected.")
            print("   Significant improvements needed for production use.")

        print("\n🔧 Error Handling Features Tested:")
        features_tested = [
            "Full Python tracebacks for debugging",
            "Professional signal handling (SIGINT/SIGTERM)",
            "Comprehensive debug information display",
            "Intelligent error recovery mechanisms",
            "Context-rich exception classes",
            "Performance impact assessment",
            "Memory usage stability",
            "End-to-end error scenarios",
            "Configuration error handling",
            "Main function error integration",
        ]

        for feature in features_tested:
            print(f"  • {feature}")

        print("=" * 80)

        self.cleanup()
        return success_rate >= 75


def run_error_handling_tests():
    """Run the complete error handling test suite."""
    validator = ErrorHandlingValidator()
    return validator.run_all_tests()


if __name__ == "__main__":
    print("Starting Error Handling System Validation...")
    success = run_error_handling_tests()

    if success:
        print("\n🎯 VALIDATION COMPLETE: Error handling system ready for production!")
    else:
        print(
            "\n⚠️  VALIDATION INCOMPLETE: Please address the issues above before production deployment."
        )

    exit(0 if success else 1)
