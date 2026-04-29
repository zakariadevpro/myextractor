from app.tasks.scrape_tasks import (
    _clean_phone_list,
    _is_placeholder_phone,
    _validate_phone,
)


def test_placeholder_phones_are_rejected():
    assert _is_placeholder_phone("+33333333333") is True
    assert _is_placeholder_phone("+33999999999") is True
    assert _is_placeholder_phone("+33000000000") is True
    assert _is_placeholder_phone("+33999999977") is True
    assert _is_placeholder_phone("+33123456789") is True


def test_real_phones_pass_validation():
    assert _validate_phone("01 42 85 71 43") == "+33142857143"
    assert _validate_phone("+33 6 81 45 72 69") == "+33681457269"
    assert _validate_phone("0142857143") == "+33142857143"


def test_validate_rejects_placeholder_even_if_format_ok():
    assert _validate_phone("+33333333333") is None
    assert _validate_phone("+33999999977") is None
    assert _validate_phone("01 11 11 11 11") is None


def test_clean_phone_list_drops_placeholders_and_dedupes():
    raw = [
        "+33333333333",
        "+33681457269",
        "01 42 85 71 43",
        "+33142857143",
        "+33999999977",
        "+33261676921",
    ]
    cleaned = _clean_phone_list(raw)
    normalized = {_validate_phone(p) for p in cleaned}
    assert "+33333333333" not in normalized
    assert "+33999999977" not in normalized
    assert "+33681457269" in normalized
    assert "+33142857143" in normalized
    assert "+33261676921" in normalized
    assert len(cleaned) == 3
