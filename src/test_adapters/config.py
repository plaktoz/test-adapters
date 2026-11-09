"""Configuration model (requirements section 7, decision D18).

Source: `test-adapters.toml` in the working directory only. Precedence is
command-line flag > environment > config file > default. This module only reads and
validates the file; it does not know about frameworks.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from test_adapters.model import FrameworkName, FrozenMap, RetryMode, TestRequest, freeze

CONFIG_FILENAME = "test-adapters.toml"


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


def load_config(cwd: Path) -> Config:
    """Read `cwd / test-adapters.toml` with `tomllib`. Missing file returns defaults.

    Raises UsageError on unknown keys or wrong types. Unknown keys are an error so a typo
    does not silently fall back to a default.
    """
    raise NotImplementedError


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


def merge(config: Config, overrides: dict[str, object]) -> Config:
    """Apply command-line flags (highest precedence) over the file config."""
    raise NotImplementedError
