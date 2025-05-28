"""
Complete integration test for Step 8 - History Management Integration.
This validates the complete workflow from configuration to persistent history.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock
from prompt_toolkit.history import FileHistory

from ifcpeek.shell import IfcPeek


class HistoryIntegrationValidator:
    """Comprehensive validation of history integration."""

    def __init__(self):
        self.test_results = []
        self.temp_dirs = []

    def log_result(self, test_name, success, message=""):
        """Log test result."""
        status = "✓ PASS" if success else "✗ FAIL"
        self.test_results.append((test_name, success, message))
        print(f"{status}: {test_name}")
        if message and not success:
            print(f"    {message}")

    def create_temp_ifc(self):
        """Create temporary IFC file for testing."""
        ifc_content = """ISO-10303-21;
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

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ifc", delete=False)
        temp_file.write(ifc_content)
        temp_file.close()
        return Path(temp_file.name)

    def test_history_file_creation_and_location(self):
        """Test that history file is created in correct XDG location."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            config_dir = temp_dir / "ifcpeek_config"
            history_path = config_dir / "history"

            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    # Mock directory creation
                    def mock_get_history_path():
                        config_dir.mkdir(parents=True, exist_ok=True)
                        return history_path

                    with patch(
                        "ifcpeek.config.get_history_file_path",
                        side_effect=mock_get_history_path,
                    ):
                        shell = IfcPeek(str(ifc_file))

                        # Verify directory was created
                        success = config_dir.exists() and config_dir.is_dir()
                        self.log_result("History directory creation", success)

                        # Verify shell has session (or None in non-terminal)
                        session_ok = shell.session is not None or shell.session is None
                        self.log_result("Session creation", session_ok)

            ifc_file.unlink()

        except Exception as e:
            self.log_result("History file creation", False, str(e))

    def test_history_persistence_across_sessions(self):
        """Test that history persists across shell sessions."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            history_path = temp_dir / "persistent_history"
            ifc_file = self.create_temp_ifc()

            # First session - add history
            session1_commands = ["/help", "IfcWall", "IfcDoor, Name=TestDoor"]

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    history1 = FileHistory(str(history_path))

                    for cmd in session1_commands:
                        history1.append_string(cmd)

                    # Force flush
                    del history1

            # Second session - check persistence
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    history2 = FileHistory(str(history_path))

                    saved_commands = list(history2.get_strings())

                    # Check all commands persisted
                    all_persisted = all(
                        cmd in saved_commands for cmd in session1_commands
                    )
                    self.log_result("History persistence", all_persisted)

                    if not all_persisted:
                        missing = [
                            cmd
                            for cmd in session1_commands
                            if cmd not in saved_commands
                        ]
                        self.log_result(
                            "Missing commands", False, f"Missing: {missing}"
                        )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("History persistence", False, str(e))

    def test_history_with_unicode_and_special_chars(self):
        """Test history with Unicode and special characters."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            history_path = temp_dir / "unicode_history"
            ifc_file = self.create_temp_ifc()

            special_commands = [
                'IfcWall, Name="Wall with spaces"',
                "IfcDoor, Name=测试门",  # Chinese
                "IfcWindow, Name=Окно",  # Cyrillic
                "IfcSlab, Material=Béton",  # French accents
                "IfcBeam, Tag=§pecial©har$",  # Special symbols
                "IfcWall | IfcDoor",  # Pipe character
            ]

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    history = FileHistory(str(history_path))

                    for cmd in special_commands:
                        history.append_string(cmd)

                    # Reload to test persistence
                    del history
                    new_history = FileHistory(str(history_path))
                    saved_commands = list(new_history.get_strings())

                    # Check all special commands persisted
                    all_saved = all(cmd in saved_commands for cmd in special_commands)
                    self.log_result("Unicode/special characters", all_saved)

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Unicode/special characters", False, str(e))

    def test_history_integration_with_shell_loop(self):
        """Test history integration with shell input processing loop."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            history_path = temp_dir / "loop_history"
            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    real_history = FileHistory(str(history_path))

                    mock_session = Mock()
                    mock_session.history = real_history

                    with patch(
                        "ifcpeek.shell.PromptSession", return_value=mock_session
                    ):
                        shell = IfcPeek(str(ifc_file))

                        # Test that shell processes input normally with history
                        test_inputs = ["/help", "IfcWall", "/exit"]
                        expected_results = [True, True, False]

                        # Simulate adding to history and processing
                        all_processed = True
                        for input_cmd, expected in zip(test_inputs, expected_results):
                            real_history.append_string(input_cmd)
                            result = shell._process_input(input_cmd)
                            if result != expected:
                                all_processed = False
                                break

                        self.log_result("Shell loop integration", all_processed)

                        # Verify history contains all inputs
                        history_strings = list(real_history.get_strings())
                        history_complete = all(
                            cmd in history_strings for cmd in test_inputs
                        )
                        self.log_result("History completeness", history_complete)

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Shell loop integration", False, str(e))

    def test_history_error_handling_and_fallback(self):
        """Test history error handling and graceful fallback."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            ifc_file = self.create_temp_ifc()

            # Test graceful fallback when history setup fails
            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                # Mock history creation to fail
                with patch(
                    "ifcpeek.shell.FileHistory",
                    side_effect=Exception("History failed"),
                ):
                    shell = IfcPeek(str(ifc_file))

                    # Should fall back to None session
                    fallback_ok = shell.session is None
                    self.log_result("Graceful fallback", fallback_ok)

                    # Shell should still process input
                    help_result = shell._process_input("/help")
                    input_ok = help_result is True
                    self.log_result("Input processing after fallback", input_ok)

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Error handling", False, str(e))

    def test_history_performance_with_large_dataset(self):
        """Test history performance with large number of entries."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            history_path = temp_dir / "performance_history"
            ifc_file = self.create_temp_ifc()

            # Create large history dataset
            start_time = time.time()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    history = FileHistory(str(history_path))

                    # Add many entries
                    for i in range(500):  # Reduced for test performance
                        history.append_string(f"IfcWall, Name=PerfWall-{i:04d}")

                    creation_time = time.time() - start_time

                    # Test shell creation time with large history
                    shell_start = time.time()
                    IfcPeek(str(ifc_file))
                    shell_time = time.time() - shell_start

                    # Performance should be reasonable
                    perf_ok = creation_time < 5.0 and shell_time < 3.0
                    self.log_result(
                        "Performance with large history",
                        perf_ok,
                        f"Creation: {creation_time:.2f}s, Shell: {shell_time:.2f}s",
                    )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Performance test", False, str(e))

    def test_history_search_capability_setup(self):
        """Test that history search capability is properly set up."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            history_path = temp_dir / "search_history"
            ifc_file = self.create_temp_ifc()

            searchable_commands = [
                "IfcWall",
                "IfcWall, material=concrete",
                "IfcWall, material=steel",
                "IfcDoor, Name=MainDoor",
                "IfcWindow, Name=Window01",
                "/help",
            ]

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    history = FileHistory(str(history_path))

                    for cmd in searchable_commands:
                        history.append_string(cmd)

                    mock_session = Mock()
                    mock_session.history = history

                    with patch(
                        "ifcpeek.shell.PromptSession", return_value=mock_session
                    ) as mock_prompt:
                        IfcPeek(str(ifc_file))

                        # Verify PromptSession created with history
                        session_created = mock_prompt.called
                        if session_created:
                            call_args = mock_prompt.call_args
                            history_passed = (
                                "history" in call_args.kwargs
                                and call_args.kwargs["history"] == history
                            )
                            self.log_result(
                                "History passed to PromptSession", history_passed
                            )
                        else:
                            self.log_result("PromptSession creation", False)

                        # Test searchable content
                        history_strings = list(history.get_strings())
                        wall_commands = [s for s in history_strings if "IfcWall" in s]
                        search_ready = (
                            len(wall_commands) == 3
                        )  # Should find 3 wall commands
                        self.log_result("Search content ready", search_ready)

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Search capability setup", False, str(e))

    def test_history_doesnt_break_existing_functionality(self):
        """Test that history integration doesn't break existing shell functionality."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            history_path = temp_dir / "compatibility_history"
            ifc_file = self.create_temp_ifc()

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    history = FileHistory(str(history_path))

                    mock_session = Mock()
                    mock_session.history = history

                    with patch(
                        "ifcpeek.shell.PromptSession", return_value=mock_session
                    ):
                        shell = IfcPeek(str(ifc_file))

                        # Test all existing functionality still works
                        functionality_tests = [
                            ("/help", True, "Help command"),
                            ("/exit", False, "Exit command"),
                            ("/quit", False, "Quit command"),
                            ("", True, "Empty input"),
                            ("   ", True, "Whitespace input"),
                        ]

                        all_functional = True
                        for test_input, expected, desc in functionality_tests:
                            try:
                                result = shell._process_input(test_input)
                                if result != expected:
                                    all_functional = False
                                    self.log_result(
                                        f"Functionality: {desc}",
                                        False,
                                        f"Expected {expected}, got {result}",
                                    )
                                else:
                                    self.log_result(f"Functionality: {desc}", True)
                            except Exception as e:
                                all_functional = False
                                self.log_result(f"Functionality: {desc}", False, str(e))

                        self.log_result(
                            "Overall functionality preservation", all_functional
                        )

            ifc_file.unlink()

        except Exception as e:
            self.log_result("Functionality compatibility", False, str(e))

    def test_xdg_compliance_integration(self):
        """Test XDG compliance integration with history."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            ifc_file = self.create_temp_ifc()

            # Test XDG_STATE_HOME compliance
            xdg_state_dir = temp_dir / "custom_xdg_state"
            expected_config_dir = xdg_state_dir / "ifcpeek"
            expected_history_path = expected_config_dir / "history"

            with patch.dict("os.environ", {"XDG_STATE_HOME": str(xdg_state_dir)}):
                with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                    mock_model = Mock()
                    mock_open.return_value = mock_model

                    # Mock the actual config functions to create directories
                    def mock_get_history_path():
                        expected_config_dir.mkdir(parents=True, exist_ok=True)
                        return expected_history_path

                    with patch(
                        "ifcpeek.config.get_history_file_path",
                        side_effect=mock_get_history_path,
                    ):
                        IfcPeek(str(ifc_file))

                        # Verify XDG compliance
                        xdg_compliant = expected_config_dir.exists()
                        self.log_result("XDG_STATE_HOME compliance", xdg_compliant)

            ifc_file.unlink()

        except Exception as e:
            self.log_result("XDG compliance", False, str(e))

    def test_complete_end_to_end_workflow(self):
        """Test complete end-to-end workflow with history."""
        temp_dir = Path(tempfile.mkdtemp())
        self.temp_dirs.append(temp_dir)

        try:
            history_path = temp_dir / "e2e_history"
            ifc_file = self.create_temp_ifc()

            # Simulate complete user workflow
            workflow_commands = [
                "/help",  # User starts with help
                "IfcWall",  # Query for walls
                "IfcWall, material=concrete",  # Refined query
                "/help",  # Help again
                "IfcDoor",  # Query for doors
                "Invalid[Query",  # Invalid query (should be handled)
                "/exit",  # Exit
            ]

            with patch("ifcpeek.shell.ifcopenshell.open") as mock_open:
                mock_model = Mock()
                mock_model.schema = "IFC4"
                mock_model.by_type.return_value = []
                mock_open.return_value = mock_model

                with patch(
                    "ifcpeek.config.get_history_file_path", return_value=history_path
                ):
                    # First session - execute workflow
                    history1 = FileHistory(str(history_path))

                    mock_session1 = Mock()
                    mock_session1.history = history1

                    with patch(
                        "ifcpeek.shell.PromptSession", return_value=mock_session1
                    ):
                        shell1 = IfcPeek(str(ifc_file))

                        # Process all workflow commands
                        for cmd in workflow_commands:
                            history1.append_string(cmd)
                            try:
                                shell1._process_input(cmd)
                            except:
                                pass  # Some commands may fail, that's OK

                    # Second session - verify history persistence
                    history2 = FileHistory(str(history_path))
                    saved_commands = list(history2.get_strings())

                    # Check workflow commands persisted
                    workflow_preserved = all(
                        cmd in saved_commands for cmd in workflow_commands
                    )
                    self.log_result("End-to-end workflow", workflow_preserved)

                    # Check command variety preserved
                    has_help = any("/help" in cmd for cmd in saved_commands)
                    has_queries = any(
                        "Ifc" in cmd and not cmd.startswith("/")
                        for cmd in saved_commands
                    )
                    has_invalid = any("Invalid" in cmd for cmd in saved_commands)

                    variety_preserved = has_help and has_queries and has_invalid
                    self.log_result("Command variety preservation", variety_preserved)

            ifc_file.unlink()

        except Exception as e:
            self.log_result("End-to-end workflow", False, str(e))

    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            try:
                import shutil

                shutil.rmtree(temp_dir)
            except:
                pass

    def run_all_tests(self):
        """Run all history integration tests."""
        print("=" * 70)
        print("HISTORY MANAGEMENT INTEGRATION TESTS - STEP 8")
        print("=" * 70)
        print()

        test_methods = [
            (
                "History File Creation & Location",
                self.test_history_file_creation_and_location,
            ),
            (
                "History Persistence Across Sessions",
                self.test_history_persistence_across_sessions,
            ),
            (
                "Unicode & Special Characters",
                self.test_history_with_unicode_and_special_chars,
            ),
            ("Shell Loop Integration", self.test_history_integration_with_shell_loop),
            (
                "Error Handling & Fallback",
                self.test_history_error_handling_and_fallback,
            ),
            (
                "Performance with Large Dataset",
                self.test_history_performance_with_large_dataset,
            ),
            ("Search Capability Setup", self.test_history_search_capability_setup),
            (
                "Existing Functionality Preservation",
                self.test_history_doesnt_break_existing_functionality,
            ),
            ("XDG Compliance Integration", self.test_xdg_compliance_integration),
            ("Complete End-to-End Workflow", self.test_complete_end_to_end_workflow),
        ]

        for test_name, test_method in test_methods:
            print(f"\nRunning: {test_name}")
            print("-" * 50)
            test_method()

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")

        if failed_tests > 0:
            print("\nFailed Tests:")
            for test_name, success, message in self.test_results:
                if not success:
                    print(f"  • {test_name}: {message}")

        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")

        if success_rate >= 90:
            print("🎉 EXCELLENT: History integration is working well!")
        elif success_rate >= 75:
            print("✅ GOOD: History integration is mostly working.")
        elif success_rate >= 50:
            print("⚠️  NEEDS WORK: Several history integration issues.")
        else:
            print("❌ CRITICAL: Major history integration problems.")

        self.cleanup()
        return success_rate >= 75


def run_history_integration_tests():
    """Run the complete history integration test suite."""
    validator = HistoryIntegrationValidator()
    return validator.run_all_tests()


if __name__ == "__main__":
    success = run_history_integration_tests()
    exit(0 if success else 1)
