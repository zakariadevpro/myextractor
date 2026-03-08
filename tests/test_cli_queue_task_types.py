from winxtract import cli


def test_execute_queue_task_supports_run_export_all(monkeypatch):
    captured: dict = {}

    def fake_run_then_export_sync(
        cfg,
        engine,
        session_factory,
        *,
        sources_dir,
        source_slug,
        export_format,
        min_score,
        city,
        has_email,
        has_phone,
        date_from,
        date_to,
        name_contains,
        progress_cb,
    ):
        captured.update(
            {
                "sources_dir": sources_dir,
                "source_slug": source_slug,
                "export_format": export_format,
                "min_score": min_score,
                "city": city,
                "has_email": has_email,
                "has_phone": has_phone,
                "date_from": date_from,
                "date_to": date_to,
                "name_contains": name_contains,
                "progress_cb": progress_cb,
            }
        )
        return "ok"

    monkeypatch.setattr(cli, "_run_then_export_sync", fake_run_then_export_sync)

    result = cli._execute_queue_task(
        object(),
        None,
        None,
        sources_dir="config/sources",
        task_type="run_export_all",
        payload={"scope": "all_active", "format": "csv", "min_score": 0},
    )

    assert result == "ok"
    assert captured["source_slug"] is None
    assert captured["export_format"] == "csv"
    assert captured["min_score"] == 0
