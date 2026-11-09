import pytest


@pytest.fixture
def broken_teardown():
    yield "value"
    raise RuntimeError("teardown broke")


def test_body_passes(broken_teardown):
    # The only problem in this project is the fixture teardown. errors > 0 must make status failed (4.2).
    assert broken_teardown == "value"
