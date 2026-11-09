import pytest


def test_passes():
    assert 1 + 1 == 2


def test_passes_too():
    assert True


def test_passes_three():
    assert "a" in "abc"


def test_fails():
    assert 1 == 2


@pytest.mark.skip(reason="not yet")
def test_skipped():
    assert False
