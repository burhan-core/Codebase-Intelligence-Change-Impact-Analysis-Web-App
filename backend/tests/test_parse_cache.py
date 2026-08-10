import json

from services import parse_cache


def _seed(tmp_path, files):
    """Writes source files and returns a fake blob map keyed by content."""
    blobs = {}
    for relative, content in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        blobs[relative] = f"sha-{hash(content) & 0xFFFFFF:06x}"
    return blobs


def test_cold_start_parses_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})

    stats = parse_cache.sync("key", repo, blobs)

    assert stats.misses == 2
    assert stats.hits == 0
    assert (tmp_path / "metadata" / "key" / "a.py.json").exists()


def test_second_run_with_no_changes_is_all_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})

    parse_cache.sync("key", repo, blobs)
    stats = parse_cache.sync("key", repo, blobs)

    assert stats.hits == 2
    assert stats.misses == 0


def test_changed_blob_is_reparsed_and_others_are_not(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})
    parse_cache.sync("key", repo, blobs)

    (repo / "b.py").write_text("def two():\n    return renamed()\n", encoding="utf-8")
    blobs["b.py"] = "sha-changed"

    stats = parse_cache.sync("key", repo, blobs)

    assert stats.hits == 1
    assert stats.misses == 1
    metadata = json.loads(
        (tmp_path / "metadata" / "key" / "b.py.json").read_text(encoding="utf-8")
    )
    assert metadata["functions"][0]["calls"][0]["name"] == "renamed"


def test_deleted_file_has_metadata_evicted(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n", "b.py": "def two():\n    pass\n"})
    parse_cache.sync("key", repo, blobs)

    del blobs["b.py"]
    stats = parse_cache.sync("key", repo, blobs)

    assert stats.deleted == 1
    assert not (tmp_path / "metadata" / "key" / "b.py.json").exists()


def test_metadata_carries_relative_path_for_the_graph_builder(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"pkg/mod.py": "def one():\n    pass\n"})

    parse_cache.sync("key", repo, blobs)

    metadata = json.loads(
        (tmp_path / "metadata" / "key" / "pkg" / "mod.py.json").read_text(encoding="utf-8")
    )
    assert metadata["relative_path"] == "pkg/mod.py"


def test_missing_metadata_file_forces_reparse_despite_index_hit(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_cache, "METADATA_ROOT", tmp_path / "metadata")
    monkeypatch.setattr(parse_cache, "CACHE_ROOT", tmp_path / "cache")
    repo = tmp_path / "repo"
    blobs = _seed(repo, {"a.py": "def one():\n    pass\n"})
    parse_cache.sync("key", repo, blobs)

    (tmp_path / "metadata" / "key" / "a.py.json").unlink()
    stats = parse_cache.sync("key", repo, blobs)

    assert stats.misses == 1
