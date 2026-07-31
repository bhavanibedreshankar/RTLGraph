from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(graph, tmp_path_factory, monkeypatch_module=None):
    import storage.pipeline as pipeline

    # Avoid re-parsing: monkeypatch load_or_build_graph to hand back the
    # already-built session graph fixture instead of hitting disk again.
    original = pipeline.load_or_build_graph
    pipeline.load_or_build_graph = lambda *a, **k: graph
    try:
        from api.main import app

        with TestClient(app) as c:
            yield c
    finally:
        pipeline.load_or_build_graph = original


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_search_endpoint(client):
    r = client.get("/search", params={"q": "cmd_proc"})
    assert r.status_code == 200
    assert len(r.json()["results"]) > 0


def test_module_endpoint(client):
    r = client.get("/module", params={"name": "tpe_cmd_proc"})
    assert r.status_code == 200
    assert r.json()["name"] == "tpe_cmd_proc"


def test_module_endpoint_404(client):
    r = client.get("/module", params={"name": "nope"})
    assert r.status_code == 404


def test_signal_endpoint(client):
    r = client.get("/signal", params={"name": "ctrl_enable_q"})
    assert r.status_code == 200
    assert r.json()["matches"]


def test_driver_endpoint(client):
    r = client.get("/driver", params={"signal": "ctrl_enable_q", "module": "tpe_cmd_proc"})
    assert r.status_code == 200
    assert r.json()["drivers"]


def test_fanin_endpoint(client):
    r = client.get("/fanin", params={"signal": "ctrl_enable_q", "module": "tpe_cmd_proc"})
    assert r.status_code == 200
    assert isinstance(r.json()["fanin"], list)


def test_fanout_endpoint(client):
    r = client.get("/fanout", params={"signal": "s_awvalid", "module": "tpe_cmd_proc"})
    assert r.status_code == 200


def test_path_endpoint(client):
    r = client.get("/path", params={"source": "ctrl_enable_q", "destination": "s_awvalid", "module": "tpe_cmd_proc"})
    assert r.status_code == 200
    assert r.json()["found"] is True


def test_signal_not_found_returns_404(client):
    r = client.get("/driver", params={"signal": "totally_bogus_xyz"})
    assert r.status_code == 404
