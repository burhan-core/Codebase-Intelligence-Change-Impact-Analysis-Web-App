import pytest

from services import github_app, parse_cache, pr_report, repo_cache

CALLER_PATCH = "@@ -1,2 +1,3 @@\n def store_it():\n-    return 1\n+    return 2\n"


@pytest.fixture
def isolated_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    monkeypatch.setattr(pr_report.metrics, "METRICS_PATH", tmp_path / "metrics.jsonl")
    return tmp_path


def test_analyze_pr_finds_callers_of_a_changed_function(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [
            {"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}
        ],
    )

    impact = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )

    assert impact.targets == ["app/store.py::store_it"]
    assert "app/main.py::handler" in [node["id"] for node in impact.impacted]
    assert "app/main.py" in impact.impacted_files


def test_second_analysis_reuses_clone_and_hits_the_parse_cache(
    isolated_roots, origin_repo, monkeypatch
):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [
            {"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}
        ],
    )

    first = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )
    second = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )

    assert first.stats["cloned"] is True
    assert first.stats["cache_misses"] == 2
    assert second.stats["cloned"] is False
    assert second.stats["cache_hits"] == 2
    assert second.stats["cache_misses"] == 0


def test_non_python_files_are_ignored(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [
            {"filename": "README.md", "status": "modified", "patch": "@@ -1 +1,2 @@\n+x\n"}
        ],
    )

    impact = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )

    assert impact.targets == []
    assert impact.impacted == []


def test_module_level_change_falls_back_to_the_file_node(
    isolated_roots, origin_repo, monkeypatch
):
    # A hunk at line 1 of main.py sits outside any function body.
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [
            {"filename": "app/main.py", "status": "modified", "patch": "@@ -1,0 +1,1 @@\n+import os\n"}
        ],
    )

    impact = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )

    assert impact.targets == ["app/main.py"]


def test_metrics_record_is_written_per_run(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [
            {"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}
        ],
    )

    pr_report.analyze_pr("owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None)

    lines = (isolated_roots / "metrics.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "parse_ms" in lines[0]
    assert "graph_ms" in lines[0]


def test_render_markdown_names_impacted_functions(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [
            {"filename": "app/store.py", "status": "modified", "patch": CALLER_PATCH}
        ],
    )

    impact = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )
    body = pr_report.render_markdown(impact)

    assert "store_it" in body
    assert "handler" in body
    assert "Impact Lens" in body


def test_render_markdown_handles_an_empty_blast_radius(isolated_roots, origin_repo, monkeypatch):
    monkeypatch.setattr(
        github_app,
        "pr_files",
        lambda repo, pr, token: [{"filename": "README.md", "patch": "@@ -1 +1,2 @@\n+x\n"}],
    )

    impact = pr_report.analyze_pr(
        "owner/repo", 7, origin_repo["second"], origin_repo["url"], token=None
    )
    body = pr_report.render_markdown(impact)

    assert "No Python changes" in body
