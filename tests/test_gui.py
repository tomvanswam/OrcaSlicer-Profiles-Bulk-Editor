import json
import threading
from collections.abc import Iterator
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

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
