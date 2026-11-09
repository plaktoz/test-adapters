import pytest


def test_plain_pass():
    assert 1 + 1 == 2


@pytest.mark.xfail(reason="known bug")
def test_xfail_expected_failure():
    # Fails as expected: pytest reports an xfail, counted as skipped (4.2).
    assert 1 == 2


@pytest.mark.xfail(strict=False, reason="fixed but not removed")
def test_xpass_non_strict():
    # Passes although marked xfail: counted as passed (4.2).
    assert True


@pytest.mark.xfail(strict=True, reason="fixed but not removed")
def test_xpass_strict():
    # Passes although marked xfail(strict): pytest reports a failure, counted as failed (4.2).
    assert True


@pytest.fixture
def broken_teardown():
    yield "value"
    raise RuntimeError("teardown broke")


def test_teardown_error(broken_teardown):
    # The body passes. The fixture teardown raises, so the outcome is an error (4.2).
    assert broken_teardown == "value"
