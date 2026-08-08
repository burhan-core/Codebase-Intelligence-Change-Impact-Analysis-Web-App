from services.graph import build_graph_from_metadata

from tests.reference_graph import build_graph_reference


def _snapshot(dg):
    nodes = sorted((nid, tuple(sorted(data.items()))) for nid, data in dg.graph.nodes(data=True))
    edges = sorted((s, t, tuple(sorted(data.items()))) for s, t, data in dg.graph.edges(data=True))
    return nodes, edges


def test_indexed_builder_matches_reference_builder(metadata_tree):
    fast = build_graph_from_metadata(metadata_tree)
    reference = build_graph_reference(metadata_tree)

    assert _snapshot(fast) == _snapshot(reference)


def test_ambiguous_calls_are_still_marked_ambiguous(metadata_tree):
    dg = build_graph_from_metadata(metadata_tree)

    edge_types = {(s, t): data["type"] for s, t, data in dg.graph.edges(data=True)}
    # Two functions named `log` exist, so the call from handler resolves to
    # both, as calls_ambiguous.
    assert edge_types[("app/main.py::handler", "app/store.py::log")] == "calls_ambiguous"
    assert edge_types[("app/main.py::handler", "app/util/__init__.py::log")] == "calls_ambiguous"


def test_local_call_resolves_locally_not_globally(metadata_tree):
    dg = build_graph_from_metadata(metadata_tree)
    edge = dg.graph.edges[("app/main.py::handler", "app/main.py::helper")]
    assert edge["type"] == "calls"


def test_from_module_import_resolves_to_package_init(metadata_tree):
    dg = build_graph_from_metadata(metadata_tree)
    assert dg.graph.has_edge("app/main.py", "app/store.py")


def test_missing_metadata_directory_yields_empty_graph(tmp_path):
    dg = build_graph_from_metadata(tmp_path / "does-not-exist")
    assert dg.graph.number_of_nodes() == 0
