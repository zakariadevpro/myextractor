from winxtract.cli import _is_non_retryable_error


def test_non_retryable_permission_error():
    assert _is_non_retryable_error(PermissionError("robots.txt disallows /"))


def test_non_retryable_value_error():
    assert _is_non_retryable_error(ValueError("invalid export format"))


def test_retryable_runtime_error():
    assert not _is_non_retryable_error(RuntimeError("temporary upstream timeout"))
