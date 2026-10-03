import json
import shutil

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.plot import SAMPLES
from kedami_server.storage import SAMPLE_FIXTURE, seed_sample

TOKEN = "test-token"
ORIGIN = "http://localhost:5173"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    seed_sample(tmp_path)
    return tmp_path


@pytest.fixture
def client(data_dir):
    settings = Settings(port=0, token=TOKEN, data_dir=data_dir, allowed_origins=(ORIGIN,))
    return TestClient(create_app(settings))


ROUTES = ["/health", "/lessons", "/lessons/sample", "/lessons/sample/blocks/height-plot/points", "/lessons/missing"]


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}, {"Authorization": f"Bearer {TOKEN}x"}],
)
def test_every_route_rejects_bad_tokens(client, path, headers):
    assert client.get(path, headers=headers).status_code == 401


def test_health(client):
    assert client.get("/health", headers=AUTH).json() == {"status": "ok"}


def test_lesson(client):
    body = client.get("/lessons/sample", headers=AUTH).json()
    assert body["status"] == "ready"
    assert body["lesson"]["id"] == "sample"
    assert body["lesson"] == json.loads(json.dumps(body["lesson"]))


def test_lesson_response_fills_defaults(client):
    lesson = client.get("/lessons/sample", headers=AUTH).json()["lesson"]
    part_d = lesson["sections"][1]["blocks"][4]["parts"][3]
    assert part_d["verified"] is False


@pytest.mark.parametrize("lesson_id", ["missing", "..%2Fsecrets", "Sample"])
def test_unknown_lesson(client, lesson_id):
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).status_code == 404


def test_points(client):
    functions = client.get("/lessons/sample/blocks/height-plot/points", headers=AUTH).json()["functions"]
    assert [f["label"] for f in functions] == ["vy = 15 m/s", "vy = 10 m/s"]
    points = functions[0]["points"]
    assert len(points) == SAMPLES
    assert points[0] == [0, 0]
    assert points[-1][0] == pytest.approx(3.2)
    assert points[-1][1] == pytest.approx(15 * 3.2 - 4.9 * 3.2**2)


def test_points_are_none_where_undefined(client, data_dir):
    lesson = json.loads((data_dir / "lessons" / "sample.json").read_text())
    plot = lesson["sections"][1]["blocks"][1]
    plot["functions"] = [{"expression": "log(x)", "label": "log"}, {"expression": "1/(x - 1)", "label": "pole"}]
    plot["x_domain"] = [0, 2]
    (data_dir / "lessons" / "sample.json").write_text(json.dumps(lesson))
    log, pole = client.get("/lessons/sample/blocks/height-plot/points", headers=AUTH).json()["functions"]
    assert log["points"][0][1] is None
    assert log["points"][-1][1] == pytest.approx(0.6931, rel=1e-3)
    assert pole["points"][SAMPLES // 2][1] is None


def test_points_use_parameter_defaults(client, data_dir):
    lesson = json.loads((data_dir / "lessons" / "sample.json").read_text())
    plot = lesson["sections"][1]["blocks"][1]
    plot["functions"] = [{"expression": "a*x", "label": "line"}]
    plot["parameters"] = [{"name": "a", "min": 0, "max": 5, "default": 2}]
    (data_dir / "lessons" / "sample.json").write_text(json.dumps(lesson))
    points = client.get("/lessons/sample/blocks/height-plot/points", headers=AUTH).json()["functions"][0]["points"]
    assert points[-1][1] == pytest.approx(2 * 3.2)


@pytest.mark.parametrize("block_id", ["components-intro", "missing"])
def test_points_need_a_plot_block(client, block_id):
    assert client.get(f"/lessons/sample/blocks/{block_id}/points", headers=AUTH).status_code == 404


def test_preflight_from_allowed_origin_needs_no_token(client):
    response = client.options(
        "/lessons/sample",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_preflight_from_other_origin_is_refused(client):
    response = client.options(
        "/lessons/sample",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_seed_does_not_overwrite_existing_lesson(data_dir):
    path = data_dir / "lessons" / "sample.json"
    path.write_text("{}")
    seed_sample(data_dir)
    assert path.read_text() == "{}"


def test_seed_is_idempotent(tmp_path):
    db.init(tmp_path)
    seed_sample(tmp_path)
    seed_sample(tmp_path)
    assert (tmp_path / "lessons" / "sample.json").read_bytes() == SAMPLE_FIXTURE.read_bytes()
    with db.connect(tmp_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 1
