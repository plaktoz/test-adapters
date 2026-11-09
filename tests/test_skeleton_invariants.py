"""Guards for the interrogate findings F1-F10 on the v0.1.0 skeleton.

Each test names the finding it guards. Imports are inside the tests so that one
missing name fails one test, not the whole module.
"""

from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def make_result(**overrides):
    from test_adapters.model import RawInfo, Status, TestResult

    base = dict(
        framework="pytest",
        status=Status.PASSED,
        error=None,
        total=5,
        passed=4,
        failed=0,
        skipped=1,
        errors=0,
        duration_ms=1,
        failures=(),
        flaky=(),
        coverage=None,
        warnings=(),
        degraded=False,
        raw=RawInfo(0, None, None),
        command="pytest",
    )
    base.update(overrides)
    return TestResult(**base)


NULL_COUNTS = dict(total=None, passed=None, failed=None, skipped=None, errors=None)


# F1: result invariants from requirements 4.2 and 4.4
class TestF1ResultInvariants:
    def test_passed_with_error_info_is_rejected(self):
        from test_adapters.model import ErrorCode, ErrorInfo, Status

        with pytest.raises(ValueError):
            make_result(status=Status.PASSED, error=ErrorInfo(ErrorCode.COLLECTION, "m", "h"))

    def test_failed_with_null_counts_is_rejected(self):
        from test_adapters.model import Status

        with pytest.raises(ValueError):
            make_result(status=Status.FAILED, **NULL_COUNTS)

    def test_total_must_equal_sum_of_counts(self):
        with pytest.raises(ValueError):
            make_result(total=6)

    def test_passed_with_failed_tests_is_rejected(self):
        from test_adapters.model import Status

        with pytest.raises(ValueError):
            make_result(status=Status.PASSED, passed=3, failed=1, total=5)

    def test_error_status_requires_error_info(self):
        from test_adapters.model import Status

        with pytest.raises(ValueError):
            make_result(status=Status.ERROR, error=None, **NULL_COUNTS)

    def test_combined_status_is_derived_not_stored(self):
        from test_adapters.model import CombinedResult, Status

        failed = make_result(status=Status.FAILED, passed=4, failed=1, skipped=0, total=5)
        combined = CombinedResult(results=(make_result(), failed))
        assert combined.status is Status.FAILED
        with pytest.raises(TypeError):
            CombinedResult(status=Status.PASSED, results=(failed,))

    def test_combined_result_needs_at_least_one_entry(self):
        from test_adapters.model import CombinedResult

        with pytest.raises(ValueError):
            CombinedResult(results=())


# F2: frozen objects must not hold mutable containers
class TestF2Immutability:
    def test_request_env_cannot_change_after_construction(self):
        from test_adapters.model import TestRequest

        request = TestRequest(cwd=Path("."))
        with pytest.raises(TypeError):
            request.env["X"] = "-x"

    def test_request_is_hashable(self):
        from test_adapters.model import TestRequest

        hash(TestRequest(cwd=Path(".")))

    def test_config_overrides_cannot_change(self):
        from test_adapters.config import Config

        config = Config(command_overrides={"pytest": "x"})
        with pytest.raises(TypeError):
            config.command_overrides["pytest"] = "y"

    def test_command_env_cannot_change(self):
        from test_adapters.adapters.base import Command

        command = Command(argv=("pytest",), env={}, report_paths=())
        with pytest.raises(TypeError):
            command.env["X"] = "1"


# F3: a new framework is a registration, not an edit to existing types
class TestF3OpenFrameworkSet:
    def test_toy_adapter_registers_without_editing_existing_code(self, monkeypatch):
        from test_adapters.adapters import registry
        from test_adapters.model import Framework

        monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))

        class Toy:
            name = "toy"
            command_template = "toy {report}"
            report_format = "toy"

            def detect(self, cwd):
                return False

            def build_command(self, request, workdir):
                raise NotImplementedError

            def parse(self, report_files, exit_code, stdout, timed_out):
                raise NotImplementedError

            def requires(self):
                return ()

        toy = Toy()
        registry.register(toy)
        assert registry.get("toy") is toy
        assert Framework(name="toy", evidence=()).name == "toy"

    def test_registering_a_name_twice_is_a_usage_error(self, monkeypatch):
        from test_adapters.adapters import registry
        from test_adapters.errors import UsageError

        monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))
        with pytest.raises(UsageError):
            registry.register(registry.get("pytest"))

    def test_unknown_framework_is_a_usage_error(self):
        from test_adapters.adapters import registry
        from test_adapters.errors import UsageError

        with pytest.raises(UsageError):
            registry.get("no-such-framework")


# F4: ambiguous runs have no single framework
class TestF4Ambiguous:
    def test_ambiguous_error_may_have_no_framework(self):
        from test_adapters.model import ErrorCode, ErrorInfo, Status

        result = make_result(
            framework=None,
            status=Status.ERROR,
            error=ErrorInfo(ErrorCode.AMBIGUOUS, "pytest, jest", "pass --framework"),
            **NULL_COUNTS,
        )
        assert result.framework is None

    def test_no_framework_is_allowed_only_for_ambiguous(self):
        from test_adapters.model import ErrorCode, ErrorInfo, Status

        with pytest.raises(ValueError):
            make_result(
                framework=None,
                status=Status.ERROR,
                error=ErrorInfo(ErrorCode.TOOL_MISSING, "m", "h"),
                **NULL_COUNTS,
            )


# F5: adapter parse takes what a run produces (requirements 5.2)
class TestF5AdapterParseSignature:
    def test_parse_takes_report_files_and_run_outputs(self):
        from test_adapters.adapters.pytest_adapter import PytestAdapter

        params = list(inspect.signature(PytestAdapter.parse).parameters)
        assert params == ["self", "report_files", "exit_code", "stdout", "timed_out"]


# Regression guard: the whole package passes strict type checking
class TestTypeCheck:
    def test_package_passes_mypy_strict(self):
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--strict", "src/test_adapters"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


# F6: the detect function must not be shadowed by a submodule of the same name
class TestF6DetectName:
    def test_detect_is_a_function_after_submodule_import(self):
        import test_adapters

        importlib.import_module("test_adapters.detection")
        assert inspect.isfunction(test_adapters.detect)


# F7: names that requirements 5.1 and 5.3 name must exist
class TestF7SpecNames:
    def test_adapter_info_is_exported_and_describes_an_adapter(self):
        import test_adapters
        from test_adapters.model import AdapterInfo

        info = test_adapters.adapter_info("pytest")
        assert isinstance(info, AdapterInfo)
        assert info.report_format
        assert "pytest" in info.requires

    def test_text_view_accepts_extra_fields(self):
        from test_adapters.render import text_view

        assert "fields" in inspect.signature(text_view).parameters


# F8: settings must be able to reach run(), and config must map to a request
class TestF8SettingsReachRun:
    def test_request_carries_execution_settings(self):
        from test_adapters.model import TestRequest

        request = TestRequest(cwd=Path("."))
        assert request.kill_grace_seconds == 5
        assert request.max_output_bytes == 5 * 1024 * 1024

    def test_config_auto_maps_to_detection_in_request(self):
        from test_adapters.config import Config, to_request

        request = to_request(Config(), Path("."))
        assert request.framework is None
        assert request.parallelism == "auto"
        assert request.kill_grace_seconds == 5

    def test_config_all_stays_all(self):
        from test_adapters.config import Config, to_request

        assert to_request(Config(framework="all"), Path(".")).framework == "all"


# F9: coverage files are objects on the wire (requirements 4.2)
class TestF9CoverageWire:
    def test_coverage_files_serialize_as_objects(self):
        import json

        from test_adapters.model import Coverage, CoverageFile, wire_coverage

        out = wire_coverage(Coverage(83.1, (CoverageFile("a.py", 70.0),)))
        assert json.loads(json.dumps(out)) == {
            "line_percent": 83.1,
            "files": [{"path": "a.py", "line_percent": 70.0}],
        }


# F10: built-in adapters are registered by importing the package
class TestF10BuiltinAdapters:
    def test_builtin_adapters_are_registered_on_import(self):
        import test_adapters  # noqa: F401
        from test_adapters.adapters import registry

        assert registry.get("pytest").name == "pytest"
        assert registry.get("jest").name == "jest"

    def test_registry_order_is_detection_order(self):
        import test_adapters  # noqa: F401
        from test_adapters.adapters import registry

        assert [a.name for a in registry.all_adapters()] == ["pytest", "jest"]
