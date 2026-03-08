from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from winxtract.storage.db import LeadORM, create_engine_from_url, init_db
from winxtract.storage.exporters import export_leads


def _seed(session: Session) -> None:
    now = datetime.now(timezone.utc)
    rows = [
        LeadORM(
            source_slug="s1",
            name="Alpha Bakery",
            city="Paris",
            emails="alpha@example.com",
            phones="",
            score=60,
            fingerprint="f1",
            scraped_at=now - timedelta(days=2),
        ),
        LeadORM(
            source_slug="s1",
            name="Beta Atelier",
            city="Paris",
            emails="",
            phones="+33123456789",
            score=40,
            fingerprint="f2",
            scraped_at=now - timedelta(days=1),
        ),
        LeadORM(
            source_slug="s2",
            name="Gamma Shop",
            city="Lyon",
            emails="gamma@example.com",
            phones="+33400000000",
            score=80,
            fingerprint="f3",
            scraped_at=now,
        ),
    ]
    session.add_all(rows)
    session.commit()


def test_export_filters_city_and_email(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'export_filters_1.db'}"
    engine = create_engine_from_url(db_url)
    init_db(engine)
    with Session(engine) as session:
        _seed(session)
        out = tmp_path / "out.json"
        count = export_leads(
            session,
            output=str(out),
            fmt="json",
            min_score=0,
            city="Paris",
            has_email=True,
        )
        assert count == 1


def test_export_filters_name_and_date(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'export_filters_2.db'}"
    engine = create_engine_from_url(db_url)
    init_db(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        _seed(session)
        out = tmp_path / "out.csv"
        count = export_leads(
            session,
            output=str(out),
            fmt="csv",
            min_score=0,
            name_contains="atelier",
            scraped_from=now - timedelta(days=1, hours=1),
            scraped_to=now + timedelta(hours=1),
        )
        assert count == 1


def test_export_filters_source_slugs(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'export_filters_3.db'}"
    engine = create_engine_from_url(db_url)
    init_db(engine)
    with Session(engine) as session:
        _seed(session)
        out = tmp_path / "out.xlsx"
        count = export_leads(
            session,
            output=str(out),
            fmt="xlsx",
            min_score=0,
            source_slugs=["s2"],
        )
        assert count == 1


def test_export_filters_city_case_insensitive(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'export_filters_4.db'}"
    engine = create_engine_from_url(db_url)
    init_db(engine)
    with Session(engine) as session:
        _seed(session)
        out = tmp_path / "out_case_city.json"
        count = export_leads(
            session,
            output=str(out),
            fmt="json",
            min_score=0,
            city="paris",
            has_email=True,
        )
        assert count == 1


def test_export_csv_writes_header_when_empty(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'export_filters_5.db'}"
    engine = create_engine_from_url(db_url)
    init_db(engine)
    with Session(engine) as session:
        _seed(session)
        out = tmp_path / "out_empty.csv"
        count = export_leads(
            session,
            output=str(out),
            fmt="csv",
            min_score=0,
            city="no-match-city",
        )
        assert count == 0
    content = out.read_text(encoding="utf-8")
    assert content.startswith("id,source_slug,name,city,website,emails,phones,score,page_url,scraped_at")
