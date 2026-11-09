"""Configuration model (requirements section 7, decision D18).

Source: `test-adapters.toml` in the working directory only. Precedence is
command-line flag > environment > config file > default. This module only reads and
validates the file; it does not know about frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from test_adapters.model import FrameworkName, RetryMode

CONFIG_FILENAME = "test-adapters.toml"


@dataclass(frozen=True)
class Config:
    framework: FrameworkName | str = "auto"  # "auto" | "pytest" | "jest" | "all"
    timeout_seconds: int = 600
    kill_grace_seconds: int = 5
    max_output_bytes: int = 5 * 1024 * 1024
    parallelism: int | str = "auto"
    require_tests: bool = True
    retry_failed: int = 0
    retry_mode: RetryMode = RetryMode.FILE
    coverage: bool = False
    command_overrides: dict[str, str] = field(default_factory=dict)


def load_config(cwd: Path) -> Config:
    """Read `cwd / test-adapters.toml` with `tomllib`. Missing file returns defaults.

    Raises UsageError on unknown keys or wrong types. Unknown keys are an error so a typo
    does not silently fall back to a default.
    """
    raise NotImplementedError


def merge(config: Config, overrides: dict[str, object]) -> Config:
    """Apply command-line flags (highest precedence) over the file config."""
    raise NotImplementedError
