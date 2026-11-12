import pytest


@pytest.fixture
def broken_teardown():
    yield "value"
    raise RuntimeError("teardown broke")


def test_body_and_teardown_fail(broken_teardown):
    # Both the body and the teardown fail. pytest writes two testcases for this one test (issue #42).
    assert broken_teardown == "other"
