from datetime import datetime, timezone

from sqlalchemy.orm import Session

from winxtract.storage.db import LeadORM, create_engine_from_url, init_db
from winxtract.storage.quality import compute_quality_report


def test_quality_report_basic(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'quality.db'}"
    engine = create_engine_from_url(db_url)
    init_db(engine)
    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        session.add_all(
            [
                LeadORM(
                    source_slug="s1",
                    name="A",
                    city="Paris",
                    emails="a@example.com",
                    phones="",
                    website="https://a.test",
                    score=80,
                    fingerprint="qa1",
                    scraped_at=now,
                ),
                LeadORM(
                    source_slug="s1",
                    name="B",
                    city="Paris",
                    emails="",
                    phones="+33111111111",
                    website="",
                    score=40,
                    fingerprint="qa2",
                    scraped_at=now,
                ),
            ]
        )
        session.commit()
        report = compute_quality_report(session, source_slug="s1")

    assert report["total_leads"] == 2
    assert report["with_email"] == 1
    assert report["with_phone"] == 1
    assert report["with_city"] == 2
    assert report["avg_score"] == 60.0
    assert report["coverage"]["email_ratio"] == 0.5
