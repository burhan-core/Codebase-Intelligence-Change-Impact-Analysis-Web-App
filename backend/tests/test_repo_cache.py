import pytest

from services import repo_cache


def test_project_key_is_stable_and_case_insensitive():
    assert repo_cache.project_key("Owner/Repo") == repo_cache.project_key("owner/repo")
    assert repo_cache.project_key("owner/repo") == repo_cache.project_key("owner/repo")


def test_project_key_differs_per_repo():
    assert repo_cache.project_key("a/b") != repo_cache.project_key("a/c")


def test_project_key_is_filesystem_safe():
    key = repo_cache.project_key("owner/repo")
    assert key.isalnum()
    assert len(key) == 16


def test_first_call_clones_and_second_call_reuses(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    path_one, cloned_one = repo_cache.ensure_repo(
        "owner/repo", origin_repo["url"], origin_repo["second"]
    )
    assert cloned_one is True
    assert (path_one / "app" / "main.py").exists()

    path_two, cloned_two = repo_cache.ensure_repo(
        "owner/repo", origin_repo["url"], origin_repo["second"]
    )
    assert cloned_two is False
    assert path_two == path_one


def test_ensure_repo_checks_out_the_requested_sha(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["first"])
    assert (path / "app" / "store.py").read_text(encoding="utf-8") == (
        "def store_it():\n    return 1\n"
    )

    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])
    assert (path / "app" / "store.py").read_text(encoding="utf-8") == (
        "def store_it():\n    return 2\n"
    )


def test_tree_blobs_lists_python_files_only(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")
    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])

    blobs = repo_cache.tree_blobs(path)

    assert set(blobs) == {"app/main.py", "app/store.py"}
    assert all(len(sha) == 40 for sha in blobs.values())


def test_tree_blobs_changes_only_for_changed_files(tmp_path, origin_repo, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["first"])
    before = repo_cache.tree_blobs(path)
    path, _ = repo_cache.ensure_repo("owner/repo", origin_repo["url"], origin_repo["second"])
    after = repo_cache.tree_blobs(path)

    assert before["app/main.py"] == after["app/main.py"]
    assert before["app/store.py"] != after["app/store.py"]


def test_unreachable_remote_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(repo_cache, "STORAGE_ROOT", tmp_path / "storage")

    with pytest.raises(repo_cache.RepoCacheError):
        repo_cache.ensure_repo("owner/nope", (tmp_path / "missing").as_uri(), "HEAD")
