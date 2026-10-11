import json
import threading
from collections.abc import Iterator
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from orca_profiles.core import ProfileRepository
from orca_profiles.gui.server import create_server


@pytest.fixture
def base_url(repo: ProfileRepository) -> Iterator[str]:
    server = create_server(repo, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get_json(url: str) -> dict:  # type: ignore[type-arg]
    with urlopen(url) as resp:
        return json.loads(resp.read())  # type: ignore[no-any-return]


def test_index_is_served(base_url: str) -> None:
    with urlopen(base_url + "/") as resp:
        assert resp.headers["Content-Type"].startswith("text/html")
        assert b"OrcaSlicer Profiles" in resp.read()


def test_profiles_endpoint(base_url: str) -> None:
    data = get_json(base_url + "/api/profiles")
    names = {p["name"] for p in data["profiles"]}
    assert "My PLA Silk" in names and len(data["errors"]) == 1
    common = next(p for p in data["profiles"] if p["name"] == "fdm_filament_common")
    assert common["instantiable"] is False


def test_chain_endpoint(base_url: str) -> None:
    data = get_json(f"{base_url}/api/chain?name={quote('My PLA Silk')}&type=filament")
    assert [n["name"] for n in data["chain"]][:2] == ["My PLA Silk", "My PLA base"]
    temp = data["settings"]["nozzle_temperature"]
    assert temp["source"] == "own" and temp["differs"] is True
    assert len(temp["overrides"]) == 3


@pytest.mark.parametrize(
    ("path", "status"),
    [("/api/chain?name=nope", 404), ("/api/chain?name=x&type=bad", 400), ("/nope", 404)],
)
def test_errors(base_url: str, path: str, status: int) -> None:
    with pytest.raises(HTTPError) as exc:
        urlopen(base_url + path)
    assert exc.value.code == status


def post_json(url: str, body: object) -> dict:  # type: ignore[type-arg]
    req = Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urlopen(req) as resp:
        return json.loads(resp.read())  # type: ignore[no-any-return]


@pytest.fixture
def edit_url(orca_dir, tmp_path, monkeypatch) -> Iterator[str]:  # type: ignore[no-untyped-def]
    import shutil

    shutil.copytree(orca_dir, tmp_path / "orca")
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = ProfileRepository.from_orca_dir(tmp_path / "orca")
    server = create_server(repo, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_edit_preview_and_apply(edit_url: str, tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = str(tmp_path / "orca/user/default/filament/My PLA Silk.json")
    body = {
        "edits": [{"path": path, "set": {"fan_max_speed": "55"}, "inherit": ["nozzle_temperature"]}]
    }
    preview = post_json(edit_url + "/api/edit", body)
    assert preview["applied"] is False
    changes = {c["key"]: c for c in preview["edits"][0]["changes"]}
    assert changes["fan_max_speed"]["new"] == ["55"]
    assert changes["nozzle_temperature"]["inherited_from"] == "My PLA base"

    done = post_json(edit_url + "/api/edit", body | {"apply": True})
    assert done["applied"] and len(done["backups"]) == 1
    chain = get_json(f"{edit_url}/api/chain?name={quote('My PLA Silk')}&type=filament")
    assert chain["settings"]["fan_max_speed"]["value"] == ["55"]
    assert chain["settings"]["nozzle_temperature"]["source"] == "parent"


def test_edit_rejects_non_json(base_url: str) -> None:
    req = Request(base_url + "/api/edit", b"edits=1", {"Content-Type": "text/plain"})
    with pytest.raises(HTTPError) as exc:
        urlopen(req)
    assert exc.value.code == 415
