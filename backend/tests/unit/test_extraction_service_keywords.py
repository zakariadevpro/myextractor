from app.schemas.extraction import ExtractionCreate
from app.services.extraction_service import ExtractionService


def test_build_keywords_does_not_inject_target_kind_tokens():
    b2c_payload = ExtractionCreate(
        source="whiteextractor",
        target_kind="b2c",
        first_name="Marcel",
        city="Paris",
    )
    b2b_payload = ExtractionCreate(
        source="whiteextractor",
        target_kind="b2b",
        company_name="Dupont Services",
        city="Paris",
    )

    b2c_keywords = [item.casefold() for item in ExtractionService._build_keywords(b2c_payload)]
    b2b_keywords = [item.casefold() for item in ExtractionService._build_keywords(b2b_payload)]

    assert "particulier" not in b2c_keywords
    assert "entreprise" not in b2b_keywords


def test_build_keywords_adds_full_name_and_postal_code():
    payload = ExtractionCreate(
        source="whiteextractor",
        target_kind="b2c",
        first_name="Jean",
        last_name="Dupont",
        postal_code="75001",
        keywords=["assurance", "jean"],
    )

    keywords = ExtractionService._build_keywords(payload)
    lowered = [item.casefold() for item in keywords]

    assert "jean dupont" in lowered
    assert "75001" in lowered
    assert lowered.count("jean") == 1
