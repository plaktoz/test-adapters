"""Config file, environment and flag precedence (requirements 7, decisions D17 and D18).

Precedence is command-line flag, then environment, then config file, then default. Unknown
keys and wrong types are a usage error (exit 2). The CLI tests stop before any test runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_adapters import cli
from test_adapters.config import CONFIG_FILENAME, ENV_PREFIX, Config, from_environment, load_config, merge, to_request
from test_adapters.errors import UsageError
from test_adapters.model import RetryMode, TestRequest


class _Stop(Exception):
    """Raised by the fake run. Carries the request the CLI built, so no test runs."""

    def __init__(self, request: TestRequest) -> None:
        super().__init__("stopped before running a test")
        self.request = request


@pytest.fixture(autouse=True)
def no_real_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def stop(request: TestRequest) -> None:
        raise _Stop(request)

    monkeypatch.setattr(cli.api, "run", stop)
    monkeypatch.setattr(cli.api, "run_all", stop)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # A developer's shell may export TEST_ADAPTERS_* variables. Start every test without them.
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)


def write_config(cwd: Path, text: str) -> None:
    (cwd / CONFIG_FILENAME).write_text(text, encoding="utf-8")


def request_from_cli(cwd: Path, *flags: str) -> TestRequest:
    with pytest.raises(_Stop) as info:
        cli.main(["run", "--cwd", str(cwd), *flags])
    return info.value.request


# File loading


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path) == Config()


def test_file_values_reach_the_request(tmp_path: Path) -> None:
    # Acceptance: framework = "pytest" and timeout_seconds = 30 give those values in the request.
    write_config(tmp_path, 'framework = "pytest"\ntimeout_seconds = 30\n')
    request = to_request(load_config(tmp_path), tmp_path)
    assert request.framework == "pytest"
    assert request.timeout_seconds == 30


def test_every_documented_key_is_read(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """
framework = "all"
timeout_seconds = 120
kill_grace_seconds = 2
max_output_bytes = 1024
parallelism = 4
require_tests = false
retry_failed = 1
retry_mode = "isolated"
coverage = true

[command_overrides]
pytest = "python -m pytest -x"
""",
    )
    assert load_config(tmp_path) == Config(
        framework="all",
        timeout_seconds=120,
        kill_grace_seconds=2,
        max_output_bytes=1024,
        parallelism=4,
        require_tests=False,
        retry_failed=1,
        retry_mode=RetryMode.ISOLATED,
        coverage=True,
        command_overrides={"pytest": "python -m pytest -x"},
    )


def test_parallelism_auto_is_read(tmp_path: Path) -> None:
    write_config(tmp_path, 'parallelism = "auto"\n')
    assert load_config(tmp_path).parallelism == "auto"


def test_invalid_toml_is_a_usage_error(tmp_path: Path) -> None:
    write_config(tmp_path, "framework = \n")
    with pytest.raises(UsageError, match=CONFIG_FILENAME):
        load_config(tmp_path)


# Unknown keys and wrong types


def test_unknown_key_is_a_usage_error_naming_the_key(tmp_path: Path) -> None:
    write_config(tmp_path, 'frmework = "pytest"\n')
    with pytest.raises(UsageError, match="frmework"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "text, key",
    [
        ('parallelism = "fast"\n', "parallelism"),  # acceptance: exits 2 naming the key
        ('timeout_seconds = "30"\n', "timeout_seconds"),
        ("timeout_seconds = true\n", "timeout_seconds"),  # a bool is not an int
        ('require_tests = "yes"\n', "require_tests"),
        ("coverage = 1\n", "coverage"),
        ('retry_mode = "sometimes"\n', "retry_mode"),
        ("framework = 3\n", "framework"),
        ("max_output_bytes = 1.5\n", "max_output_bytes"),
        ("[command_overrides]\npytest = 3\n", "command_overrides"),
    ],
)
def test_wrong_type_is_a_usage_error_naming_the_key(tmp_path: Path, text: str, key: str) -> None:
    write_config(tmp_path, text)
    with pytest.raises(UsageError, match=key):
        load_config(tmp_path)


def test_cli_exits_2_on_unknown_key_before_running(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_config(tmp_path, 'frmework = "pytest"\n')
    assert cli.main(["run", "--cwd", str(tmp_path)]) == 2
    assert "frmework" in capsys.readouterr().err


def test_cli_exits_2_on_wrong_parallelism_before_running(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_config(tmp_path, 'parallelism = "fast"\n')
    assert cli.main(["run", "--cwd", str(tmp_path)]) == 2
    assert "parallelism" in capsys.readouterr().err


# Environment


def test_environment_values_are_typed() -> None:
    overrides = from_environment(
        {
            "TEST_ADAPTERS_FRAMEWORK": "pytest",
            "TEST_ADAPTERS_TIMEOUT_SECONDS": "30",
            "TEST_ADAPTERS_PARALLELISM": "auto",
            "TEST_ADAPTERS_REQUIRE_TESTS": "false",
            "TEST_ADAPTERS_RETRY_MODE": "isolated",
            "UNRELATED": "x",
        }
    )
    assert overrides == {
        "framework": "pytest",
        "timeout_seconds": 30,
        "parallelism": "auto",
        "require_tests": False,
        "retry_mode": RetryMode.ISOLATED,
    }


def test_environment_parallelism_accepts_an_integer() -> None:
    assert from_environment({"TEST_ADAPTERS_PARALLELISM": "4"}) == {"parallelism": 4}


@pytest.mark.parametrize(
    "name, value",
    [
        ("TEST_ADAPTERS_TIMEOUT_SECONDS", "soon"),
        ("TEST_ADAPTERS_PARALLELISM", "fast"),
        ("TEST_ADAPTERS_REQUIRE_TESTS", "yes"),
        ("TEST_ADAPTERS_RETRY_MODE", "sometimes"),
    ],
)
def test_bad_environment_value_names_the_variable(name: str, value: str) -> None:
    with pytest.raises(UsageError, match=name):
        from_environment({name: value})


# Merge


def test_merge_applies_overrides_and_refuses_unknown_keys() -> None:
    assert merge(Config(), {"timeout_seconds": 5}).timeout_seconds == 5
    with pytest.raises(UsageError, match="nope"):
        merge(Config(), {"nope": 1})


# Precedence in the CLI: flag > environment > file > default


def test_default_applies_when_nothing_is_set(tmp_path: Path) -> None:
    assert request_from_cli(tmp_path).timeout_seconds == 600


def test_file_overrides_default(tmp_path: Path) -> None:
    write_config(tmp_path, "timeout_seconds = 30\n")
    assert request_from_cli(tmp_path).timeout_seconds == 30


def test_flag_overrides_file(tmp_path: Path) -> None:
    # Acceptance: a flag on the command line overrides the file.
    write_config(tmp_path, "timeout_seconds = 30\n")
    assert request_from_cli(tmp_path, "--timeout", "45").timeout_seconds == 45


def test_flag_framework_overrides_file_framework(tmp_path: Path) -> None:
    write_config(tmp_path, 'framework = "pytest"\n')
    assert request_from_cli(tmp_path, "--framework", "jest").framework == "jest"


def test_environment_overrides_file_and_flag_overrides_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, "timeout_seconds = 30\n")
    monkeypatch.setenv("TEST_ADAPTERS_TIMEOUT_SECONDS", "40")
    assert request_from_cli(tmp_path).timeout_seconds == 40
    assert request_from_cli(tmp_path, "--timeout", "45").timeout_seconds == 45


def test_file_settings_reach_the_run_request(tmp_path: Path) -> None:
    write_config(tmp_path, "kill_grace_seconds = 2\nmax_output_bytes = 1024\nrequire_tests = false\n")
    request = request_from_cli(tmp_path)
    assert request.kill_grace_seconds == 2
    assert request.max_output_bytes == 1024
    assert request.require_tests is False


# Flags the engine does not implement stay refused, also when the file sets them (Phase 6)


@pytest.mark.parametrize("text", ["coverage = true\n", "retry_failed = 1\n", 'retry_mode = "isolated"\n'])
def test_file_setting_of_an_unimplemented_option_is_refused(
    tmp_path: Path, text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    write_config(tmp_path, text)
    assert cli.main(["run", "--cwd", str(tmp_path)]) == 2
    assert "not implemented" in capsys.readouterr().err
