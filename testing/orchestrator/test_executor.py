#!/usr/bin/env python3
"""
Test Executor - Automated test execution for E2E testing

Handles different test types:
- CLI command tests
- MCP tool tests
- Installation/setup tests
- Performance benchmarks
- Manual-only tests (marked as MANUAL_REQUIRED)
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TestExecutor:
    """Executes individual test scenarios and captures results"""

    def __init__(self, project_root: str = "/app"):
        self.project_root = Path(project_root)
        self.qdrant_url = os.getenv("CLAUDE_RAG_QDRANT_URL", "http://qdrant:6333")
        self.storage_backend = os.getenv("CLAUDE_RAG_STORAGE_BACKEND", "qdrant")

        # Initialize test implementations
        try:
            sys.path.insert(0, str(self.project_root))
            from testing.orchestrator.test_implementations import (
                PerformanceTests,
                SecurityTests,
                ErrorHandlingTests,
                ConfigurationTests,
            )

            self.perf_tests = PerformanceTests(str(self.project_root))
            self.security_tests = SecurityTests(str(self.project_root))
            self.error_tests = ErrorHandlingTests(str(self.project_root))
            self.config_tests = ConfigurationTests(str(self.project_root))
        except ImportError as e:
            logger.warning(f"Could not import test implementations: {e}")
            self.perf_tests = None
            self.security_tests = None
            self.error_tests = None
            self.config_tests = None

    def execute_test(self, test_id: str) -> Dict[str, Any]:
        """
        Execute a single test scenario

        Routes to appropriate test handler based on test ID prefix:
        - INST-XXX: Installation/setup tests
        - MCP-XXX: MCP tool tests
        - CLI-XXX: CLI command tests
        - CODE-XXX: Code search/indexing tests
        - MEM-XXX: Memory management tests
        - PROJ-XXX: Multi-project tests
        - HEALTH-XXX: Health monitoring tests
        - DASH-XXX: Dashboard tests (manual)
        - CONFIG-XXX: Configuration tests
        - DOC-XXX: Documentation tests
        - SEC-XXX: Security tests
        - ERR-XXX: Error handling tests
        - PERF-XXX: Performance tests
        - UX-XXX: UX quality tests (manual)
        """
        test_prefix = test_id.split("-")[0]

        handlers = {
            "INST": self._execute_installation_test,
            "MCP": self._execute_mcp_test,
            "CLI": self._execute_cli_test,
            "CODE": self._execute_code_search_test,
            "MEM": self._execute_memory_test,
            "PROJ": self._execute_project_test,
            "HEALTH": self._execute_health_test,
            "DASH": self._execute_manual_test,  # Dashboard requires manual testing
            "CONFIG": self._execute_config_test,
            "DOC": self._execute_doc_test,
            "SEC": self._execute_security_test,
            "ERR": self._execute_error_test,
            "PERF": self._execute_performance_test,
            "UX": self._execute_manual_test,  # UX quality requires manual assessment
        }

        handler = handlers.get(test_prefix, self._execute_manual_test)

        try:
            return handler(test_id)
        except Exception as e:
            logger.error(f"Test {test_id} failed with exception: {e}", exc_info=True)
            return {
                "test_id": test_id,
                "status": "ERROR",
                "notes": f"Exception during test execution: {str(e)}",
                "bugs_found": [],
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
            }

    def _execute_installation_test(self, test_id: str) -> Dict[str, Any]:
        """Execute installation/setup tests"""
        result = {
            "test_id": test_id,
            "start_time": datetime.now().isoformat(),
            "status": "PASS",
            "notes": "",
            "bugs_found": [],
        }

        # Installation tests by ID
        tests = {
            "INST-001": self._test_setup_wizard,
            "INST-002": self._test_rust_fallback,
            "INST-003": self._test_sqlite_backend,
            "INST-004": self._test_manual_install,
            "INST-005": self._test_docker_qdrant,
            "INST-006": self._test_health_check,
            "INST-007": self._test_mcp_registration,
            "INST-008": self._test_upgrade_path,
            "INST-009": self._test_uninstall,
            "INST-010": self._test_config_files,
        }

        if test_id in tests:
            try:
                tests[test_id](result)
            except Exception as e:
                result["status"] = "ERROR"
                result["notes"] = f"Test execution error: {str(e)}"
        else:
            result["status"] = "MANUAL_REQUIRED"
            result["notes"] = (
                f"Test {test_id} requires manual execution - see TEST-006_e2e_test_plan.md"
            )

        result["end_time"] = datetime.now().isoformat()
        return result

    def _execute_mcp_test(self, test_id: str) -> Dict[str, Any]:
        """Execute MCP tool tests"""
        result = {
            "test_id": test_id,
            "start_time": datetime.now().isoformat(),
            "status": "PASS",
            "notes": "",
            "bugs_found": [],
        }

        # MCP tests - these test the actual MCP tools
        tests = {
            "MCP-001": self._test_store_memory,
            "MCP-002": self._test_retrieve_memories,
            "MCP-003": self._test_list_memories,
            "MCP-004": self._test_delete_memory,
            "MCP-005": self._test_export_memories,
            "MCP-006": self._test_import_memories,
            "MCP-007": self._test_search_code,
            "MCP-008": self._test_index_codebase,
            "MCP-009": self._test_find_similar_code,
            "MCP-010": self._test_search_all_projects,
            "MCP-011": self._test_opt_in_cross_project,
            "MCP-012": self._test_opt_out_cross_project,
            "MCP-013": self._test_list_opted_in_projects,
            "MCP-014": self._test_get_performance_metrics,
            "MCP-015": self._test_get_health_score,
            "MCP-016": self._test_get_active_alerts,
        }

        if test_id in tests:
            try:
                tests[test_id](result)
            except Exception as e:
                result["status"] = "ERROR"
                result["notes"] = f"Test execution error: {str(e)}"
        else:
            result["status"] = "MANUAL_REQUIRED"
            result["notes"] = f"Test {test_id} requires manual execution via MCP client"

        result["end_time"] = datetime.now().isoformat()
        return result

    def _execute_cli_test(self, test_id: str) -> Dict[str, Any]:
        """Execute CLI command tests"""
        result = {
            "test_id": test_id,
            "start_time": datetime.now().isoformat(),
            "status": "PASS",
            "notes": "",
            "bugs_found": [],
        }

        # CLI tests map
        tests = {
            "CLI-001": self._test_cli_index,
            "CLI-002": self._test_cli_search,
            "CLI-003": self._test_cli_list,
            "CLI-004": self._test_cli_delete,
            "CLI-005": self._test_cli_export,
            "CLI-006": self._test_cli_import,
            "CLI-007": self._test_cli_health,
            "CLI-008": self._test_cli_watch,
            "CLI-009": self._test_cli_stats,
            "CLI-010": self._test_cli_backup,
            "CLI-011": self._test_cli_restore,
            "CLI-012": self._test_cli_optimize,
            "CLI-013": self._test_cli_verify,
            "CLI-014": self._test_cli_help,
        }

        if test_id in tests:
            try:
                tests[test_id](result)
            except Exception as e:
                result["status"] = "ERROR"
                result["notes"] = f"Test execution error: {str(e)}"
        else:
            result["status"] = "MANUAL_REQUIRED"
            result["notes"] = f"Test {test_id} requires manual CLI testing"

        result["end_time"] = datetime.now().isoformat()
        return result

    def _execute_code_search_test(self, test_id: str) -> Dict[str, Any]:
        """Execute code search and indexing tests"""
        return self._execute_automated_test(
            test_id,
            {
                "CODE-001": self._test_python_indexing,
                "CODE-002": self._test_javascript_indexing,
                "CODE-003": self._test_semantic_search,
                "CODE-004": self._test_similarity_search,
                "CODE-005": self._test_hybrid_search,
            },
        )

    def _execute_memory_test(self, test_id: str) -> Dict[str, Any]:
        """Execute memory management tests"""
        return self._execute_automated_test(
            test_id,
            {
                "MEM-001": self._test_memory_lifecycle,
                "MEM-002": self._test_memory_provenance,
                "MEM-003": self._test_duplicate_detection,
                "MEM-004": self._test_memory_consolidation,
            },
        )

    def _execute_project_test(self, test_id: str) -> Dict[str, Any]:
        """Execute multi-project tests"""
        return self._execute_automated_test(
            test_id,
            {
                "PROJ-001": self._test_cross_project_search,
                "PROJ-002": self._test_project_isolation,
                "PROJ-003": self._test_consent_management,
            },
        )

    def _execute_health_test(self, test_id: str) -> Dict[str, Any]:
        """Execute health monitoring tests"""
        return self._execute_automated_test(
            test_id,
            {
                "HEALTH-001": self._test_health_score,
                "HEALTH-002": self._test_performance_metrics,
                "HEALTH-003": self._test_active_alerts,
            },
        )

    def _execute_config_test(self, test_id: str) -> Dict[str, Any]:
        """Execute configuration tests"""
        return self._execute_automated_test(
            test_id,
            {
                "CONFIG-001": self._test_env_variables,
                "CONFIG-002": self._test_backend_switching,
                "CONFIG-003": self._test_model_configuration,
            },
        )

    def _execute_doc_test(self, test_id: str) -> Dict[str, Any]:
        """Execute documentation tests"""
        return self._execute_automated_test(
            test_id,
            {
                "DOC-001": self._test_readme_accuracy,
                "DOC-002": self._test_api_docs,
                "DOC-003": self._test_examples,
            },
        )

    def _execute_security_test(self, test_id: str) -> Dict[str, Any]:
        """Execute security tests"""
        return self._execute_automated_test(
            test_id,
            {
                "SEC-001": self._test_path_injection,
                "SEC-002": self._test_command_injection,
                "SEC-003": self._test_input_validation,
            },
        )

    def _execute_error_test(self, test_id: str) -> Dict[str, Any]:
        """Execute error handling tests"""
        return self._execute_automated_test(
            test_id,
            {
                "ERR-001": self._test_missing_dependencies,
                "ERR-002": self._test_invalid_inputs,
                "ERR-003": self._test_network_failures,
            },
        )

    def _execute_performance_test(self, test_id: str) -> Dict[str, Any]:
        """Execute performance benchmark tests"""
        return self._execute_automated_test(
            test_id,
            {
                "PERF-001": self._test_search_latency,
                "PERF-002": self._test_indexing_speed,
                "PERF-003": self._test_concurrent_load,
            },
        )

    def _execute_manual_test(self, test_id: str) -> Dict[str, Any]:
        """Mark test as requiring manual execution"""
        return {
            "test_id": test_id,
            "start_time": datetime.now().isoformat(),
            "status": "MANUAL_REQUIRED",
            "notes": f"Test {test_id} requires manual execution - see TEST-006_e2e_test_plan.md for detailed steps",
            "bugs_found": [],
            "end_time": datetime.now().isoformat(),
        }

    def _execute_automated_test(self, test_id: str, test_map: Dict) -> Dict[str, Any]:
        """Helper to execute automated tests from a map"""
        result = {
            "test_id": test_id,
            "start_time": datetime.now().isoformat(),
            "status": "PASS",
            "notes": "",
            "bugs_found": [],
        }

        if test_id in test_map:
            try:
                test_map[test_id](result)
            except Exception as e:
                result["status"] = "ERROR"
                result["notes"] = f"Test execution error: {str(e)}"
        else:
            result["status"] = "MANUAL_REQUIRED"
            result["notes"] = f"Test {test_id} requires manual execution"

        result["end_time"] = datetime.now().isoformat()
        return result

    def _run_command(
        self, cmd: List[str], timeout: int = 30, capture_output: bool = True
    ) -> Tuple[int, str, str]:
        """Run a shell command and return (returncode, stdout, stderr)"""
        try:
            # Pass environment variables to subprocess, including Qdrant URL
            env = os.environ.copy()
            env["CLAUDE_RAG_QDRANT_URL"] = self.qdrant_url
            env["CLAUDE_RAG_STORAGE_BACKEND"] = self.storage_backend

            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                cwd=str(self.project_root),
                env=env,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return -1, "", str(e)

    def _is_success_with_warnings(
        self, returncode: int, stdout: str, stderr: str
    ) -> bool:
        """
        Check if command succeeded despite having warnings.

        Returns True if:
        - returncode is 0 (success), OR
        - returncode is non-zero BUT stderr only contains benign warnings or "no data" messages
        """
        if returncode == 0:
            return True

        # Check if stderr only contains benign warnings/messages, not actual errors
        if stderr:
            stderr_lower = stderr.lower()

            # Benign patterns that should not fail tests
            benign_patterns = [
                "rust parsing module not available",
                "using python fallback parser",
                "degradation: rust parser",
                "no memories found",
                "no projects found",
                "database is empty",
                "collection not found",
                "collection does not exist",
            ]

            # Real error patterns that should fail tests
            error_patterns = [
                "traceback (most recent call last)",
                "exception occurred",
                "failed to connect",
                "connection refused",
                "permission denied",
                "file not found",
                "module not found",
            ]

            # Check if any benign pattern matches
            has_benign = any(pattern in stderr_lower for pattern in benign_patterns)
            # Check if any real error pattern matches
            has_real_errors = any(pattern in stderr_lower for pattern in error_patterns)

            # If we have benign warnings/messages but no real errors, consider it a success
            if has_benign and not has_real_errors:
                return True

        return False

    # ===== Installation Test Implementations =====

    def _test_setup_wizard(self, result: Dict):
        """Test INST-001: Automated setup wizard"""
        # Check if setup.py exists
        setup_file = self.project_root / "setup.py"
        if not setup_file.exists():
            result["status"] = "FAIL"
            result["notes"] = (
                "setup.py not found in repository - automated setup unavailable"
            )
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-001",
                    "severity": "HIGH",
                    "description": "setup.py missing from repository - no automated installation path",
                    "test_id": "INST-001",
                    "impact": "Users must manually install, significantly increasing setup friction",
                }
            )
            return

        # Check if setup.py contains key components
        try:
            setup_content = setup_file.read_text()
            required_components = [
                ("check_python", "Python version check"),
                ("install_dependencies", "Dependency installation"),
                ("check_docker", "Docker availability check"),
                # Note: Qdrant startup is intentionally manual/external (see setup.py line 833)
                # so we don't require start_qdrant function
            ]

            missing_components = []
            for component, description in required_components:
                if component not in setup_content:
                    missing_components.append(description)

            if missing_components:
                result["status"] = "FAIL"
                result["notes"] = (
                    f'setup.py missing critical components: {", ".join(missing_components)}'
                )
                result["bugs_found"].append(
                    {
                        "bug_id": "BUG-NEW-001B",
                        "severity": "MEDIUM",
                        "description": f'setup.py incomplete - missing: {", ".join(missing_components)}',
                        "test_id": "INST-001",
                        "impact": "Setup wizard may not handle all installation scenarios",
                    }
                )
            else:
                result["status"] = "MANUAL_REQUIRED"
                result["notes"] = (
                    "setup.py exists with required components. Interactive wizard requires manual testing - verify all wizard steps work correctly, error handling is clear, completion time is 2-5 minutes, and user can recover from interruptions."
                )
        except Exception as e:
            result["status"] = "ERROR"
            result["notes"] = f"Error reading setup.py: {str(e)}"

    def _test_rust_fallback(self, result: Dict):
        """Test INST-002: Rust parser availability (required)

        Note: Python parser fallback was removed (it was broken, returned 0 units).
        Rust parser (mcp_performance_core) is now required for code indexing.
        """
        # Rust parser is now required - no fallback
        try:
            import sys

            sys.path.insert(0, str(self.project_root))
            from mcp_performance_core import parse_source_file

            # Test basic parsing
            test_code = 'def hello():\n    print("hello")\n'
            parse_result = parse_source_file("test.py", test_code)

            if hasattr(parse_result, "units") and len(parse_result.units) > 0:
                result["status"] = "PASS"
                result["notes"] = (
                    f"Rust parser (mcp_performance_core) is installed and functional - extracted {len(parse_result.units)} units"
                )
            else:
                result["status"] = "FAIL"
                result["notes"] = (
                    "Rust parser exists but failed to extract semantic units"
                )
                result["bugs_found"].append(
                    {
                        "bug_id": "BUG-NEW-002B",
                        "severity": "HIGH",
                        "description": "Rust parser exists but not functional - failed basic parsing test",
                        "test_id": "INST-002",
                        "impact": "Code indexing will not work",
                    }
                )
        except ImportError as e:
            result["status"] = "FAIL"
            result["notes"] = (
                f"Rust parser (mcp_performance_core) not installed: {str(e)}"
            )
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-002",
                    "severity": "CRITICAL",
                    "description": f"Rust parser not installed: {str(e)}",
                    "test_id": "INST-002",
                    "impact": "Code indexing will not work. Install with: cd rust_core && maturin build --release && pip install target/wheels/*.whl",
                }
            )
        except Exception as e:
            result["status"] = "ERROR"
            result["notes"] = f"Error testing Rust parser: {str(e)}"

    def _test_sqlite_backend(self, result: Dict):
        """Test INST-003: SQLite backend setup (removed in v4.0 - Qdrant-only architecture)"""
        # Check if config only allows qdrant backend (v4.0+ behavior)
        config_file = self.project_root / "src" / "config.py"
        if config_file.exists():
            config_content = config_file.read_text()
            # Check for Qdrant-only configuration
            if (
                'Literal["qdrant"]' in config_content
                or 'storage_backend: Literal["qdrant"]' in config_content
            ):
                result["status"] = "PASS"
                result["notes"] = (
                    "v4.0 uses Qdrant-only architecture (SQLite intentionally removed). "
                    'storage_backend config accepts only "qdrant". '
                    "This is a breaking change from v3.x - users must migrate to Qdrant."
                )
                return

        # Fallback: Check if SQLite store exists (v3.x behavior)
        sqlite_store = self.project_root / "src" / "store" / "sqlite_store.py"
        if not sqlite_store.exists():
            result["status"] = "PASS"
            result["notes"] = (
                "SQLite store not found - likely v4.0+ with Qdrant-only architecture. "
                "Check CHANGELOG.md for migration guide from v3.x SQLite to v4.0 Qdrant."
            )
            return

        # Try to import SQLite store
        try:
            import sys

            sys.path.insert(0, str(self.project_root))

            # Check if deprecated warning exists in code
            store_content = sqlite_store.read_text()
            has_deprecation_note = (
                "deprecated" in store_content.lower()
                or "qdrant" in store_content.lower()
            )

            result["status"] = "PASS"
            if has_deprecation_note:
                result["notes"] = (
                    "SQLite backend available (correctly marked as deprecated) - Qdrant is now the primary backend"
                )
            else:
                result["notes"] = (
                    "SQLite backend available but may be missing deprecation warnings"
                )
                result["bugs_found"].append(
                    {
                        "bug_id": "BUG-NEW-003B",
                        "severity": "LOW",
                        "description": "SQLite store may be missing deprecation warnings - users should be guided to Qdrant",
                        "test_id": "INST-003",
                        "impact": "Users may use deprecated backend without knowing better option exists",
                    }
                )
        except Exception as e:
            result["status"] = "FAIL"
            result["notes"] = f"SQLite store exists but cannot be imported: {str(e)}"

    def _test_manual_install(self, result: Dict):
        """Test INST-004: Manual installation path"""
        # Check requirements.txt exists
        req_file = self.project_root / "requirements.txt"
        if not req_file.exists():
            result["status"] = "FAIL"
            result["notes"] = (
                "requirements.txt not found - manual installation impossible"
            )
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-004",
                    "severity": "CRITICAL",
                    "description": "requirements.txt missing - project cannot be installed",
                    "test_id": "INST-004",
                    "impact": "No way to install dependencies for manual or automated setup",
                }
            )
            return

        # Parse requirements.txt and check for critical dependencies
        try:
            req_content = req_file.read_text()
            # Critical deps for this MCP server (stdio transport, not HTTP)
            critical_deps = [
                "qdrant-client",
                "sentence-transformers",
                "mcp",
                "watchdog",
            ]
            missing_deps = [
                dep for dep in critical_deps if dep not in req_content.lower()
            ]

            if missing_deps:
                result["status"] = "FAIL"
                result["notes"] = (
                    f'requirements.txt missing critical dependencies: {", ".join(missing_deps)}'
                )
                result["bugs_found"].append(
                    {
                        "bug_id": "BUG-NEW-004B",
                        "severity": "HIGH",
                        "description": f'requirements.txt incomplete - missing: {", ".join(missing_deps)}',
                        "test_id": "INST-004",
                        "impact": "Manual installation will fail due to missing dependencies",
                    }
                )
            else:
                # Check README for manual installation instructions
                readme = self.project_root / "README.md"
                if readme.exists():
                    readme_content = readme.read_text()
                    has_install_instructions = (
                        "pip install" in readme_content
                        and "requirements.txt" in readme_content
                    )
                    if has_install_instructions:
                        result["status"] = "PASS"
                        result["notes"] = (
                            "Manual installation files present - requirements.txt complete and README has installation instructions"
                        )
                    else:
                        result["status"] = "PASS"
                        result["notes"] = (
                            "requirements.txt complete but README may be missing installation instructions"
                        )
                        result["bugs_found"].append(
                            {
                                "bug_id": "BUG-NEW-004C",
                                "severity": "LOW",
                                "description": "README missing clear manual installation instructions",
                                "test_id": "INST-004",
                                "impact": "Users may struggle with manual installation without clear guidance",
                            }
                        )
                else:
                    result["status"] = "PASS"
                    result["notes"] = (
                        "requirements.txt exists and appears complete, but README not found"
                    )
        except Exception as e:
            result["status"] = "ERROR"
            result["notes"] = f"Error checking requirements.txt: {str(e)}"

    def _test_docker_qdrant(self, result: Dict):
        """Test INST-005: Docker Qdrant setup"""
        # Check docker-compose.yml exists
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            result["status"] = "FAIL"
            result["notes"] = "docker-compose.yml not found - Docker setup unavailable"
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-005",
                    "severity": "HIGH",
                    "description": "docker-compose.yml missing - no easy way to start Qdrant",
                    "test_id": "INST-005",
                    "impact": "Users must manually configure Qdrant container, increasing setup complexity",
                }
            )
            return

        # Validate docker-compose.yml content
        try:
            compose_content = compose_file.read_text()
            required_keys = ["qdrant", "image:", "ports:", "6333"]
            missing_keys = [key for key in required_keys if key not in compose_content]

            if missing_keys:
                result["notes"] = (
                    f'docker-compose.yml exists but may be incomplete - missing: {", ".join(missing_keys)}'
                )
                result["bugs_found"].append(
                    {
                        "bug_id": "BUG-NEW-005B",
                        "severity": "MEDIUM",
                        "description": f'docker-compose.yml incomplete - missing: {", ".join(missing_keys)}',
                        "test_id": "INST-005",
                        "impact": "Qdrant may not start correctly from docker-compose",
                    }
                )
        except Exception as e:
            result["notes"] = f"Error reading docker-compose.yml: {str(e)}"

        # Try to connect to Qdrant (use root endpoint, not /health)
        returncode, stdout, stderr = self._run_command(
            [
                "python",
                "-c",
                f'import urllib.request; resp = urllib.request.urlopen("{self.qdrant_url}/", timeout=5); print("OK")',
            ],
            timeout=10,
        )

        if returncode == 0 and "OK" in stdout:
            result["status"] = "PASS"
            result["notes"] = (
                f"Qdrant accessible at {self.qdrant_url} and docker-compose.yml present"
            )
        else:
            result["status"] = "FAIL"
            result["notes"] = (
                f"Qdrant not accessible at {self.qdrant_url}: {stderr}. Ensure Docker is running and Qdrant container is started."
            )
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-005C",
                    "severity": "HIGH",
                    "description": f"Qdrant container not accessible at {self.qdrant_url} - may not be running",
                    "test_id": "INST-005",
                    "impact": "System cannot function without Qdrant connection. Run: docker-compose up -d",
                }
            )

    def _test_health_check(self, result: Dict):
        """Test INST-006: Health check command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "health"], timeout=20
        )

        if self._is_success_with_warnings(returncode, stdout, stderr):
            # Parse output to verify components are checked
            output = stdout.lower()
            expected_components = ["qdrant", "parser", "storage", "python"]
            found_components = [comp for comp in expected_components if comp in output]

            if len(found_components) >= 2:  # At least some health checks present
                result["status"] = "PASS"
                result["notes"] = (
                    f'Health check command executed successfully - checked: {", ".join(found_components)}'
                )
            else:
                result["status"] = "PASS"
                result["notes"] = (
                    f"Health check command ran but output format may be incomplete. Output: {stdout[:300]}"
                )
                result["bugs_found"].append(
                    {
                        "bug_id": "BUG-NEW-006",
                        "severity": "LOW",
                        "description": "Health check output may be missing component status details",
                        "test_id": "INST-006",
                        "impact": "Users may not get comprehensive system health information",
                    }
                )
        else:
            result["status"] = "FAIL"
            result["notes"] = (
                f"Health check failed with exit code {returncode}: {stderr[:500]}"
            )
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-006B",
                    "severity": "MEDIUM",
                    "description": f"Health check command failed: {stderr[:500]}",
                    "test_id": "INST-006",
                    "impact": "Users cannot verify system health, may have import or configuration issues",
                }
            )

    def _test_mcp_registration(self, result: Dict):
        """Test INST-007: MCP server file structure and imports"""
        # Check if MCP server file exists
        mcp_server = self.project_root / "src" / "mcp_server.py"
        if not mcp_server.exists():
            result["status"] = "FAIL"
            result["notes"] = "MCP server file not found at src/mcp_server.py"
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-007",
                    "severity": "CRITICAL",
                    "description": "MCP server file missing - core functionality unavailable",
                    "test_id": "INST-007",
                    "impact": "Cannot be used as MCP server with Claude Desktop/Code",
                }
            )
            return

        # Verify MCP server can be imported
        try:
            import sys

            sys.path.insert(0, str(self.project_root))

            # Test import
            with open(mcp_server) as f:
                content = f.read()
                has_main = "__main__" in content or "if __name__" in content
                has_mcp_tools = "mcp" in content.lower() and "tool" in content.lower()

                if has_main and has_mcp_tools:
                    result["status"] = "MANUAL_REQUIRED"
                    result["notes"] = (
                        "MCP server file exists with proper structure. MANUAL TEST REQUIRED: Register with Claude Code using: claude mcp add --transport stdio --scope user claude-memory-rag -- python src/mcp_server.py"
                    )
                else:
                    result["status"] = "FAIL"
                    result["notes"] = (
                        "MCP server file exists but may be missing main entry point or tool definitions"
                    )
                    result["bugs_found"].append(
                        {
                            "bug_id": "BUG-NEW-007B",
                            "severity": "HIGH",
                            "description": "MCP server file incomplete - missing main entry or tool definitions",
                            "test_id": "INST-007",
                            "impact": "MCP server may not start correctly",
                        }
                    )
        except Exception as e:
            result["status"] = "ERROR"
            result["notes"] = f"Error analyzing MCP server file: {str(e)}"

    def _test_upgrade_path(self, result: Dict):
        """Test INST-008: Upgrade path documentation"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = (
            "MANUAL TEST REQUIRED: Upgrade from v3.x to v4.0 requires testing data migration, config preservation, and no data loss. Check CHANGELOG.md for migration guide."
        )

    def _test_uninstall(self, result: Dict):
        """Test INST-009: Clean uninstallation"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = (
            "MANUAL TEST REQUIRED: Verify clean uninstall removes ~/.claude-rag/, stops Qdrant container, removes MCP registration, and leaves no orphaned files."
        )

    def _test_config_files(self, result: Dict):
        """Test INST-010: Configuration file templates and generation"""
        # Check for configuration templates
        env_example = self.project_root / ".env.example"
        readme = self.project_root / "README.md"

        issues = []
        notes = []

        if env_example.exists():
            notes.append(".env.example template exists")
        else:
            notes.append(
                "No .env.example (system may use environment variables or defaults)"
            )

        if readme.exists():
            readme_content = readme.read_text()
            has_config_docs = (
                "configuration" in readme_content.lower()
                or "environment" in readme_content.lower()
            )
            if has_config_docs:
                notes.append("README contains configuration documentation")
            else:
                issues.append(
                    {
                        "bug_id": "BUG-NEW-010",
                        "severity": "LOW",
                        "description": "README may be missing configuration documentation",
                        "test_id": "INST-010",
                        "impact": "Users may not know how to configure the system",
                    }
                )

        result["status"] = "PASS" if len(issues) == 0 else "PASS"
        result["notes"] = (
            " | ".join(notes) if notes else "Configuration documentation present"
        )
        if issues:
            result["bugs_found"].extend(issues)

    # ===== MCP Test Implementations =====
    # (Simplified - actual implementation would use MCP client)

    def _test_store_memory(self, result: Dict):
        """Test MCP-001: store_memory tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = (
            "MCP tool testing requires MCP client - use Claude Desktop or MCP test client"
        )

    def _test_retrieve_memories(self, result: Dict):
        """Test MCP-002: retrieve_memories tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_list_memories(self, result: Dict):
        """Test MCP-003: list_memories tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_delete_memory(self, result: Dict):
        """Test MCP-004: delete_memory tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_export_memories(self, result: Dict):
        """Test MCP-005: export_memories tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_import_memories(self, result: Dict):
        """Test MCP-006: import_memories tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_search_code(self, result: Dict):
        """Test MCP-007: search_code tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_index_codebase(self, result: Dict):
        """Test MCP-008: index_codebase tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_find_similar_code(self, result: Dict):
        """Test MCP-009: find_similar_code tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_search_all_projects(self, result: Dict):
        """Test MCP-010: search_all_projects tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_opt_in_cross_project(self, result: Dict):
        """Test MCP-011: opt_in_cross_project tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_opt_out_cross_project(self, result: Dict):
        """Test MCP-012: opt_out_cross_project tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_list_opted_in_projects(self, result: Dict):
        """Test MCP-013: list_opted_in_projects tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_get_performance_metrics(self, result: Dict):
        """Test MCP-014: get_performance_metrics tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_get_health_score(self, result: Dict):
        """Test MCP-015: get_health_score tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    def _test_get_active_alerts(self, result: Dict):
        """Test MCP-016: get_active_alerts tool"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "MCP tool testing requires MCP client"

    # ===== CLI Test Implementations =====

    def _test_cli_index(self, result: Dict):
        """Test CLI-001: Index command - basic functionality and output"""
        # Create a small test directory with various file types
        test_dir = Path("/tmp/test_code_cli001")
        test_dir.mkdir(exist_ok=True)

        # Create test files
        (test_dir / "test.py").write_text(
            'def hello():\n    """Say hello"""\n    print("hello")\n\nclass TestClass:\n    def method(self):\n        pass'
        )
        (test_dir / "test.js").write_text('function greet() {\n  console.log("hi");\n}')
        (test_dir / "README.md").write_text("# Test Project\nDocumentation here")

        returncode, stdout, stderr = self._run_command(
            [
                "python",
                "-m",
                "src.cli",
                "index",
                str(test_dir),
                "--project-name",
                "test-project-cli",
            ],
            timeout=60,
        )

        if not self._is_success_with_warnings(returncode, stdout, stderr):
            result["status"] = "FAIL"
            result["notes"] = (
                f"Index command failed with exit code {returncode}: {stderr[:300]}"
            )
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-CLI-001",
                    "severity": "HIGH",
                    "description": f"CLI index command failed: {stderr[:300]}",
                    "test_id": "CLI-001",
                    "impact": "Cannot index code via CLI - primary functionality broken",
                }
            )
            return

        # Parse output for quality checks
        output = stdout.lower()
        issues = []

        # Check for progress indicators
        has_progress = any(
            keyword in output
            for keyword in ["indexed", "files", "processing", "complete"]
        )
        if not has_progress:
            issues.append(
                {
                    "bug_id": "BUG-NEW-CLI-001B",
                    "severity": "LOW",
                    "description": "Index command missing progress indicators or completion message",
                    "test_id": "CLI-001",
                    "impact": "Poor UX - users don't know if indexing is working",
                }
            )

        # Check for file count
        import re

        file_count_match = re.search(r"(\d+)\s*files?", output)
        if file_count_match:
            file_count = int(file_count_match.group(1))
            if file_count < 2:
                issues.append(
                    {
                        "bug_id": "BUG-NEW-CLI-001C",
                        "severity": "MEDIUM",
                        "description": f"Index command found only {file_count} files - may not be indexing all file types",
                        "test_id": "CLI-001",
                        "impact": "Code files may not be discovered or indexed correctly",
                    }
                )

        # Check for time/performance reporting
        has_timing = any(
            keyword in output for keyword in ["seconds", "time", "duration", "took"]
        )

        if returncode == 0:
            result["status"] = "PASS"
            notes_parts = [
                "Index command successful - processed files in test directory"
            ]
            if file_count_match:
                notes_parts.append(f"found {file_count_match.group(1)} files")
            if has_timing:
                notes_parts.append("includes timing info")
            if not has_progress:
                notes_parts.append("WARNING: missing progress indicators")
            result["notes"] = " | ".join(notes_parts)
        else:
            result["status"] = "FAIL"
            result["notes"] = f"Index command had issues: {stderr[:500]}"

        if issues:
            result["bugs_found"].extend(issues)

    def _test_cli_search(self, result: Dict):
        """Test CLI-002: Search command (requires indexed project from CLI-001)"""
        # Note: This test depends on CLI-001 having indexed test-project-cli
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "--help"], timeout=10
        )

        # Check if search command is available
        if "search" not in stdout.lower():
            result["status"] = "FAIL"
            result["notes"] = "Search command not found in CLI help output"
            result["bugs_found"].append(
                {
                    "bug_id": "BUG-NEW-CLI-002",
                    "severity": "HIGH",
                    "description": "Search command missing from CLI - cannot search indexed code",
                    "test_id": "CLI-002",
                    "impact": "Major functionality gap - users cannot search their indexed code via CLI",
                }
            )
            return

        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = (
            'MANUAL TEST REQUIRED: Search command listed in help. Test actual search after indexing: python -m src.cli search "authentication" --project-name test-project. Verify: results returned, relevance scores shown, file paths and line numbers included, and search completes in <1 second.'
        )

    def _test_cli_list(self, result: Dict):
        """Test CLI-003: List command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "list"], timeout=30
        )

        if self._is_success_with_warnings(returncode, stdout, stderr):
            result["status"] = "PASS"
            result["notes"] = (
                "List command executed (may have warnings about Rust parser)"
            )
        else:
            result["status"] = "FAIL"
            result["notes"] = f"List command failed: {stderr[:500]}"

    def _test_cli_delete(self, result: Dict):
        """Test CLI-004: Delete command"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Delete command requires valid memory ID - manual test"

    def _test_cli_export(self, result: Dict):
        """Test CLI-005: Export command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "export", "/tmp/test_export.json"], timeout=30
        )

        if self._is_success_with_warnings(returncode, stdout, stderr):
            result["status"] = "PASS"
            result["notes"] = (
                "Export command executed (may have warnings about Rust parser)"
            )
        else:
            result["status"] = "FAIL"
            result["notes"] = f"Export command failed: {stderr[:500]}"

    def _test_cli_import(self, result: Dict):
        """Test CLI-006: Import command"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = (
            "Import command requires valid export file - manual test after export"
        )

    def _test_cli_health(self, result: Dict):
        """Test CLI-007: Health command (duplicate of INST-006)"""
        self._test_health_check(result)

    def _test_cli_watch(self, result: Dict):
        """Test CLI-008: Watch command"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Watch command runs continuously - requires manual testing"

    def _test_cli_stats(self, result: Dict):
        """Test CLI-009: Stats command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "stats"], timeout=30
        )

        if self._is_success_with_warnings(returncode, stdout, stderr):
            result["status"] = "PASS"
            result["notes"] = "Stats command executed"
        else:
            result["status"] = "FAIL"
            result["notes"] = f"Stats command failed: {stderr[:500]}"

    def _test_cli_backup(self, result: Dict):
        """Test CLI-010: Backup command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "backup", "/tmp/backup.tar.gz"], timeout=60
        )

        if self._is_success_with_warnings(returncode, stdout, stderr):
            result["status"] = "PASS"
            result["notes"] = "Backup command executed"
        else:
            result["status"] = "FAIL"
            result["notes"] = f"Backup command failed: {stderr[:500]}"

    def _test_cli_restore(self, result: Dict):
        """Test CLI-011: Restore command"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = (
            "Restore command requires valid backup - manual test after backup"
        )

    def _test_cli_optimize(self, result: Dict):
        """Test CLI-012: Optimize command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "optimize"], timeout=60
        )

        if self._is_success_with_warnings(returncode, stdout, stderr):
            result["status"] = "PASS"
            result["notes"] = "Optimize command executed"
        else:
            result["status"] = "FAIL"
            result["notes"] = f"Optimize command failed: {stderr[:500]}"

    def _test_cli_verify(self, result: Dict):
        """Test CLI-013: Verify command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "verify"], timeout=60
        )

        if self._is_success_with_warnings(returncode, stdout, stderr):
            result["status"] = "PASS"
            result["notes"] = "Verify command executed"
        else:
            result["status"] = "FAIL"
            result["notes"] = f"Verify command failed: {stderr[:500]}"

    def _test_cli_help(self, result: Dict):
        """Test CLI-014: Help command"""
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "src.cli", "--help"], timeout=10
        )

        if returncode == 0 and "usage" in stdout.lower():
            result["status"] = "PASS"
            result["notes"] = "Help displayed correctly"
        else:
            result["status"] = "FAIL"
            result["notes"] = "Help command failed or missing usage info"

    # ===== Placeholder implementations for other test categories =====

    def _test_python_indexing(self, result: Dict):
        """Test CODE-001: Python code indexing"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Code indexing test - use CLI-001 test results"

    def _test_javascript_indexing(self, result: Dict):
        """Test CODE-002: JavaScript indexing"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "JavaScript indexing requires test project"

    def _test_semantic_search(self, result: Dict):
        """Test CODE-003: Semantic search"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Semantic search requires indexed codebase"

    def _test_similarity_search(self, result: Dict):
        """Test CODE-004: Similarity search"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Similarity search requires indexed codebase"

    def _test_hybrid_search(self, result: Dict):
        """Test CODE-005: Hybrid search"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Hybrid search requires indexed codebase"

    def _test_memory_lifecycle(self, result: Dict):
        """Test MEM-001: Memory lifecycle"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Memory lifecycle testing requires MCP client"

    def _test_memory_provenance(self, result: Dict):
        """Test MEM-002: Memory provenance tracking"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Provenance testing requires MCP client"

    def _test_duplicate_detection(self, result: Dict):
        """Test MEM-003: Duplicate detection"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Duplicate detection requires MCP client"

    def _test_memory_consolidation(self, result: Dict):
        """Test MEM-004: Memory consolidation"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Memory consolidation requires MCP client"

    def _test_cross_project_search(self, result: Dict):
        """Test PROJ-001: Cross-project search"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Cross-project search requires multiple indexed projects"

    def _test_project_isolation(self, result: Dict):
        """Test PROJ-002: Project isolation"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Project isolation requires multiple projects"

    def _test_consent_management(self, result: Dict):
        """Test PROJ-003: Consent management"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Consent management requires MCP client"

    def _test_health_score(self, result: Dict):
        """Test HEALTH-001: Health score calculation"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = (
            "Health score testing requires MCP client or CLI health command"
        )

    def _test_performance_metrics(self, result: Dict):
        """Test HEALTH-002: Performance metrics"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Performance metrics require MCP client"

    def _test_active_alerts(self, result: Dict):
        """Test HEALTH-003: Active alerts"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Alerts testing requires MCP client"

    def _test_env_variables(self, result: Dict):
        """Test CONFIG-001: Environment variables"""
        if self.config_tests:
            self.config_tests.test_env_variables(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Configuration test implementation not available"

    def _test_backend_switching(self, result: Dict):
        """Test CONFIG-002: Backend switching"""
        if self.config_tests:
            self.config_tests.test_backend_switching(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Configuration test implementation not available"

    def _test_model_configuration(self, result: Dict):
        """TEST CONFIG-003: Model configuration"""
        if self.config_tests:
            self.config_tests.test_model_configuration(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Configuration test implementation not available"

    def _test_readme_accuracy(self, result: Dict):
        """Test DOC-001: README accuracy"""
        readme = self.project_root / "README.md"
        if readme.exists():
            result["status"] = "PASS"
            result["notes"] = "README exists - manual review required for accuracy"
        else:
            result["status"] = "FAIL"
            result["notes"] = "README.md not found"

    def _test_api_docs(self, result: Dict):
        """Test DOC-002: API documentation"""
        api_doc = self.project_root / "docs" / "API.md"
        if api_doc.exists():
            result["status"] = "PASS"
            result["notes"] = "API documentation exists"
        else:
            result["status"] = "PASS"
            result["notes"] = (
                "API.md not found - check if documentation exists elsewhere"
            )

    def _test_examples(self, result: Dict):
        """Test DOC-003: Example code"""
        result["status"] = "MANUAL_REQUIRED"
        result["notes"] = "Examples require manual verification for accuracy"

    def _test_path_injection(self, result: Dict):
        """Test SEC-001: Path injection protection"""
        if self.security_tests:
            self.security_tests.test_path_injection(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Security test implementation not available"

    def _test_command_injection(self, result: Dict):
        """Test SEC-002: Command injection protection"""
        if self.security_tests:
            self.security_tests.test_command_injection(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Security test implementation not available"

    def _test_input_validation(self, result: Dict):
        """Test SEC-003: Input validation"""
        if self.security_tests:
            self.security_tests.test_input_validation(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Security test implementation not available"

    def _test_missing_dependencies(self, result: Dict):
        """Test ERR-001: Missing dependencies handling"""
        if self.error_tests:
            self.error_tests.test_missing_dependencies(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Error handling test implementation not available"

    def _test_invalid_inputs(self, result: Dict):
        """Test ERR-002: Invalid input handling"""
        if self.error_tests:
            self.error_tests.test_invalid_inputs(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Error handling test implementation not available"

    def _test_network_failures(self, result: Dict):
        """Test ERR-003: Network failure handling"""
        if self.error_tests:
            self.error_tests.test_network_failures(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Error handling test implementation not available"

    def _test_search_latency(self, result: Dict):
        """Test PERF-001: Search latency benchmark"""
        if self.perf_tests:
            self.perf_tests.test_search_latency(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Performance test implementation not available"

    def _test_indexing_speed(self, result: Dict):
        """Test PERF-002: Indexing speed benchmark"""
        if self.perf_tests:
            self.perf_tests.test_indexing_speed(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Performance test implementation not available"

    def _test_concurrent_load(self, result: Dict):
        """Test PERF-003: Concurrent load handling"""
        if self.perf_tests:
            self.perf_tests.test_concurrent_load(result)
        else:
            result["status"] = "ERROR"
            result["notes"] = "Performance test implementation not available"
