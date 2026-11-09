"""Fixture for T5: two pass, one skips, one fails, then one test hangs past the timeout."""

import time

import pytest


def test_pass_one():
    assert True


def test_pass_two():
    assert True


@pytest.mark.skip(reason="skipped on purpose")
def test_skipped():
    pass


def test_fails():
    assert 1 == 2


def test_hangs():
    time.sleep(600)
