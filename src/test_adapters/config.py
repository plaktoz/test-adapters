"""Configuration model (requirements section 7, decision D18).

Source: `test-adapters.toml` in the working directory only. Precedence is
command-line flag > environment > config file > default. This module reads and validates the
file and the environment; it does not know about frameworks.

Standard library only (ADR 0003): `tomllib` reads the file, as UTF-8 bytes, so line endings
and encodings do not depend on the platform.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from test_adapters.errors import UsageError
from test_adapters.model import FrameworkName, FrozenMap, RetryMode, TestRequest, freeze

CONFIG_FILENAME = "test-adapters.toml"
ENV_PREFIX = "TEST_ADAPTERS_"  # environment variable for key `k` is ENV_PREFIX + k.upper()


@dataclass(frozen=True)
class Config:
    framework: FrameworkName = "auto"  # "auto", "all", or a registered framework name
    timeout_seconds: int = 600
    kill_grace_seconds: int = 5
    max_output_bytes: int = 5 * 1024 * 1024
    parallelism: int | str = "auto"  # an int, or "auto"
    require_tests: bool = True
    retry_failed: int = 0
    retry_mode: RetryMode = RetryMode.FILE
    coverage: bool = False
    command_overrides: Mapping[str, str] = field(default_factory=FrozenMap)

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_overrides", freeze(self.command_overrides))


# The type of each key. One table drives the file, the environment and flag checks.
_STR = "str"
_INT = "int"
_BOOL = "bool"
_PARALLELISM = "parallelism"
_RETRY_MODE = "retry_mode"
_OVERRIDES = "overrides"

_KINDS: dict[str, str] = {
    "framework": _STR,
    "timeout_seconds": _INT,
    "kill_grace_seconds": _INT,
    "max_output_bytes": _INT,
    "parallelism": _PARALLELISM,
    "require_tests": _BOOL,
    "retry_failed": _INT,
    "retry_mode": _RETRY_MODE,
    "coverage": _BOOL,
    "command_overrides": _OVERRIDES,
}
# A table cannot be written as one environment variable, so command_overrides is file-only.
_ENV_KEYS = tuple(key for key in _KINDS if key != "command_overrides")
_EXPECTED = {
    _STR: "a string",
    _INT: "an integer",
    _BOOL: "true or false",
    _PARALLELISM: 'an integer or "auto"',
    _RETRY_MODE: "file or isolated",
    _OVERRIDES: "a table of strings",
}


def load_config(cwd: Path) -> Config:
    """Read `cwd / test-adapters.toml` with `tomllib`. Missing file returns defaults.

    Raises UsageError on unknown keys, wrong types or invalid TOML. Unknown keys are an error
    so a typo does not silently fall back to a default.
    """
    path = cwd / CONFIG_FILENAME
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        return Config()
    except tomllib.TOMLDecodeError as exc:
        raise UsageError(f"{CONFIG_FILENAME}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise UsageError(f"cannot read {CONFIG_FILENAME}: {exc}") from exc
    return replace(Config(), **_validate(data, CONFIG_FILENAME))


def from_environment(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    """Read the `TEST_ADAPTERS_*` variables that are set and non-empty, typed as the file would be.

    Raises UsageError, naming the variable, when a value has the wrong type.
    """
    env = os.environ if environ is None else environ
    overrides: dict[str, object] = {}
    for key in _ENV_KEYS:
        name = ENV_PREFIX + key.upper()
        text = env.get(name, "")
        if text == "":
            continue
        overrides[key] = _coerce(key, _from_env_text(key, text), name)
    return overrides


def resolve_config(cwd: Path, flags: Mapping[str, object], environ: Mapping[str, str] | None = None) -> Config:
    """Apply the precedence of section 7: flag, then environment, then file, then default.

    `flags` holds only the flags the user gave. A key whose value is None is not set.
    """
    config = load_config(cwd)
    config = merge(config, from_environment(environ))
    return merge(config, flags)


def to_request(config: Config, cwd: Path) -> TestRequest:
    """Turn file config into a request. "auto" framework becomes None (detect); "all" is kept.

    `parallelism` "auto" stays "auto"; an int stays an int. Execution settings carry over so
    `run()` honours the file (7).
    """
    parallelism: int | str = config.parallelism
    if isinstance(parallelism, str) and parallelism != "auto":
        raise ValueError(f"parallelism must be an int or 'auto', got {parallelism!r}")
    return TestRequest(
        cwd=cwd,
        framework=None if config.framework == "auto" else config.framework,
        timeout_seconds=config.timeout_seconds,
        parallelism="auto" if parallelism == "auto" else int(parallelism),
        coverage=config.coverage,
        retry_failed=config.retry_failed,
        retry_mode=config.retry_mode,
        require_tests=config.require_tests,
        kill_grace_seconds=config.kill_grace_seconds,
        max_output_bytes=config.max_output_bytes,
    )


def merge(config: Config, overrides: Mapping[str, object]) -> Config:
    """Apply `overrides` over `config`. Unknown keys and wrong types raise UsageError.

    A None value means "not set" and is skipped, so the CLI can pass every flag.
    """
    return replace(config, **_validate(overrides))


def _validate(values: Mapping[str, object], source: str = "") -> dict[str, Any]:
    """Check every key and value, and return the typed values. None is skipped.

    Returns Any values because each one has just been checked against `_KINDS`, and
    `dataclasses.replace` takes keyword arguments that the type checker cannot match to fields.
    """
    prefix = f"{source}: " if source else ""
    checked: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if key not in _KINDS:
            raise UsageError(f"{prefix}unknown key {key!r}")
        checked[key] = _coerce(key, value, source)
    return checked


def _coerce(key: str, value: object, source: str = "") -> object:
    """Return `value` typed for `key`, or raise UsageError. `key` must be a known key."""
    kind = _KINDS[key]
    if kind == _STR and isinstance(value, str):
        return value
    if kind == _INT and _is_int(value):
        return value
    if kind == _BOOL and isinstance(value, bool):
        return value
    if kind == _PARALLELISM and (value == "auto" or _is_int(value)):
        return value
    if kind == _RETRY_MODE:
        if isinstance(value, RetryMode):
            return value
        if isinstance(value, str) and value in {mode.value for mode in RetryMode}:
            return RetryMode(value)
    if kind == _OVERRIDES and isinstance(value, Mapping):
        if all(isinstance(name, str) and isinstance(command, str) for name, command in value.items()):
            return dict(value)
    prefix = f"{source}: " if source else ""
    raise UsageError(f"{prefix}{key} must be {_EXPECTED[kind]}, got {value!r}")


def _from_env_text(key: str, text: str) -> object:
    """Turn environment text into the value the file would hold. A value that does not parse
    is returned as text, and `_coerce` rejects it with the variable name."""
    kind = _KINDS[key]
    if kind == _BOOL:
        return {"true": True, "false": False}.get(text.lower(), text)
    if kind in (_INT, _PARALLELISM):
        try:
            return int(text)
        except ValueError:
            return text
    return text


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
