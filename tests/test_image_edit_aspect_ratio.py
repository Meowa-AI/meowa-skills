"""Offline CLI -> multipart request regressions; never submit a generation job."""
import argparse
from email.parser import BytesParser
from email.policy import default
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys

import pytest
import requests

RATIOS = ["auto", "1:1", "3:4", "4:3", "9:16", "16:9"]
MODELS = {"nano-banana": "nanobanana", "image-2": "image2", "image-2.5": "image2_5"}
RUNNER = Path(os.environ.get("MEOWA_TEST_RUNNER", Path(__file__).resolve().parents[1] / "skills/game-assets/meowart_api.py"))


@pytest.fixture
def runner(monkeypatch, tmp_path):
    def forbid_network(*args, **kwargs):
        pytest.fail("Real network and paid requests are forbidden in this regression")

    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_network)
    monkeypatch.setattr(socket, "create_connection", forbid_network)
    monkeypatch.setattr(requests.sessions.Session, "send", forbid_network)
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location("image_edit_offline", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cli(tmp_path, model, mode, ratio):
    source = tmp_path / "source.png"
    source.write_bytes(b"offline reference")
    args = ["image-edit-run", "--reference-image", str(source), "--prompt", "Replace the shield",
            "--generation-model", model, "--mode", mode, "--output-dir", str(tmp_path / "output")]
    if ratio is not None:
        args += ["--aspect-ratio", ratio]
    return args


@pytest.mark.parametrize("mode", ["pixel", "hd"])
@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("ratio", [None, *RATIOS])
def test_cli_to_actual_multipart_request(runner, monkeypatch, tmp_path, mode, model, ratio):
    argv = cli(tmp_path, model, mode, ratio)
    expected = ratio or "auto"
    assert runner.build_parser().parse_args(argv).aspect_ratio == expected
    captured = []

    def capture_send(session, request, **kwargs):
        captured.append(request)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"job_id":"offline-job"}'
        response.headers["Content-Type"] = "application/json"
        return response

    monkeypatch.setattr(requests.sessions.Session, "send", capture_send)
    monkeypatch.setattr(runner, "_resolve_auth_token", lambda: "offline-placeholder")
    monkeypatch.setattr(runner, "wait_submitted_workflow_job", lambda **kwargs: {"status": "success", "result": {}})
    monkeypatch.setattr(runner, "_save_run_outputs", lambda **kwargs: (tmp_path / "output", []))
    monkeypatch.setattr(sys, "argv", [str(RUNNER), *argv])
    assert runner.main() == 0
    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert request.url == "https://api.meowa.ai/api/workflows/image_edit/run"
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + request.headers["Content-Type"].encode() + b"\r\n\r\n" + request.body)
    fields = {part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
              for part in message.iter_parts()}
    assert fields["aspect_ratio"].decode() == expected
    assert fields["generation_provider"].decode() == MODELS[model]
    assert fields["reference_images"] == b"offline reference"


@pytest.mark.parametrize("ratio", ["3:5", "square", "", "AUTO"])
def test_invalid_ratio_rejected_before_auth_or_submission(runner, monkeypatch, tmp_path, ratio):
    def forbid_auth():
        pytest.fail("Invalid input must fail before authentication")
    monkeypatch.setattr(runner, "_resolve_auth_token", forbid_auth)
    monkeypatch.setattr(sys, "argv", [str(RUNNER), *cli(tmp_path, "image-2.5", "hd", ratio)])
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2


def test_contract_and_help_expose_ratio(runner):
    parser = runner.build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    command = subparsers.choices["image-edit-run"]
    action = next(action for action in command._actions if "--aspect-ratio" in action.option_strings)
    contract = json.loads(RUNNER.with_name("web_parameter_contract.json").read_text())["features"]["image_edit"]["parameters"]["aspect_ratio"]
    assert action.default == contract["default"] == "auto"
    assert set(action.choices) == set(contract["choices"]) == set(RATIOS)
    assert contract["request_field"] == "aspect_ratio"
    assert "--aspect-ratio" in command.format_help()


def test_packaged_release_integrity(runner):
    manifest = json.loads(RUNNER.with_name("release.json").read_text())
    assert manifest["version"] == runner.MEOWART_API_CLI_VERSION
    assert manifest["artifact_policy_version"] == runner.ARTIFACT_POLICY_VERSION
    assert manifest["sha256"] == hashlib.sha256(RUNNER.read_bytes()).hexdigest()
