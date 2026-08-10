import json

from services import metrics


def test_stage_records_duration_for_each_stage(tmp_path):
    run = metrics.RunMetrics(repo="owner/repo", pr=7)

    with run.stage("fetch"):
        pass
    with run.stage("parse"):
        pass

    assert "fetch_ms" in run.record
    assert "parse_ms" in run.record
    assert run.record["fetch_ms"] >= 0
    assert run.record["parse_ms"] >= 0


def test_set_adds_arbitrary_fields(tmp_path):
    run = metrics.RunMetrics(repo="owner/repo", pr=7)
    run.set(cache_hits=42, cache_misses=3)

    assert run.record["cache_hits"] == 42
    assert run.record["cache_misses"] == 3


def test_write_appends_one_json_object_per_run(tmp_path):
    target = tmp_path / "metrics.jsonl"

    first = metrics.RunMetrics(repo="a/b", pr=1)
    first.write(target)
    second = metrics.RunMetrics(repo="a/b", pr=2)
    second.write(target)

    lines = target.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["pr"] == 1
    assert json.loads(lines[1])["pr"] == 2


def test_write_records_total_and_timestamp(tmp_path):
    target = tmp_path / "metrics.jsonl"
    run = metrics.RunMetrics(repo="a/b", pr=1)
    written = run.write(target)

    assert "total_ms" in written
    assert "timestamp" in written
