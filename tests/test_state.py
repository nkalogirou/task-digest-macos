import json

from task_digest.state import DigestState


def test_state_migrates_old_flat_format(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"2026-07-20:morning": "time"}), encoding="utf-8")
    state = DigestState(str(path))
    assert state.sent("2026-07-20:morning")
    assert state.get_snapshot() == {}


def test_state_records_snapshot(tmp_path) -> None:
    path = tmp_path / "state.json"
    state = DigestState(str(path))
    state.record_run("2026-07-20:morning", "time", {"asana:1": {"title": "A"}})
    reloaded = DigestState(str(path))
    assert reloaded.sent("2026-07-20:morning")
    assert reloaded.get_snapshot()["asana:1"]["title"] == "A"
