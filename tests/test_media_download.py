"""Download recovery against a real HTTP server that truncates response bodies."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def skill_runner():
    runner = Path(__file__).resolve().parents[1] / "skills/game-assets/meowart_api.py"
    spec = importlib.util.spec_from_file_location("meowa_download_test", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("interruptions", [0, 1, 3])
def test_media_body_disconnect_retries_without_publishing_partial_file(
    skill_runner, tmp_path, monkeypatch, interruptions,
):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", "5")
            self.end_headers()
            self.wfile.write(b"fi" if len(calls) <= interruptions else b"final")
            self.close_connection = True

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_get = skill_runner.requests.get
    monkeypatch.setattr(
        skill_runner.requests, "get",
        lambda url, **kwargs: original_get(
            f"http://127.0.0.1:{server.server_port}/final.png", **kwargs,
        ),
    )
    monkeypatch.setattr(skill_runner.time, "sleep", lambda seconds: None)
    target = tmp_path / "final.png"
    target.write_bytes(b"existing final")
    try:
        def download():
            return skill_runner._download_file(
                "https://media-cn.meowjito.com/public/final.png", target,
                timeout=45, verify=True, require_media=True,
            )

        if interruptions == 3:
            with pytest.raises(skill_runner.requests.exceptions.ChunkedEncodingError):
                download()
            assert target.read_bytes() == b"existing final"
        else:
            assert download() == "image/png"
            assert target.read_bytes() == b"final"
        assert len(calls) == min(interruptions + 1, 3)
        assert not list(tmp_path.glob("*.part"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
