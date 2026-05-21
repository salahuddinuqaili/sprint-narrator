from sprint_narrator.storage import get_trends_data, init_db, save_summary


def test_get_trends_data(tmp_path, monkeypatch):
    """get_trends_data returns parsed raw_data from saved summaries."""
    db_path = tmp_path / "history.db"
    monkeypatch.setattr("sprint_narrator.storage.DB_PATH", db_path)

    init_db()
    save_summary(
        date_range="2026-05-01 to 2026-05-14",
        sources=["github"],
        narrative="Sprint 1",
        raw_data={"total": 10, "completed": 8, "completion_rate": "80%", "contributors": ["Alice"]},
    )
    save_summary(
        date_range="2026-05-15 to 2026-05-28",
        sources=["github", "linear"],
        narrative="Sprint 2",
        raw_data={
            "total": 12,
            "completed": 10,
            "completion_rate": "83%",
            "contributors": ["Alice", "Bob"],
        },
    )

    data = get_trends_data(5)

    assert len(data) == 2
    # Oldest first
    assert data[0]["date_range"] == "2026-05-01 to 2026-05-14"
    assert data[0]["total"] == 10
    assert data[1]["date_range"] == "2026-05-15 to 2026-05-28"
    assert data[1]["completed"] == 10
    assert data[1]["contributors"] == ["Alice", "Bob"]


def test_get_trends_data_skips_bad_entries(tmp_path, monkeypatch):
    """Entries with missing or malformed raw_data are skipped."""
    db_path = tmp_path / "history.db"
    monkeypatch.setattr("sprint_narrator.storage.DB_PATH", db_path)

    init_db()
    # No raw_data
    save_summary("sprint 1", ["github"], "text", raw_data=None)
    # Valid raw_data
    save_summary(
        "sprint 2",
        ["github"],
        "text",
        raw_data={"total": 5, "completed": 3, "completion_rate": "60%", "contributors": []},
    )

    data = get_trends_data(5)

    assert len(data) == 1
    assert data[0]["total"] == 5
