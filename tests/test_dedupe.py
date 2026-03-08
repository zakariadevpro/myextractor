from winxtract.core.dedupe import lead_fingerprint


def test_fingerprint_prefers_email():
    fp1 = lead_fingerprint("Foo", "Paris", ["A@EXAMPLE.COM"])
    fp2 = lead_fingerprint("Bar", "Lyon", ["a@example.com"])
    assert fp1 == fp2


def test_fingerprint_name_city_fallback():
    fp1 = lead_fingerprint("Foo  Shop", " Paris ", [])
    fp2 = lead_fingerprint("foo shop", "paris", [])
    assert fp1 == fp2
