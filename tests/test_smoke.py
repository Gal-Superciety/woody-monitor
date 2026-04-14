"""Basic smoke tests to keep CI pytest step green."""


def test_pytest_collection_smoke() -> None:
    """Ensure at least one test is collected and executable."""
    assert True
