from backend.services.persona_service import normalize_handles


def test_normalizes_and_dedupes_preserving_order():
    assert normalize_handles(["@UserB", "usera", "userb ", ""]) == ["userb", "usera"]


def test_empty_and_none_input():
    assert normalize_handles([]) == []
    assert normalize_handles(None) == []


def test_single_handle():
    assert normalize_handles(["@Some.User"]) == ["some.user"]
