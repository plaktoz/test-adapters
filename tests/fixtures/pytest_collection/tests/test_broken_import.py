import this_module_does_not_exist  # noqa: F401


def test_never_collected():
    assert True
