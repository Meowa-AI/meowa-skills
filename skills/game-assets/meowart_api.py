#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests

MEOWART_API_CLI_VERSION = "2026.06.11.2"
BOOTSTRAP_VERSION = 1
DEFAULT_API_BASE = "https://api.meowa.ai"
DEFAULT_API_KEY_ENV = "MEOWART_API_KEY"
DEFAULT_DEV_KEY_ENV = "MEOWART_DEV_KEY"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_WORK_DIR = str(Path(__file__).resolve().parent / ".meow_art")
DEFAULT_TIMEOUT = 240
DEFAULT_MAX_WAIT = 900
DEFAULT_POLL_INTERVAL = 3.0
ACTIVE_JOB_STATUSES = {"queued", "pending", "running"}
TERMINAL_JOB_STATUSES = {"success", "failure", "cancelled"}
TERMINAL_ANIMATE_STATUSES = {"success", "completed", "failure", "failed", "cancelled", "canceled"}
SUCCESS_ANIMATE_STATUSES = {"success", "completed"}
LONG_INLINE_DATA_DISPLAY_LIMIT = 240
AUTH_HEADER_HOST_SUFFIXES = ("meowa.ai", "generativelanguage.googleapis.com")
MEOWART_ENDPOINT_HINT = (
    "Meowa does not expose /generate or /api/generate. "
    "Use POST /api/pixel-gen for pixel sprites, POST /api/hd-gen for HD assets, "
    "or POST /api/gemini/... for generic image generation."
)
DEFAULT_BOOTSTRAP_MANIFEST_URL = (
    "https://raw.githubusercontent.com/Meowa-AI/meowa-skills/main/"
    "skills/game-assets/meowart_api.bootstrap.json"
)
BOOTSTRAP_ENABLED_ENV = "MEOWART_BOOTSTRAP"
BOOTSTRAP_SKIP_ENV = "MEOWART_BOOTSTRAP_SKIP"
BOOTSTRAP_MANIFEST_ENV = "MEOWART_BOOTSTRAP_MANIFEST_URL"
BOOTSTRAP_CACHE_DIR_ENV = "MEOWART_BOOTSTRAP_CACHE_DIR"
BOOTSTRAP_TIMEOUT_ENV = "MEOWART_BOOTSTRAP_TIMEOUT"
BOOTSTRAP_VERBOSE_ENV = "MEOWART_BOOTSTRAP_VERBOSE"
BOOTSTRAP_ALLOW_FILE_ENV = "MEOWART_BOOTSTRAP_ALLOW_FILE"
BOOTSTRAP_MAX_BYTES = 5 * 1024 * 1024
SKILL_DOC_URL_ENV = "MEOWA_SKILL_DOC_URL"
SKILL_DOC_CACHE_DIR_ENV = "MEOWA_SKILL_DOC_CACHE_DIR"
SKILL_DOC_CACHE_TTL_ENV = "MEOWA_SKILL_DOC_CACHE_TTL_SECONDS"
SKILL_DOC_MAX_BYTES = 100 * 1024
SKILL_DOC_DEFAULT_TTL_SECONDS = 24 * 60 * 60
MAP_PRESET_CATALOG_URL_ENV = "MEOWA_MAP_PRESET_CATALOG_URL"
MAP_PRESET_CATALOG_MAX_BYTES = 10 * 1024 * 1024
MAP_WORKFLOW_ENDPOINTS = {
    "pixel_isometric_gen": "/api/workflows/pixel_isometric_gen/run",
    "pixel_hex_isometric_gen": "/api/workflows/pixel_hex_isometric_gen/run",
    "hd_isometric_gen": "/api/workflows/hd_isometric_gen/run",
    "hd_hex_isometric_gen": "/api/workflows/hd_hex_isometric_gen/run",
}
MAP_WORKFLOW_COMMANDS = {
    "isometric-gen-submit": "pixel_isometric_gen",
    "pixel-isometric-gen-submit": "pixel_isometric_gen",
    "isometric-gen-run": "pixel_isometric_gen",
    "pixel-isometric-gen-run": "pixel_isometric_gen",
    "isometric-gen-poll": "pixel_isometric_gen",
    "pixel-isometric-gen-poll": "pixel_isometric_gen",
    "hex-isometric-gen-submit": "pixel_hex_isometric_gen",
    "pixel-hex-isometric-gen-submit": "pixel_hex_isometric_gen",
    "hex-isometric-gen-run": "pixel_hex_isometric_gen",
    "pixel-hex-isometric-gen-run": "pixel_hex_isometric_gen",
    "hex-isometric-gen-poll": "pixel_hex_isometric_gen",
    "pixel-hex-isometric-gen-poll": "pixel_hex_isometric_gen",
    "hd-isometric-gen-submit": "hd_isometric_gen",
    "hd-isometric-gen-run": "hd_isometric_gen",
    "hd-isometric-gen-poll": "hd_isometric_gen",
    "hd-hex-isometric-gen-submit": "hd_hex_isometric_gen",
    "hd-hex-isometric-gen-run": "hd_hex_isometric_gen",
    "hd-hex-isometric-gen-poll": "hd_hex_isometric_gen",
}
MAP_WORKFLOW_POLL_COMMANDS = {
    command for command in MAP_WORKFLOW_COMMANDS if command.endswith("-poll")
}


def _configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(line_buffering=True)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"", "0", "false", "no", "off"}


def _bootstrap_log(message: str) -> None:
    if _env_flag(BOOTSTRAP_VERBOSE_ENV):
        print(f"[BOOTSTRAP] {message}", file=sys.stderr)


def _default_bootstrap_cache_dir() -> Path:
    cache_root = os.environ.get("XDG_CACHE_HOME")
    if cache_root:
        return Path(cache_root).expanduser() / "meowa-skills" / "game-assets"
    return Path.home() / ".cache" / "meowa-skills" / "game-assets"


def _bootstrap_cache_dir() -> Path:
    configured = os.environ.get(BOOTSTRAP_CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return _default_bootstrap_cache_dir()


def _bootstrap_timeout() -> float:
    raw = os.environ.get(BOOTSTRAP_TIMEOUT_ENV, "").strip()
    if not raw:
        return 2.0
    try:
        return max(float(raw), 0.2)
    except ValueError:
        return 2.0


def _bootstrap_file_allowed() -> bool:
    return _env_flag(BOOTSTRAP_ALLOW_FILE_ENV)


def _bootstrap_url_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "file":
        return _bootstrap_file_allowed()
    return False


def _version_key(value: str) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for token in re.split(r"([0-9]+)", str(value or "").strip().lower()):
        if not token:
            continue
        if token.isdigit():
            parts.append((0, int(token)))
            continue
        parts.append((1, token))
    return tuple(parts)


def _is_version_newer(candidate: str, current: str) -> bool:
    return _version_key(candidate) > _version_key(current)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_bootstrap_url(url: str, timeout: float) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        if not _bootstrap_file_allowed():
            raise ValueError("file bootstrap URLs require MEOWART_BOOTSTRAP_ALLOW_FILE=1")
        return Path(unquote(parsed.path)).read_bytes()
    if parsed.scheme != "https":
        raise ValueError("bootstrap URLs must use https")
    response = requests.get(url, timeout=timeout, headers={"Accept": "application/json, text/plain, */*"})
    response.raise_for_status()
    content = response.content
    if len(content) > BOOTSTRAP_MAX_BYTES:
        raise ValueError(f"bootstrap payload too large: {len(content)} bytes")
    return content


def _fetch_bootstrap_manifest(manifest_url: str, timeout: float) -> dict[str, Any]:
    if not _bootstrap_url_allowed(manifest_url):
        raise ValueError("bootstrap manifest URL must use https")
    raw = _read_bootstrap_url(manifest_url, timeout)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("bootstrap manifest must be a JSON object")
    version = str(payload.get("version") or "").strip()
    runner_url = str(payload.get("runner_url") or "").strip()
    sha256 = str(payload.get("sha256") or "").strip().lower()
    min_bootstrap_version = int(payload.get("min_bootstrap_version") or 1)
    if not version:
        raise ValueError("bootstrap manifest missing version")
    if not runner_url:
        raise ValueError("bootstrap manifest missing runner_url")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("bootstrap manifest missing valid sha256")
    if min_bootstrap_version > BOOTSTRAP_VERSION:
        raise ValueError(
            f"bootstrap manifest requires bootstrap version {min_bootstrap_version}, "
            f"current is {BOOTSTRAP_VERSION}"
        )
    if not _bootstrap_url_allowed(runner_url):
        raise ValueError("bootstrap runner URL must use https")
    return {
        "version": version,
        "runner_url": runner_url,
        "sha256": sha256,
        "min_bootstrap_version": min_bootstrap_version,
        "manifest_url": manifest_url,
    }


def _bootstrap_state_path(cache_dir: Path) -> Path:
    return cache_dir / "bootstrap_state.json"


def _load_bootstrap_state(cache_dir: Path) -> dict[str, Any]:
    path = _bootstrap_state_path(cache_dir)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_bootstrap_state(cache_dir: Path, state: dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _bootstrap_state_path(cache_dir)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _cached_bootstrap_runner(cache_dir: Path) -> Path | None:
    state = _load_bootstrap_state(cache_dir)
    version = str(state.get("version") or "").strip()
    runner_path = Path(str(state.get("runner_path") or "")).expanduser()
    sha256 = str(state.get("sha256") or "").strip().lower()
    if not version or not runner_path.is_file() or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        return None
    if not _is_version_newer(version, MEOWART_API_CLI_VERSION):
        return None
    try:
        if _sha256_file(runner_path) != sha256:
            return None
    except OSError:
        return None
    return runner_path


def _download_bootstrap_runner(
    *,
    manifest: dict[str, Any],
    cache_dir: Path,
    timeout: float,
    force: bool,
) -> Path:
    version = str(manifest["version"])
    sha256 = str(manifest["sha256"])
    target = cache_dir / f"meowart_api_{_safe_slug(version)}_{sha256[:12]}.py"
    if target.is_file() and not force and _sha256_file(target) == sha256:
        return target

    raw = _read_bootstrap_url(str(manifest["runner_url"]), timeout)
    actual_sha = _sha256_bytes(raw)
    if actual_sha != sha256:
        raise ValueError(f"bootstrap runner sha256 mismatch: expected {sha256}, got {actual_sha}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(".py.tmp")
    tmp_path.write_bytes(raw)
    tmp_path.chmod(0o700)
    tmp_path.replace(target)
    return target


def _exec_bootstrap_runner(runner_path: Path, argv: list[str], source: str) -> None:
    env = os.environ.copy()
    env[BOOTSTRAP_SKIP_ENV] = "1"
    env["MEOWART_BOOTSTRAP_SOURCE"] = source
    env["MEOWART_BOOTSTRAP_PARENT_VERSION"] = MEOWART_API_CLI_VERSION
    _bootstrap_log(f"executing cached runner {runner_path}")
    os.execve(sys.executable, [sys.executable, str(runner_path), *argv[1:]], env)


def _bootstrap_disabled_by_argv(argv: list[str]) -> bool:
    return any(arg == "--no-bootstrap" for arg in argv[1:]) or "bootstrap-status" in argv[1:2]


def _bootstrap_should_skip(argv: list[str]) -> bool:
    if os.environ.get(BOOTSTRAP_SKIP_ENV):
        return True
    if not _env_flag(BOOTSTRAP_ENABLED_ENV, default=True):
        return True
    if _bootstrap_disabled_by_argv(argv):
        return True
    if any(arg in {"-h", "--help", "--version"} for arg in argv[1:]):
        return True
    return False


def _bootstrap_maybe_exec(argv: list[str]) -> None:
    if _bootstrap_should_skip(argv):
        return

    cache_dir = _bootstrap_cache_dir()
    timeout = _bootstrap_timeout()
    manifest_url = os.environ.get(BOOTSTRAP_MANIFEST_ENV, DEFAULT_BOOTSTRAP_MANIFEST_URL).strip()
    force = any(arg == "--bootstrap-force" for arg in argv[1:])
    try:
        manifest = _fetch_bootstrap_manifest(manifest_url, timeout)
    except Exception as exc:
        cached_runner = _cached_bootstrap_runner(cache_dir)
        if cached_runner is not None:
            _exec_bootstrap_runner(cached_runner, argv, "cached-after-manifest-error")
        _bootstrap_log(f"manifest check failed: {exc}")
        return

    if not _is_version_newer(str(manifest["version"]), MEOWART_API_CLI_VERSION):
        return

    try:
        runner_path = _download_bootstrap_runner(
            manifest=manifest,
            cache_dir=cache_dir,
            timeout=timeout,
            force=force,
        )
        state = {
            "version": manifest["version"],
            "sha256": manifest["sha256"],
            "runner_url": manifest["runner_url"],
            "manifest_url": manifest["manifest_url"],
            "runner_path": str(runner_path),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_bootstrap_state(cache_dir, state)
    except Exception as exc:
        cached_runner = _cached_bootstrap_runner(cache_dir)
        if cached_runner is not None:
            _exec_bootstrap_runner(cached_runner, argv, "cached-after-download-error")
        _bootstrap_log(f"runner update failed: {exc}")
        return

    _exec_bootstrap_runner(runner_path, argv, "remote-manifest")


def bootstrap_status(*, check_remote: bool = False) -> dict[str, Any]:
    cache_dir = _bootstrap_cache_dir()
    manifest_url = os.environ.get(BOOTSTRAP_MANIFEST_ENV, DEFAULT_BOOTSTRAP_MANIFEST_URL).strip()
    state = _load_bootstrap_state(cache_dir)
    payload: dict[str, Any] = {
        "bootstrap_version": BOOTSTRAP_VERSION,
        "cli_version": MEOWART_API_CLI_VERSION,
        "enabled": _env_flag(BOOTSTRAP_ENABLED_ENV, default=True),
        "manifest_url": manifest_url,
        "cache_dir": str(cache_dir),
        "cached_runner": state or None,
        "env": {
            BOOTSTRAP_ENABLED_ENV: os.environ.get(BOOTSTRAP_ENABLED_ENV, ""),
            BOOTSTRAP_MANIFEST_ENV: os.environ.get(BOOTSTRAP_MANIFEST_ENV, ""),
            BOOTSTRAP_CACHE_DIR_ENV: os.environ.get(BOOTSTRAP_CACHE_DIR_ENV, ""),
            BOOTSTRAP_TIMEOUT_ENV: os.environ.get(BOOTSTRAP_TIMEOUT_ENV, ""),
        },
    }
    if not check_remote:
        return payload
    try:
        manifest = _fetch_bootstrap_manifest(manifest_url, _bootstrap_timeout())
        payload["remote_manifest"] = manifest
        payload["remote_is_newer"] = _is_version_newer(str(manifest["version"]), MEOWART_API_CLI_VERSION)
    except Exception as exc:
        payload["remote_error"] = str(exc)
    return payload


def _mime_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _endpoint_hint_for_response(response: requests.Response) -> str:
    path = urlparse(str(response.url)).path.rstrip("/").lower()
    if response.status_code == 404 and path in {"/generate", "/api/generate"}:
        return f" {MEOWART_ENDPOINT_HINT}"
    return ""


def _parse_json_response(response: requests.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        body = response.text[:500].strip()
        raise ValueError(
            f"expected JSON response, got {content_type or 'unknown'}: {body}"
            f"{_endpoint_hint_for_response(response)}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object, got {type(payload).__name__}")
    return payload


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    timeout: int,
    verify: bool,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | list[tuple[str, Any]] | None = None,
    files: dict[str, tuple[str, bytes, str]] | list[tuple[str, tuple[str, bytes, str]]] | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[requests.Response, dict[str, Any]]:
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        data=data,
        files=files,
        json=json_body,
        timeout=timeout,
        verify=verify,
    )
    try:
        return response, _parse_json_response(response)
    except ValueError as exc:
        hint = _endpoint_hint_for_response(response)
        if hint and hint not in str(exc):
            raise ValueError(f"{exc}{hint}") from exc
        raise


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_json_for_display(payload: Any) -> str:
    return json.dumps(_sanitize_for_meta(payload), ensure_ascii=False, indent=2)


def _skill_doc_cache_dir() -> Path:
    configured = os.environ.get(SKILL_DOC_CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return _default_bootstrap_cache_dir() / "docs"


def _skill_doc_cache_ttl_seconds() -> int:
    raw = os.environ.get(SKILL_DOC_CACHE_TTL_ENV, "").strip()
    if not raw:
        return SKILL_DOC_DEFAULT_TTL_SECONDS
    try:
        return max(int(raw), 0)
    except ValueError:
        return SKILL_DOC_DEFAULT_TTL_SECONDS


def _skill_doc_cache_key(topic: str = "") -> str:
    cleaned = str(topic or "").strip().lower()
    if not cleaned:
        return "general"
    return re.sub(r"[^a-z0-9_.-]+", "_", cleaned).strip("_.-") or "general"


def _skill_doc_cache_path(topic: str = "") -> Path:
    return _skill_doc_cache_dir() / f"{_skill_doc_cache_key(topic)}.json"


def _local_skill_doc_path() -> Path:
    return Path(__file__).resolve().parent / "meowart_api.md"


def _normalize_meowa_brand_copy(content: str) -> str:
    return re.sub(r"Meow(?:Art|art)", "Meowa", content)


def _read_local_skill_doc() -> str:
    return _normalize_meowa_brand_copy(_local_skill_doc_path().read_text(encoding="utf-8"))


def _load_skill_doc_cache(topic: str = "") -> dict[str, Any] | None:
    path = _skill_doc_cache_path(topic)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    return payload if isinstance(content, str) and content else None


def _skill_doc_cache_is_fresh(payload: dict[str, Any]) -> bool:
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return False
    ttl = _skill_doc_cache_ttl_seconds()
    if ttl <= 0:
        return False
    return time.time() - float(fetched_at) <= ttl


def _write_skill_doc_cache(topic: str, payload: dict[str, Any]) -> None:
    cache_payload = dict(payload)
    cache_payload["fetched_at"] = time.time()
    _save_json(_skill_doc_cache_path(topic), cache_payload)


def _skill_doc_endpoint(api_base: str) -> str:
    configured = os.environ.get(SKILL_DOC_URL_ENV, "").strip()
    if configured:
        return configured
    return _normalize_base_url(api_base, "/api/agent-skills/game-assets/doc")


def _validate_remote_skill_doc(payload: dict[str, Any]) -> dict[str, Any]:
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("skill doc response missing markdown content")
    if str(payload.get("format") or "").strip().lower() != "markdown":
        raise ValueError("skill doc response format must be markdown")
    if len(content.encode("utf-8")) > SKILL_DOC_MAX_BYTES:
        raise ValueError(f"skill doc response too large: max {SKILL_DOC_MAX_BYTES} bytes")

    sha256 = str(payload.get("sha256") or "").strip().lower()
    actual_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if sha256 and sha256 != actual_sha:
        raise ValueError(f"skill doc sha256 mismatch: expected {sha256}, got {actual_sha}")

    normalized = dict(payload)
    normalized["content"] = _normalize_meowa_brand_copy(content)
    normalized["sha256"] = actual_sha
    return normalized


def _fetch_remote_skill_doc(
    *,
    api_base: str,
    topic: str = "",
    task: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
    cached: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = _skill_doc_endpoint(api_base)
    params: dict[str, str] = {}
    if topic:
        params["topic"] = topic
    if task:
        params["task"] = task

    headers = {"Accept": "application/json"}
    etag = str((cached or {}).get("etag") or "").strip()
    if etag:
        headers["If-None-Match"] = etag

    response = requests.get(url, params=params or None, timeout=timeout, verify=verify, headers=headers)
    if response.status_code == 304 and cached is not None:
        refreshed = dict(cached)
        refreshed["source"] = "cache-not-modified"
        refreshed["fetched_at"] = time.time()
        return refreshed
    response.raise_for_status()
    if len(response.content) > SKILL_DOC_MAX_BYTES * 2:
        raise ValueError(f"skill doc response too large: {len(response.content)} bytes")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("skill doc response must be a JSON object")

    doc = _validate_remote_skill_doc(payload)
    doc["source"] = "remote"
    doc["source_url"] = url
    doc["etag"] = response.headers.get("ETag", "")
    return doc


def _fallback_skill_doc(reason: str, *, topic: str = "") -> dict[str, Any]:
    content = _read_local_skill_doc()
    return {
        "skill_name": "game-assets",
        "skill_doc_version": "bundled",
        "format": "markdown",
        "content": content,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "source": "bundled-fallback",
        "topic": str(topic or "").strip() or None,
        "fallback": True,
        "warning": reason,
    }


def skill_doc(
    *,
    api_base: str,
    topic: str = "",
    task: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
    refresh: bool = False,
) -> dict[str, Any]:
    cached = _load_skill_doc_cache(topic)
    if cached is not None and not refresh and _skill_doc_cache_is_fresh(cached):
        result = dict(cached)
        result["source"] = "cache"
        return result

    try:
        remote = _fetch_remote_skill_doc(
            api_base=api_base,
            topic=str(topic or "").strip(),
            task=str(task or "").strip(),
            timeout=timeout,
            verify=verify,
            cached=cached,
        )
        _write_skill_doc_cache(topic, remote)
        return remote
    except Exception as exc:
        if cached is not None:
            result = dict(cached)
            result["source"] = "cache-after-remote-error"
            result["warning"] = str(exc)
            return result
        return _fallback_skill_doc(str(exc), topic=topic)


def skill_doc_status(
    *,
    api_base: str,
    topic: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
    check_remote: bool = False,
) -> dict[str, Any]:
    cached = _load_skill_doc_cache(topic)
    status: dict[str, Any] = {
        "endpoint": _skill_doc_endpoint(api_base),
        "cache_dir": str(_skill_doc_cache_dir()),
        "cache_key": _skill_doc_cache_key(topic),
        "cache_ttl_seconds": _skill_doc_cache_ttl_seconds(),
        "cached": None,
    }
    if cached is not None:
        status["cached"] = {
            "skill_doc_version": cached.get("skill_doc_version"),
            "sha256": cached.get("sha256"),
            "source": cached.get("source"),
            "fetched_at": cached.get("fetched_at"),
            "fresh": _skill_doc_cache_is_fresh(cached),
        }
    if not check_remote:
        return status
    try:
        remote = _fetch_remote_skill_doc(
            api_base=api_base,
            topic=topic,
            timeout=timeout,
            verify=verify,
            cached=cached,
        )
        status["remote"] = {
            "skill_doc_version": remote.get("skill_doc_version"),
            "sha256": remote.get("sha256"),
            "source": remote.get("source"),
            "updated_at": remote.get("updated_at"),
        }
    except Exception as exc:
        status["remote_error"] = str(exc)
    return status


def _map_preset_catalog_endpoint(api_base: str) -> str:
    configured = os.environ.get(MAP_PRESET_CATALOG_URL_ENV, "").strip()
    if configured:
        return configured
    return _normalize_base_url(api_base, "/api/agent-skills/game-assets/map-presets")


def fetch_map_preset_catalog(
    *,
    api_base: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _map_preset_catalog_endpoint(api_base)
    response, payload = _request_json(
        method="GET",
        url=url,
        headers={"Accept": "application/json"},
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    if len(response.content) > MAP_PRESET_CATALOG_MAX_BYTES:
        raise RuntimeError(f"map preset catalog too large: {len(response.content)} bytes")
    presets = payload.get("presets")
    if not isinstance(presets, list):
        raise ValueError("map preset catalog response missing presets list")
    return payload


def _preset_text_blob(preset: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "id",
        "catalogId",
        "workflowId",
        "workflowName",
        "templateId",
        "templateName",
        "templateDescription",
        "group",
        "filename",
        "label",
        "tileSize",
        "assetKind",
    ):
        value = preset.get(key)
        if value:
            parts.append(str(value))
    for value in preset.get("tags") or []:
        parts.append(str(value))
    metadata = preset.get("metadata")
    if isinstance(metadata, dict):
        for value in metadata.values():
            if value:
                parts.append(str(value))
    return " ".join(parts).lower()


def _query_tokens(query: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(query or "").strip().lower())
    return [token for token in normalized.split(" ") if token]


def _preset_matches_filters(
    preset: dict[str, Any],
    *,
    workflow_id: str = "",
    template_id: str = "",
    tile_size: str = "",
    asset_kind: str = "",
    group: str = "",
) -> bool:
    filters = {
        "workflowId": workflow_id,
        "templateId": template_id,
        "tileSize": tile_size,
        "assetKind": asset_kind,
        "group": group,
    }
    for key, raw_expected in filters.items():
        expected = str(raw_expected or "").strip()
        if expected and str(preset.get(key) or "").strip() != expected:
            return False
    return True


def _preset_search_score(preset: dict[str, Any], tokens: list[str]) -> int:
    if not tokens:
        return 0
    score = 0
    weighted_fields = (
        ("templateId", 8),
        ("templateName", 6),
        ("group", 4),
        ("filename", 4),
        ("templateDescription", 3),
        ("label", 3),
    )
    for token in tokens:
        for key, weight in weighted_fields:
            if token in str(preset.get(key) or "").lower():
                score += weight
    return score


def search_map_presets(
    *,
    api_base: str,
    query: str = "",
    workflow_id: str = "",
    template_id: str = "",
    tile_size: str = "",
    asset_kind: str = "",
    group: str = "",
    limit: int = 20,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    catalog = fetch_map_preset_catalog(api_base=api_base, timeout=timeout, verify=verify)
    tokens = _query_tokens(query)
    matches: list[dict[str, Any]] = []
    for preset in catalog.get("presets") or []:
        if not isinstance(preset, dict):
            continue
        if not _preset_matches_filters(
            preset,
            workflow_id=workflow_id,
            template_id=template_id,
            tile_size=tile_size,
            asset_kind=asset_kind,
            group=group,
        ):
            continue
        text_blob = _preset_text_blob(preset)
        if tokens and not all(token in text_blob for token in tokens):
            continue
        enriched = dict(preset)
        enriched["_score"] = _preset_search_score(enriched, tokens)
        matches.append(enriched)

    matches.sort(
        key=lambda item: (
            -int(item.get("_score") or 0),
            str(item.get("workflowId") or ""),
            str(item.get("templateId") or ""),
            str(item.get("group") or ""),
            str(item.get("filename") or ""),
        )
    )
    capped_limit = max(int(limit or 20), 1)
    return {
        "catalogId": catalog.get("catalogId"),
        "version": catalog.get("version"),
        "query": query,
        "filters": {
            "workflowId": workflow_id,
            "templateId": template_id,
            "tileSize": tile_size,
            "assetKind": asset_kind,
            "group": group,
        },
        "count": len(matches),
        "matches": matches[:capped_limit],
    }


def _absolute_url(api_base: str, value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("/"):
        return _normalize_base_url(api_base, raw)
    return raw


def _preset_download_filename(preset: dict[str, Any], index: int) -> str:
    filename = str(preset.get("filename") or "preset.png").strip() or "preset.png"
    suffix = Path(filename).suffix or ".png"
    stem = _safe_slug(
        "_".join(
            part
            for part in (
                str(preset.get("workflowId") or ""),
                str(preset.get("templateId") or ""),
                str(preset.get("group") or ""),
                Path(filename).stem,
            )
            if part
        )
    )
    return f"{index:02d}_{stem}{suffix}"


def download_map_presets(
    *,
    api_base: str,
    query: str = "",
    preset_ids: list[str] | None = None,
    workflow_id: str = "",
    template_id: str = "",
    tile_size: str = "",
    asset_kind: str = "",
    group: str = "",
    limit: int = 20,
    output_dir: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if preset_ids:
        catalog = fetch_map_preset_catalog(api_base=api_base, timeout=timeout, verify=verify)
        wanted = {str(preset_id).strip() for preset_id in preset_ids if str(preset_id).strip()}
        matches = [
            preset for preset in catalog.get("presets") or []
            if isinstance(preset, dict) and str(preset.get("id") or "") in wanted
        ]
        search_payload = {
            "catalogId": catalog.get("catalogId"),
            "version": catalog.get("version"),
            "query": "",
            "filters": {"ids": sorted(wanted)},
            "count": len(matches),
            "matches": matches[: max(int(limit or len(matches) or 1), 1)],
        }
    else:
        search_payload = search_map_presets(
            api_base=api_base,
            query=query,
            workflow_id=workflow_id,
            template_id=template_id,
            tile_size=tile_size,
            asset_kind=asset_kind,
            group=group,
            limit=limit,
            timeout=timeout,
            verify=verify,
        )
        matches = list(search_payload.get("matches") or [])

    if not matches:
        raise RuntimeError("no map preset matched the requested filters")

    target_dir = Path(output_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    _save_json(target_dir / "map_preset_search.json", _sanitize_for_meta(search_payload))

    downloads: list[dict[str, Any]] = [{"type": "json", "path": str(target_dir / "map_preset_search.json")}]
    for index, preset in enumerate(matches[: max(int(limit or len(matches)), 1)], start=1):
        if not isinstance(preset, dict):
            continue
        source_url = _absolute_url(
            api_base,
            str(preset.get("downloadPath") or preset.get("downloadUrl") or preset.get("url") or ""),
        )
        if not source_url:
            print(f"[WARN] preset has no downloadable URL: {preset.get('id')}", file=sys.stderr)
            continue
        target_path = target_dir / _preset_download_filename(preset, index)
        mime_type = _download_file(source_url, target_path, timeout=timeout, verify=verify)
        downloads.append(
            {
                "type": "map_preset",
                "preset_id": preset.get("id"),
                "source_url": source_url,
                "mime_type": mime_type,
                "path": str(target_path),
            }
        )
        print(f"[INFO] downloaded={target_path}")
    return search_payload, downloads


def _timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _mask_secret(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    return "***REDACTED***"


def _sanitize_for_meta(value: Any, *, key: str = "") -> Any:
    lowered_key = key.lower()
    if isinstance(value, dict):
        return {inner_key: _sanitize_for_meta(inner_value, key=str(inner_key)) for inner_key, inner_value in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_meta(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_meta(item, key=key) for item in value]
    if isinstance(value, Path):
        return str(value)
    if any(token in lowered_key for token in {"api_key", "dev_key", "token", "authorization", "secret"}):
        return _mask_secret(str(value))
    if lowered_key == "data" and isinstance(value, str) and len(value) > LONG_INLINE_DATA_DISPLAY_LIMIT:
        return f"***TRUNCATED_INLINE_DATA:{len(value)} chars***"
    return value


def _create_run_dir(work_dir: str, command: str) -> Path:
    root = Path(work_dir).expanduser()
    run_dir = root / f"{_timestamp_slug()}_{_safe_slug(command)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _resolve_output_dir(raw_path: str, run_dir: Path) -> Path:
    if str(raw_path or "").strip():
        return Path(raw_path).expanduser()
    return run_dir


def _predict_saved_dir(output_root: str | Path, slug_seed: str) -> Path:
    return Path(output_root).expanduser() / _safe_slug(slug_seed)


def _write_meta(
    *,
    run_dir: Path,
    started_at: str,
    finished_at: str,
    args: argparse.Namespace,
    request_payload: Any | None,
    response_payload: Any | None,
    downloads: list[dict[str, Any]] | None,
    effective_output_dir: str,
    error: str = "",
) -> None:
    meta = {
        "command": args.command,
        "started_at": started_at,
        "finished_at": finished_at,
        "run_dir": str(run_dir),
        "work_dir": str(Path(args.work_dir).expanduser()),
        "effective_output_dir": effective_output_dir,
        "request": {
            "cli_args": _sanitize_for_meta(vars(args)),
            "payload": _sanitize_for_meta(request_payload),
        },
        "response": _sanitize_for_meta(response_payload),
        "downloads": _sanitize_for_meta(downloads or []),
        "error": error,
    }
    _save_json(run_dir / "meta.json", meta)


def _suffix_from_mime(mime_type: str) -> str:
    normalized = str(mime_type or "").split(";", 1)[0].strip().lower()
    if not normalized:
        return ".bin"
    guessed = mimetypes.guess_extension(normalized)
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ".bin"


def _download_file(
    url: str,
    target_path: Path,
    *,
    timeout: int,
    verify: bool,
    headers: dict[str, str] | None = None,
) -> str:
    response = requests.get(url, timeout=timeout, verify=verify, headers=headers or None)
    response.raise_for_status()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(response.content)
    return str(response.headers.get("content-type") or "").strip()


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "output"


def _base_headers(api_key: str) -> dict[str, str]:
    token = str(api_key or "").strip()
    dev_prefix = "x-dev-key:"
    if token.startswith(dev_prefix):
        return {"X-Dev-Key": token[len(dev_prefix):].strip()}
    auth_prefix = "authenticate:"
    if token.lower().startswith(auth_prefix):
        candidate = token[len(auth_prefix):].strip()
        if candidate.startswith("ma_live_"):
            token = candidate
    return {"Authorization": f"Bearer {token}"}


def _host_matches_suffix(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith(f".{suffix}")


def _should_send_auth_headers(url: str) -> bool:
    host = (urlparse(url).netloc or "").strip().lower()
    if not host:
        return False
    if host.endswith("storage.googleapis.com"):
        return False
    return any(_host_matches_suffix(host, suffix) for suffix in AUTH_HEADER_HOST_SUFFIXES)


def _normalize_api_base(api_base: str) -> str:
    raw = str(api_base or DEFAULT_API_BASE).strip() or DEFAULT_API_BASE
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid --api-base: {raw!r}")

    path = parsed.path.rstrip("/")
    lowered_path = path.lower()
    if lowered_path in {"/generate", "/api/generate"}:
        print(
            f"[WARN] --api-base included deprecated endpoint path {path!r}; using host root instead. "
            f"{MEOWART_ENDPOINT_HINT}",
            file=sys.stderr,
        )
        path = ""

    return parsed._replace(path=path, params="", query="", fragment="").geturl().rstrip("/")


def _normalize_base_url(api_base: str, endpoint: str) -> str:
    return f"{_normalize_api_base(api_base)}/{endpoint.lstrip('/')}"


def _print_status(prefix: str, payload: dict[str, Any]) -> None:
    status = str(payload.get("status") or "").strip()
    stage = str(payload.get("stage") or "").strip()
    error = str(payload.get("error") or "").strip()
    progress = payload.get("progress")
    progress_label = ""
    progress_percent = ""
    if isinstance(progress, dict):
        progress_label = str(progress.get("label") or "").strip()
        progress_percent = str(progress.get("percent") or "").strip()
    line = f"{prefix} status={status or '?'}"
    if stage:
        line += f" stage={stage}"
    if progress_label or progress_percent:
        line += f" progress={progress_label or '?'}:{progress_percent or '?'}%"
    if error:
        line += f" error={error}"
    print(line)


def _collect_http_urls(value: Any, *, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            found.extend(_collect_http_urls(inner, prefix=child_prefix))
        return found
    if isinstance(value, list):
        for index, inner in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            found.extend(_collect_http_urls(inner, prefix=child_prefix))
        return found
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            found.append((prefix or "url", raw))
    return found


def _suffix_from_url(url: str) -> str:
    path = Path(url.split("?", 1)[0])
    suffix = path.suffix.lower()
    return suffix if suffix else ".bin"


def _filename_from_url_or_key(url: str, key: str) -> str:
    parsed = urlparse(url)
    raw_name = Path(parsed.path).name.strip()
    if raw_name and "." in raw_name and raw_name not in {".", ".."}:
        return raw_name
    fallback = _safe_slug(key.replace(".", "_").replace("[", "_").replace("]", ""))
    return f"{fallback}{_suffix_from_url(url)}"


def _unique_target_path(output_dir: Path, filename: str) -> Path:
    candidate = output_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        alternative = output_dir / f"{stem}_{counter}{suffix}"
        if not alternative.exists():
            return alternative
        counter += 1


def _collect_gemini_inline_images(value: Any, *, prefix: str = "") -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        mime_type = str(value.get("mimeType") or value.get("mime_type") or "").strip()
        data = str(value.get("data") or "").strip()
        if mime_type.startswith("image/") and data:
            found.append((prefix or "image", mime_type, data))
        for key, inner in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            found.extend(_collect_gemini_inline_images(inner, prefix=child_prefix))
        return found
    if isinstance(value, list):
        for index, inner in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            found.extend(_collect_gemini_inline_images(inner, prefix=child_prefix))
    return found


def _save_gemini_response_assets(
    *,
    payload: dict[str, Any],
    output_dir: str,
    timeout: int,
    verify: bool,
    api_key: str,
    save_json: bool = True,
) -> tuple[Path | None, list[dict[str, Any]]]:
    target_dir = Path(output_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    wrote_any = False
    downloads: list[dict[str, Any]] = []
    if save_json:
        _save_json(target_dir / "response.json", payload)
        wrote_any = True
        downloads.append({"type": "json", "path": str(target_dir / "response.json")})

    inline_images = _collect_gemini_inline_images(payload)
    for index, (key, mime_type, data) in enumerate(inline_images, start=1):
        filename = _safe_slug(key.replace(".", "_").replace("[", "_").replace("]", "")) or f"image_{index}"
        target_path = target_dir / f"{filename}_{index:02d}{_suffix_from_mime(mime_type)}"
        try:
            target_path.write_bytes(base64.b64decode(data, validate=True))
            wrote_any = True
            downloads.append({"type": "inline_image", "key": key, "mime_type": mime_type, "path": str(target_path)})
            print(f"[INFO] downloaded={target_path}")
        except ValueError as exc:
            print(f"[WARN] failed to decode inline image {key}: {exc}", file=sys.stderr)

    http_urls = [(key, url) for key, url in _collect_http_urls(payload) if any(token in key.lower() for token in {"image", "inline", "file", "uri", "url"})]
    if http_urls:
        downloaded_urls = _download_named_urls(
            urls=http_urls,
            output_dir=target_dir,
            timeout=timeout,
            verify=verify,
            headers=_base_headers(api_key),
        )
        downloads.extend(downloaded_urls)
        if downloaded_urls:
            wrote_any = True

    return (target_dir if wrote_any else None, downloads)


def _download_named_urls(
    *,
    urls: list[tuple[str, str]],
    output_dir: Path,
    timeout: int,
    verify: bool,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    downloads: list[dict[str, Any]] = []
    for key, url in urls:
        if url in seen:
            continue
        seen.add(url)
        target = _unique_target_path(output_dir, _filename_from_url_or_key(url, key))
        try:
            request_headers = headers if headers and _should_send_auth_headers(url) else None
            mime_type = _download_file(url, target, timeout=timeout, verify=verify, headers=request_headers)
            if target.suffix == ".bin":
                resolved_suffix = _suffix_from_mime(mime_type)
                if resolved_suffix != ".bin":
                    renamed_target = _unique_target_path(output_dir, f"{target.stem}{resolved_suffix}")
                    target.rename(renamed_target)
                    target = renamed_target
            downloads.append({"type": "url_download", "key": key, "url": url, "path": str(target)})
            print(f"[INFO] downloaded={target}")
        except requests.RequestException as exc:
            print(f"[WARN] download failed for {url}: {exc}", file=sys.stderr)
    return downloads


def _looks_like_downloadable_output_url(key: str, url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False

    path = parsed.path or ""
    if path.endswith("/"):
        return False

    host = (parsed.netloc or "").lower()
    if host == "storage.googleapis.com":
        if path.startswith("/meowart-bucket-public/"):
            return True
        return bool(parsed.query)

    lowered_key = key.lower()
    if any(token in lowered_key for token in {"base_url", "run_dir", "debug", "manifest", "metadata"}):
        return False
    return any(token in lowered_key for token in {"output", "result", "image", "file", "sprite", "audio", "music", "texture", "tileset", "preview", "url"})


def image_file_to_data_url(image_path: str) -> str:
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"image not found: {path}")
    mime = _mime_for_path(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def image_file_to_inline_data_part(image_path: str) -> dict[str, Any]:
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"image not found: {path}")
    return {
        "inline_data": {
            "mime_type": _mime_for_path(path),
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    }


def build_gemini_generate_content_contents(*, text: str = "", image_files: list[str] | None = None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if str(text or ""):
        parts.append({"text": str(text)})
    for raw_path in image_files or []:
        if str(raw_path or "").strip():
            parts.append(image_file_to_inline_data_part(raw_path))
    if not parts:
        raise ValueError("gemini-generate-content requires --text or at least one --image-file")
    return [{"parts": parts}]


def gemini_proxy_request(
    *,
    api_base: str,
    api_key: str,
    path: str,
    method: str = "POST",
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, f"/api/gemini/{path.lstrip('/')}")
    response, payload = _request_json(
        method=method.upper(),
        url=url,
        headers=_base_headers(api_key),
        json_body=json_body,
        params=params,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def gemini_generate_content(
    *,
    api_base: str,
    api_key: str,
    model: str,
    contents: list[dict[str, Any]],
    generation_config: dict[str, Any] | None = None,
    safety_settings: list[dict[str, Any]] | None = None,
    system_instruction: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {"contents": contents}
    if generation_config:
        body["generationConfig"] = generation_config
    if safety_settings:
        body["safetySettings"] = safety_settings
    if system_instruction:
        body["systemInstruction"] = system_instruction
    return gemini_proxy_request(
        api_base=api_base,
        api_key=api_key,
        path=f"v1beta/models/{model}:generateContent",
        method="POST",
        json_body=body,
        timeout=timeout,
        verify=verify,
    )


def get_credits_balance(
    *,
    api_base: str,
    api_key: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/credits/balance")
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def poll_job_until_done(
    *,
    jobs_url: str,
    api_key: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> dict[str, Any]:
    deadline = time.time() + max(max_wait, 1)
    headers = _base_headers(api_key)
    final_payload: dict[str, Any] | None = None
    while time.time() <= deadline:
        try:
            _, payload = _request_json(
                method="GET",
                url=jobs_url,
                headers=headers,
                timeout=timeout,
                verify=verify,
            )
        except (requests.RequestException, ValueError) as exc:
            print(f"[WARN] poll request failed: {exc}", file=sys.stderr)
            time.sleep(max(poll_interval, 0.1))
            continue

        _print_status("[INFO]", payload)
        status = str(payload.get("status") or "").strip().lower()
        if status in TERMINAL_JOB_STATUSES:
            final_payload = payload
            break
        if status not in ACTIVE_JOB_STATUSES:
            print(f"[WARN] unexpected intermediate status: {status}", file=sys.stderr)
        time.sleep(max(poll_interval, 0.1))

    if final_payload is None:
        raise TimeoutError(f"polling timed out after {max_wait}s")
    return final_payload


def pixel_gen_template_info(
    *,
    api_base: str,
    api_key: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/pixel-gen/template-info")
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def submit_pixel_gen(
    *,
    api_base: str,
    api_key: str,
    template_name: str,
    requirement: str,
    template_config: dict[str, Any] | None = None,
    job_name: str = "",
    model_name: str = "",
    resolution: str = "",
    aspect_ratio: str = "1:1",
    temperature: float = 0.0,
    include_base64: bool = False,
    reference_file: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    submit_url = _normalize_base_url(api_base, "/api/pixel-gen")
    data: dict[str, str] = {
        "template_name": template_name,
        "template_config": json.dumps(template_config or {}, ensure_ascii=False),
        "requirement": requirement,
        "aspect_ratio": aspect_ratio,
        "temperature": str(temperature),
        "include_base64": "true" if include_base64 else "false",
    }
    if job_name:
        data["job_name"] = job_name
    if model_name:
        data["model_name"] = model_name
    files = None
    if str(reference_file or "").strip():
        path = Path(reference_file).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"reference file not found: {path}")
        files = {"reference_file": (path.name, path.read_bytes(), _mime_for_path(path))}

    response, payload = _request_json(
        method="POST",
        url=submit_url,
        headers=_base_headers(api_key),
        data=data,
        files=files,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def poll_pixel_gen_job(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/pixel-gen/jobs")
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        params={"id": api_job_id},
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def wait_pixel_gen_job(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> dict[str, Any]:
    deadline = time.time() + max(max_wait, 1)
    final_payload: dict[str, Any] | None = None
    while time.time() <= deadline:
        payload = poll_pixel_gen_job(
            api_base=api_base,
            api_key=api_key,
            api_job_id=api_job_id,
            timeout=timeout,
            verify=verify,
        )
        _print_status("[INFO]", payload)
        status = str(payload.get("status") or "").strip().lower()
        if status in TERMINAL_JOB_STATUSES:
            final_payload = payload
            break
        time.sleep(max(poll_interval, 0.1))
    if final_payload is None:
        raise TimeoutError(f"pixel-gen polling timed out after {max_wait}s")
    return final_payload


def run_pixel_gen(
    *,
    api_base: str,
    api_key: str,
    template_name: str,
    requirement: str,
    template_config: dict[str, Any] | None = None,
    job_name: str = "",
    model_name: str = "",
    resolution: str = "",
    aspect_ratio: str = "1:1",
    temperature: float = 0.0,
    include_base64: bool = False,
    reference_file: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_pixel_gen(
        api_base=api_base,
        api_key=api_key,
        template_name=template_name,
        requirement=requirement,
        template_config=template_config,
        job_name=job_name,
        model_name=model_name,
        aspect_ratio=aspect_ratio,
        temperature=temperature,
        include_base64=include_base64,
        reference_file=reference_file,
        timeout=timeout,
        verify=verify,
    )
    api_job_id = str(submit_payload.get("api_job_id") or "").strip()
    if not api_job_id:
        raise RuntimeError("pixel-gen submit response missing api_job_id")
    print(f"[INFO] submitted api_job_id={api_job_id}")
    final_payload = wait_pixel_gen_job(
        api_base=api_base,
        api_key=api_key,
        api_job_id=api_job_id,
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def pixel_gen_history(
    *,
    api_base: str,
    api_key: str,
    limit: int = 20,
    offset: int = 0,
    status: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/pixel-gen/history")
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        params=params,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def pixel_gen_cancel(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, f"/api/pixel-gen/jobs/{api_job_id}/cancel")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def pixel_gen_download(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    output_dir: str,
    output_index: int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> Path:
    if output_index is None:
        url = _normalize_base_url(api_base, f"/api/pixel-gen/jobs/{api_job_id}/download")
    else:
        url = _normalize_base_url(api_base, f"/api/pixel-gen/jobs/{api_job_id}/outputs/{output_index}/download")
    target_dir = Path(output_dir).expanduser()
    suffix = ".png"
    if output_index is None:
        filename = f"{api_job_id}{suffix}"
    else:
        filename = f"{api_job_id}_output_{output_index}{suffix}"
    path = target_dir / filename
    _download_file(url, path, timeout=timeout, verify=verify, headers=_base_headers(api_key))
    return path


def hd_gen_template_info(
    *,
    api_base: str,
    api_key: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/hd-gen/template-info")
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def submit_hd_gen(
    *,
    api_base: str,
    api_key: str,
    template_name: str,
    requirement: str,
    template_config: dict[str, Any] | None = None,
    job_name: str = "",
    model_name: str = "gemini-3.1-flash-image-preview",
    resolution: str = "",
    aspect_ratio: str = "1:1",
    temperature: float = 0.0,
    hd_remove_bg_mode: str = "",
    include_base64: bool = False,
    reference_file: str = "",
    reference_files: list[str] | None = None,
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "template_name": template_name,
        "template_config": json.dumps(template_config or {}, ensure_ascii=False),
        "requirement": requirement,
        "job_name": job_name,
        "model_name": model_name,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "temperature": str(temperature),
        "hd_remove_bg_mode": hd_remove_bg_mode,
        "include_base64": "true" if include_base64 else "false",
    }
    if project_id is not None:
        data["project_id"] = project_id
    if thread_id is not None:
        data["thread_id"] = thread_id

    files: list[tuple[str, tuple[str, bytes, str]]] = []
    if str(reference_file or "").strip():
        path = Path(reference_file).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"reference file not found: {path}")
        files.append(("reference_file", (path.name, path.read_bytes(), _mime_for_path(path))))
    for raw_path in reference_files or []:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"reference file not found: {path}")
        files.append(("reference_files", (path.name, path.read_bytes(), _mime_for_path(path))))

    url = _normalize_base_url(api_base, "/api/hd-gen")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        files=files or None,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def poll_hd_gen_job(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/hd-gen/jobs")
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        params={"id": api_job_id},
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def wait_hd_gen_job(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> dict[str, Any]:
    deadline = time.time() + max(max_wait, 1)
    final_payload: dict[str, Any] | None = None
    while time.time() <= deadline:
        payload = poll_hd_gen_job(
            api_base=api_base,
            api_key=api_key,
            api_job_id=api_job_id,
            timeout=timeout,
            verify=verify,
        )
        _print_status("[INFO]", payload)
        status = str(payload.get("status") or "").strip().lower()
        if status in TERMINAL_JOB_STATUSES:
            final_payload = payload
            break
        time.sleep(max(poll_interval, 0.1))
    if final_payload is None:
        raise TimeoutError(f"hd-gen polling timed out after {max_wait}s")
    return final_payload


def run_hd_gen(
    *,
    api_base: str,
    api_key: str,
    template_name: str,
    requirement: str,
    template_config: dict[str, Any] | None = None,
    job_name: str = "",
    model_name: str = "gemini-3.1-flash-image-preview",
    resolution: str = "",
    aspect_ratio: str = "1:1",
    temperature: float = 0.0,
    hd_remove_bg_mode: str = "",
    include_base64: bool = False,
    reference_file: str = "",
    reference_files: list[str] | None = None,
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_hd_gen(
        api_base=api_base,
        api_key=api_key,
        template_name=template_name,
        requirement=requirement,
        template_config=template_config,
        job_name=job_name,
        model_name=model_name,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        temperature=temperature,
        hd_remove_bg_mode=hd_remove_bg_mode,
        include_base64=include_base64,
        reference_file=reference_file,
        reference_files=reference_files,
        project_id=project_id,
        thread_id=thread_id,
        timeout=timeout,
        verify=verify,
    )
    api_job_id = str(submit_payload.get("api_job_id") or submit_payload.get("job_id") or "").strip()
    if not api_job_id:
        raise RuntimeError("hd-gen submit response missing api_job_id")
    print(f"[INFO] submitted api_job_id={api_job_id}")
    final_payload = wait_hd_gen_job(
        api_base=api_base,
        api_key=api_key,
        api_job_id=api_job_id,
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def hd_gen_history(
    *,
    api_base: str,
    api_key: str,
    limit: int = 20,
    offset: int = 0,
    status: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/hd-gen/history")
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        params=params,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def hd_gen_cancel(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, f"/api/hd-gen/jobs/{api_job_id}/cancel")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def hd_gen_download(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    output_dir: str,
    output_index: int | None = None,
    preview: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> Path:
    if preview:
        url = _normalize_base_url(api_base, f"/api/hd-gen/jobs/{api_job_id}/preview/download")
        filename = f"{api_job_id}_preview.png"
    elif output_index is None:
        url = _normalize_base_url(api_base, f"/api/hd-gen/jobs/{api_job_id}/download")
        filename = f"{api_job_id}.png"
    else:
        url = _normalize_base_url(api_base, f"/api/hd-gen/jobs/{api_job_id}/outputs/{output_index}/download")
        filename = f"{api_job_id}_output_{output_index}.png"
    target_dir = Path(output_dir).expanduser()
    path = target_dir / filename
    mime_type = _download_file(url, path, timeout=timeout, verify=verify, headers=_base_headers(api_key))
    resolved_suffix = _suffix_from_mime(mime_type)
    if resolved_suffix != ".bin" and path.suffix.lower() != resolved_suffix:
        renamed_path = _unique_target_path(target_dir, f"{path.stem}{resolved_suffix}")
        path.rename(renamed_path)
        path = renamed_path
    return path


def submit_animate(
    *,
    api_base: str,
    api_key: str,
    image_data_url: str,
    prompt: str = "",
    is_pixel: bool = False,
    optimize_prompt: bool = True,
    model: str = "",
    negative_prompt: str = "",
    pixel_config: dict[str, Any] | None = None,
    output_frames: int = 8,
    seed: int | None = None,
    output_format: str = "webp",
    matte_color: str = "#808080",
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/animate")
    payload: dict[str, Any] = {
        "image": image_data_url,
        "prompt": prompt,
        "is_pixel": is_pixel,
        "optimize_prompt": optimize_prompt,
        "output_frames": output_frames,
        "output_format": output_format,
        "matte_color": matte_color,
    }
    if model:
        payload["model"] = model
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if pixel_config:
        payload["pixel_config"] = pixel_config
    if seed is not None:
        payload["seed"] = seed
    if project_id is not None:
        payload["project_id"] = project_id
    if thread_id is not None:
        payload["thread_id"] = thread_id

    response, body = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        json_body=payload,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(json.dumps(body, ensure_ascii=False, indent=2))
    return body


def submit_remove_background(
    *,
    api_base: str,
    api_key: str,
    image_file: str,
    method: str = "hd",
    enable_perfect_pixel: bool = False,
    is_white_bg: bool = True,
    prompt: str = "",
    ai_api_key: str = "",
    ai_model_name: str = "gemini-3.1-flash-image-preview",
    ai_resolution: str = "1K",
    ai_aspect_ratio: str = "1:1",
    ai_temperature: float = 0.0,
    ai_background_diff_threshold: int = 120,
    photoroom_api_key: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    path = Path(image_file).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"image file not found: {path}")
    data = {
        "method": method,
        "enable_perfect_pixel": "true" if enable_perfect_pixel else "false",
        "is_white_bg": "true" if is_white_bg else "false",
        "prompt": prompt,
        "ai_api_key": ai_api_key,
        "ai_model_name": ai_model_name,
        "ai_resolution": ai_resolution,
        "ai_aspect_ratio": ai_aspect_ratio,
        "ai_temperature": str(ai_temperature),
        "ai_background_diff_threshold": str(ai_background_diff_threshold),
        "photoroom_api_key": photoroom_api_key,
    }
    files = {"file": (path.name, path.read_bytes(), _mime_for_path(path))}
    url = _normalize_base_url(api_base, "/api/image/remove-background")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        files=files,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_remove_background(
    *,
    api_base: str,
    api_key: str,
    image_file: str,
    method: str = "hd",
    enable_perfect_pixel: bool = False,
    is_white_bg: bool = True,
    prompt: str = "",
    ai_api_key: str = "",
    ai_model_name: str = "gemini-3.1-flash-image-preview",
    ai_resolution: str = "1K",
    ai_aspect_ratio: str = "1:1",
    ai_temperature: float = 0.0,
    ai_background_diff_threshold: int = 120,
    photoroom_api_key: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_remove_background(
        api_base=api_base,
        api_key=api_key,
        image_file=image_file,
        method=method,
        enable_perfect_pixel=enable_perfect_pixel,
        is_white_bg=is_white_bg,
        prompt=prompt,
        ai_api_key=ai_api_key,
        ai_model_name=ai_model_name,
        ai_resolution=ai_resolution,
        ai_aspect_ratio=ai_aspect_ratio,
        ai_temperature=ai_temperature,
        ai_background_diff_threshold=ai_background_diff_threshold,
        photoroom_api_key=photoroom_api_key,
        timeout=timeout,
        verify=verify,
    )
    jobs_url = str(submit_payload.get("jobs_url") or "").strip()
    if not jobs_url:
        raise RuntimeError("remove-background submit response missing jobs_url")
    final_payload = poll_job_until_done(
        jobs_url=jobs_url,
        api_key=api_key,
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def submit_pixelate(
    *,
    api_base: str,
    api_key: str,
    image_file: str,
    pixel_size: str = "",
    alpha_threshold: int = 128,
    sample_method: str = "majority",
    min_size: float = 2.0,
    peak_width: int = 6,
    refine_intensity: float = 0.25,
    fix_square: bool = True,
    pad_pow2_square: bool = True,
    crop_border: bool = False,
    crop_color_thr: int = 20,
    crop_bg_ratio: float = 0.995,
    crop_edge_width: int = 10,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    path = Path(image_file).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"image file not found: {path}")
    data = {
        "pixel_size": pixel_size,
        "alpha_threshold": str(alpha_threshold),
        "sample_method": sample_method,
        "min_size": str(min_size),
        "peak_width": str(peak_width),
        "refine_intensity": str(refine_intensity),
        "fix_square": "true" if fix_square else "false",
        "pad_pow2_square": "true" if pad_pow2_square else "false",
        "crop_border": "true" if crop_border else "false",
        "crop_color_thr": str(crop_color_thr),
        "crop_bg_ratio": str(crop_bg_ratio),
        "crop_edge_width": str(crop_edge_width),
    }
    files = {"file": (path.name, path.read_bytes(), _mime_for_path(path))}
    url = _normalize_base_url(api_base, "/api/image/pixelate")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        files=files,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_pixelate(
    *,
    api_base: str,
    api_key: str,
    image_file: str,
    pixel_size: str = "",
    alpha_threshold: int = 128,
    sample_method: str = "majority",
    min_size: float = 2.0,
    peak_width: int = 6,
    refine_intensity: float = 0.25,
    fix_square: bool = True,
    pad_pow2_square: bool = True,
    crop_border: bool = False,
    crop_color_thr: int = 20,
    crop_bg_ratio: float = 0.995,
    crop_edge_width: int = 10,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_pixelate(
        api_base=api_base,
        api_key=api_key,
        image_file=image_file,
        pixel_size=pixel_size,
        alpha_threshold=alpha_threshold,
        sample_method=sample_method,
        min_size=min_size,
        peak_width=peak_width,
        refine_intensity=refine_intensity,
        fix_square=fix_square,
        pad_pow2_square=pad_pow2_square,
        crop_border=crop_border,
        crop_color_thr=crop_color_thr,
        crop_bg_ratio=crop_bg_ratio,
        crop_edge_width=crop_edge_width,
        timeout=timeout,
        verify=verify,
    )
    jobs_url = str(submit_payload.get("jobs_url") or "").strip()
    if not jobs_url:
        raise RuntimeError("pixelate submit response missing jobs_url")
    final_payload = poll_job_until_done(
        jobs_url=jobs_url,
        api_key=api_key,
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def submit_pixel_gen_self_loop(
    *,
    api_base: str,
    api_key: str,
    image_file: str,
    job_name: str = "",
    resolution: str = "1K",
    mode: str = "basic",
    direction: str = "horizontal",
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    path = Path(image_file).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"image file not found: {path}")
    data = {
        "job_name": job_name,
        "resolution": resolution,
        "mode": mode,
        "direction": direction,
    }
    files = {"file": (path.name, path.read_bytes(), _mime_for_path(path))}
    url = _normalize_base_url(api_base, "/api/workflows/pixel_gen_self_loop/run")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        files=files,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_pixel_gen_self_loop(
    *,
    api_base: str,
    api_key: str,
    image_file: str,
    job_name: str = "",
    resolution: str = "1K",
    mode: str = "basic",
    direction: str = "horizontal",
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_pixel_gen_self_loop(
        api_base=api_base,
        api_key=api_key,
        image_file=image_file,
        job_name=job_name,
        resolution=resolution,
        mode=mode,
        direction=direction,
        timeout=timeout,
        verify=verify,
    )
    jobs_url = str(submit_payload.get("jobs_url") or "").strip()
    if not jobs_url:
        raise RuntimeError("self-loop submit response missing jobs_url")
    final_payload = poll_job_until_done(
        jobs_url=jobs_url,
        api_key=api_key,
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def wait_submitted_workflow_job(
    *,
    api_base: str,
    api_key: str,
    submit_payload: dict[str, Any],
    label: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> dict[str, Any]:
    jobs_url = str(submit_payload.get("jobs_url") or "").strip()
    if jobs_url:
        return poll_job_until_done(
            jobs_url=jobs_url,
            api_key=api_key,
            timeout=timeout,
            max_wait=max_wait,
            poll_interval=poll_interval,
            verify=verify,
        )

    api_job_id = str(submit_payload.get("job_id") or submit_payload.get("api_job_id") or "").strip()
    if not api_job_id:
        raise RuntimeError(f"{label} submit response missing job_id")
    deadline = time.time() + max(max_wait, 1)
    final_payload: dict[str, Any] | None = None
    while time.time() <= deadline:
        payload = poll_job(
            api_base=api_base,
            api_key=api_key,
            api_job_id=api_job_id,
            timeout=timeout,
            verify=verify,
        )
        _print_status("[INFO]", payload)
        status = str(payload.get("status") or "").strip().lower()
        if status in TERMINAL_JOB_STATUSES:
            final_payload = payload
            break
        time.sleep(max(poll_interval, 0.1))
    if final_payload is None:
        raise TimeoutError(f"{label} polling timed out after {max_wait}s")
    return final_payload


def submit_sound_effect_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str,
    duration: float = 2,
    loop: bool = False,
    sound_pack: bool = False,
    variants: bool = False,
    count: int = 4,
    language: str = "en",
    temperature: float = 0.3,
    normalize_volume: bool = True,
    target_peak_db: float = -3.0,
    max_gain_db: float = 36.0,
    provider_api_key: str = "",
    base_url: str = "",
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "prompt": prompt,
        "duration": str(duration),
        "loop": "true" if loop else "false",
        "sound_pack": "true" if sound_pack else "false",
        "variants": "true" if variants else "false",
        "count": str(count),
        "language": language,
        "temperature": str(temperature),
        "normalize_volume": "true" if normalize_volume else "false",
        "target_peak_db": str(target_peak_db),
        "max_gain_db": str(max_gain_db),
    }
    if provider_api_key:
        data["api_key"] = provider_api_key
    if base_url:
        data["base_url"] = base_url
    if project_id is not None:
        data["project_id"] = project_id
    if thread_id is not None:
        data["thread_id"] = thread_id

    url = _normalize_base_url(api_base, "/api/workflows/elevenlabs_generator/run")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_sound_effect_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str,
    duration: float = 2,
    loop: bool = False,
    sound_pack: bool = False,
    variants: bool = False,
    count: int = 4,
    language: str = "en",
    temperature: float = 0.3,
    normalize_volume: bool = True,
    target_peak_db: float = -3.0,
    max_gain_db: float = 36.0,
    provider_api_key: str = "",
    base_url: str = "",
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_sound_effect_generator(
        api_base=api_base,
        api_key=api_key,
        prompt=prompt,
        duration=duration,
        loop=loop,
        sound_pack=sound_pack,
        variants=variants,
        count=count,
        language=language,
        temperature=temperature,
        normalize_volume=normalize_volume,
        target_peak_db=target_peak_db,
        max_gain_db=max_gain_db,
        provider_api_key=provider_api_key,
        base_url=base_url,
        project_id=project_id,
        thread_id=thread_id,
        timeout=timeout,
        verify=verify,
    )
    api_job_id = str(submit_payload.get("job_id") or submit_payload.get("api_job_id") or "").strip()
    if api_job_id:
        print(f"[INFO] submitted api_job_id={api_job_id}")
    final_payload = wait_submitted_workflow_job(
        api_base=api_base,
        api_key=api_key,
        submit_payload=submit_payload,
        label="sound",
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def submit_texture_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str = "",
    texture_names: list[str] | None = None,
    padding_mode: str = "no_padding",
    edge_fill_pixels: int = 1,
    self_loop: bool = True,
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    data: list[tuple[str, Any]] = [
        ("prompt", prompt),
        ("padding_mode", padding_mode),
        ("edge_fill_pixels", str(edge_fill_pixels)),
        ("self_loop", "true" if self_loop else "false"),
    ]
    for name in texture_names or []:
        data.append(("texture_names", name))
    if project_id is not None:
        data.append(("project_id", project_id))
    if thread_id is not None:
        data.append(("thread_id", thread_id))

    url = _normalize_base_url(api_base, "/api/workflows/texture_gen/run")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_texture_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str = "",
    texture_names: list[str] | None = None,
    padding_mode: str = "no_padding",
    edge_fill_pixels: int = 1,
    self_loop: bool = True,
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_texture_generator(
        api_base=api_base,
        api_key=api_key,
        prompt=prompt,
        texture_names=texture_names,
        padding_mode=padding_mode,
        edge_fill_pixels=edge_fill_pixels,
        self_loop=self_loop,
        project_id=project_id,
        thread_id=thread_id,
        timeout=timeout,
        verify=verify,
    )
    api_job_id = str(submit_payload.get("job_id") or submit_payload.get("api_job_id") or "").strip()
    if api_job_id:
        print(f"[INFO] submitted api_job_id={api_job_id}")
    final_payload = wait_submitted_workflow_job(
        api_base=api_base,
        api_key=api_key,
        submit_payload=submit_payload,
        label="texture-gen",
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def submit_tileset_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str = "",
    tileset_mode: str = "dual-grid-15",
    foreground_texture: str = "",
    background_texture: str = "",
    texture_reference_size: int | None = None,
    texture_reference_mode: str = "white_region_fill",
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "prompt": prompt,
        "tileset_mode": tileset_mode,
        "texture_reference_mode": texture_reference_mode,
    }
    if texture_reference_size is not None:
        data["texture_reference_size"] = str(texture_reference_size)
    if project_id is not None:
        data["project_id"] = project_id
    if thread_id is not None:
        data["thread_id"] = thread_id

    files: list[tuple[str, tuple[str, bytes, str]]] = []
    if str(foreground_texture or "").strip():
        path = Path(foreground_texture).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"foreground texture not found: {path}")
        files.append(("foreground_texture", (path.name, path.read_bytes(), _mime_for_path(path))))
    if str(background_texture or "").strip():
        path = Path(background_texture).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"background texture not found: {path}")
        files.append(("background_texture", (path.name, path.read_bytes(), _mime_for_path(path))))

    url = _normalize_base_url(api_base, "/api/workflows/tileset_gen/run")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        files=files or None,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_tileset_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str = "",
    tileset_mode: str = "dual-grid-15",
    foreground_texture: str = "",
    background_texture: str = "",
    texture_reference_size: int | None = None,
    texture_reference_mode: str = "white_region_fill",
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_tileset_generator(
        api_base=api_base,
        api_key=api_key,
        prompt=prompt,
        tileset_mode=tileset_mode,
        foreground_texture=foreground_texture,
        background_texture=background_texture,
        texture_reference_size=texture_reference_size,
        texture_reference_mode=texture_reference_mode,
        project_id=project_id,
        thread_id=thread_id,
        timeout=timeout,
        verify=verify,
    )
    api_job_id = str(submit_payload.get("job_id") or submit_payload.get("api_job_id") or "").strip()
    if api_job_id:
        print(f"[INFO] submitted api_job_id={api_job_id}")
    final_payload = wait_submitted_workflow_job(
        api_base=api_base,
        api_key=api_key,
        submit_payload=submit_payload,
        label="tileset-gen",
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def _append_reference_image_files(files: list[tuple[str, tuple[str, bytes, str]]], reference_images: list[str] | None) -> None:
    for raw_path in reference_images or []:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"reference image not found: {path}")
        files.append(("reference_images", (path.name, path.read_bytes(), _mime_for_path(path))))


def _optional_bool_form_value(value: bool | None) -> str | None:
    if value is None:
        return None
    return "true" if bool(value) else "false"


def submit_map_workflow(
    *,
    api_base: str,
    api_key: str,
    workflow_id: str,
    prompt: str,
    reference_images: list[str] | None = None,
    mode: str = "standard",
    template: str = "",
    similar_tiles: bool | None = None,
    tile_only: bool | None = None,
    road_template_id: str = "",
    road_width: int | None = None,
    style_name: str = "",
    style_description: str = "",
    top_left: str = "",
    top_right: str = "",
    bottom_left: str = "",
    bottom_right: str = "",
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    if workflow_id not in MAP_WORKFLOW_ENDPOINTS:
        raise ValueError(f"unsupported map workflow: {workflow_id}")

    data: dict[str, str] = {
        "prompt": prompt,
        "mode": mode,
    }
    if template:
        data["template"] = template
    for key, value in {
        "similar_tiles": _optional_bool_form_value(similar_tiles),
        "tile_only": _optional_bool_form_value(tile_only),
        "road_template_id": road_template_id,
        "style_name": style_name,
        "style_description": style_description,
        "top_left": top_left,
        "top_right": top_right,
        "bottom_left": bottom_left,
        "bottom_right": bottom_right,
    }.items():
        if value not in (None, ""):
            data[key] = str(value)
    if road_width is not None:
        data["road_width"] = str(road_width)
    if project_id is not None:
        data["project_id"] = project_id
    if thread_id is not None:
        data["thread_id"] = thread_id

    files: list[tuple[str, tuple[str, bytes, str]]] = []
    _append_reference_image_files(files, reference_images)

    url = _normalize_base_url(api_base, MAP_WORKFLOW_ENDPOINTS[workflow_id])
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        files=files or None,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_map_workflow(
    *,
    api_base: str,
    api_key: str,
    workflow_id: str,
    prompt: str,
    reference_images: list[str] | None = None,
    mode: str = "standard",
    template: str = "",
    similar_tiles: bool | None = None,
    tile_only: bool | None = None,
    road_template_id: str = "",
    road_width: int | None = None,
    style_name: str = "",
    style_description: str = "",
    top_left: str = "",
    top_right: str = "",
    bottom_left: str = "",
    bottom_right: str = "",
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_map_workflow(
        api_base=api_base,
        api_key=api_key,
        workflow_id=workflow_id,
        prompt=prompt,
        reference_images=reference_images,
        mode=mode,
        template=template,
        similar_tiles=similar_tiles,
        tile_only=tile_only,
        road_template_id=road_template_id,
        road_width=road_width,
        style_name=style_name,
        style_description=style_description,
        top_left=top_left,
        top_right=top_right,
        bottom_left=bottom_left,
        bottom_right=bottom_right,
        project_id=project_id,
        thread_id=thread_id,
        timeout=timeout,
        verify=verify,
    )
    api_job_id = str(submit_payload.get("job_id") or submit_payload.get("api_job_id") or "").strip()
    if api_job_id:
        print(f"[INFO] submitted api_job_id={api_job_id}")
    final_payload = wait_submitted_workflow_job(
        api_base=api_base,
        api_key=api_key,
        submit_payload=submit_payload,
        label=workflow_id,
        timeout=timeout,
        max_wait=max_wait,
        poll_interval=poll_interval,
        verify=verify,
    )
    return submit_payload, final_payload


def submit_music_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str = "",
    audio_generate: bool = False,
    demo: bool = False,
    reference_images: list[str] | None = None,
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "prompt": prompt,
        "audio_generate": "true" if audio_generate else "false",
        "demo": "true" if demo else "false",
    }
    if project_id is not None:
        data["project_id"] = project_id
    if thread_id is not None:
        data["thread_id"] = thread_id

    files: list[tuple[str, tuple[str, bytes, str]]] = []
    for raw_path in reference_images or []:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"reference image not found: {path}")
        files.append(("reference_images", (path.name, path.read_bytes(), _mime_for_path(path))))

    url = _normalize_base_url(api_base, "/api/workflows/music_generator/run")
    response, payload = _request_json(
        method="POST",
        url=url,
        headers=_base_headers(api_key),
        data=data,
        files=files or None,
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def poll_job(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, f"/api/jobs/{api_job_id}")
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    return payload


def run_music_generator(
    *,
    api_base: str,
    api_key: str,
    prompt: str = "",
    audio_generate: bool = False,
    demo: bool = False,
    reference_images: list[str] | None = None,
    project_id: str | None = None,
    thread_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    submit_payload = submit_music_generator(
        api_base=api_base,
        api_key=api_key,
        prompt=prompt,
        audio_generate=audio_generate,
        demo=demo,
        reference_images=reference_images,
        project_id=project_id,
        thread_id=thread_id,
        timeout=timeout,
        verify=verify,
    )
    jobs_url = str(submit_payload.get("jobs_url") or "").strip()
    if jobs_url:
        final_payload = poll_job_until_done(
            jobs_url=jobs_url,
            api_key=api_key,
            timeout=timeout,
            max_wait=max_wait,
            poll_interval=poll_interval,
            verify=verify,
        )
        return submit_payload, final_payload

    api_job_id = str(submit_payload.get("job_id") or submit_payload.get("api_job_id") or "").strip()
    if not api_job_id:
        raise RuntimeError("music submit response missing job_id")
    deadline = time.time() + max(max_wait, 1)
    final_payload: dict[str, Any] | None = None
    while time.time() <= deadline:
        payload = poll_job(
            api_base=api_base,
            api_key=api_key,
            api_job_id=api_job_id,
            timeout=timeout,
            verify=verify,
        )
        _print_status("[INFO]", payload)
        status = str(payload.get("status") or "").strip().lower()
        if status in TERMINAL_JOB_STATUSES:
            final_payload = payload
            break
        time.sleep(max(poll_interval, 0.1))
    if final_payload is None:
        raise TimeoutError(f"music polling timed out after {max_wait}s")
    return submit_payload, final_payload


def poll_animate_job(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> dict[str, Any]:
    url = _normalize_base_url(api_base, "/api/jobs")
    response, payload = _request_json(
        method="GET",
        url=url,
        headers=_base_headers(api_key),
        params={"id": api_job_id},
        timeout=timeout,
        verify=verify,
    )
    if response.status_code >= 400:
        raise RuntimeError(_format_json_for_display(payload))
    returned_job_id = str(payload.get("job_id") or payload.get("api_job_id") or "").strip()
    if returned_job_id == api_job_id:
        return payload

    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and str(item.get("job_id") or "").strip() == api_job_id:
                return item
    raise RuntimeError(f"animate job not found in /api/jobs response: {api_job_id}")


def wait_animate_job(
    *,
    api_base: str,
    api_key: str,
    api_job_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_wait: int = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: bool = True,
) -> dict[str, Any]:
    deadline = time.time() + max(max_wait, 1)
    final_payload: dict[str, Any] | None = None
    while time.time() <= deadline:
        try:
            payload = poll_animate_job(
                api_base=api_base,
                api_key=api_key,
                api_job_id=api_job_id,
                timeout=timeout,
                verify=verify,
            )
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            print(f"[WARN] animate poll request failed: {exc}", file=sys.stderr)
            time.sleep(max(poll_interval, 0.1))
            continue
        _print_status("[INFO]", payload)
        status = str(payload.get("status") or "").strip().lower()
        if status in TERMINAL_ANIMATE_STATUSES:
            final_payload = payload
            break
        time.sleep(max(poll_interval, 0.1))
    if final_payload is None:
        raise TimeoutError(f"animate polling timed out after {max_wait}s")
    return final_payload


def _save_run_outputs(
    *,
    output_root: str,
    slug_seed: str,
    submit_payload: dict[str, Any],
    final_payload: dict[str, Any],
    timeout: int,
    verify: bool,
    api_key: str = "",
    no_download: bool = False,
) -> tuple[Path, list[dict[str, Any]]]:
    output_dir = _predict_saved_dir(output_root, slug_seed)
    _save_json(output_dir / "submit_response.json", _sanitize_for_meta(submit_payload))
    _save_json(output_dir / "job_response.json", _sanitize_for_meta(final_payload))
    downloads: list[dict[str, Any]] = [
        {"type": "json", "path": str(output_dir / "submit_response.json")},
        {"type": "json", "path": str(output_dir / "job_response.json")},
    ]
    urls = [(key, url) for key, url in _collect_http_urls(final_payload) if _looks_like_downloadable_output_url(key, url)]
    if not no_download and urls:
        print(f"[INFO] downloading_outputs count={len(urls)} to={output_dir}")
        headers = _base_headers(api_key) if api_key else None
        downloads.extend(_download_named_urls(
            urls=urls,
            output_dir=output_dir,
            timeout=timeout,
            verify=verify,
            headers=headers,
        ))
    return output_dir, downloads


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone Meowa API test CLI.")
    parser.add_argument("--version", action="version", version=f"meowart_api.py {MEOWART_API_CLI_VERSION}")
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Run the bundled CLI without checking the remote bootstrap runner",
    )
    parser.add_argument(
        "--bootstrap-force",
        action="store_true",
        help="Force re-downloading the remote bootstrap runner when a newer manifest is available",
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="API base URL")
    parser.add_argument(
        "--api-key",
        default="",
        help=f"User API key, e.g. ma_live_xxx. Defaults to ${DEFAULT_API_KEY_ENV} or .env when omitted.",
    )
    parser.add_argument(
        "--dev-key",
        default="",
        help=(
            f"Developer auth key sent as X-Dev-Key. Defaults to ${DEFAULT_DEV_KEY_ENV}, "
            "then DEV_API_KEY, or matching .env values when omitted."
        ),
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Per-request timeout in seconds")
    parser.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT, help="Max polling wait in seconds")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL, help="Polling interval in seconds")
    parser.add_argument(
        "--work-dir",
        "--work_dir",
        dest="work_dir",
        default=DEFAULT_WORK_DIR,
        help="Base directory for per-run logs and metadata",
    )
    parser.add_argument(
        "--output-dir",
        "--output_dir",
        dest="output_dir",
        default="",
        help="Directory to save generated files; defaults to this run directory",
    )
    parser.add_argument("--no-download", action="store_true", help="Skip downloading remote files")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def option_exists(command_parser: argparse.ArgumentParser, *option_strings: str) -> bool:
        known_options = {
            option
            for action in command_parser._actions
            for option in getattr(action, "option_strings", ())
        }
        return any(option in known_options for option in option_strings)

    def add_if_missing(command_parser: argparse.ArgumentParser, *option_strings: str, **kwargs: Any) -> None:
        if not option_exists(command_parser, *option_strings):
            command_parser.add_argument(*option_strings, **kwargs)

    def add_shared_path_args(command_parser: argparse.ArgumentParser) -> None:
        # Mirror common global flags on subcommands so users can place them
        # either before or after the command name.
        add_if_missing(
            command_parser,
            "--no-bootstrap",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Run the bundled CLI without checking the remote bootstrap runner",
        )
        add_if_missing(
            command_parser,
            "--bootstrap-force",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Force re-downloading the remote bootstrap runner when a newer manifest is available",
        )
        add_if_missing(command_parser, "--api-base", default=argparse.SUPPRESS, help="API base URL")
        add_if_missing(
            command_parser,
            "--api-key",
            default=argparse.SUPPRESS,
            help=f"User API key, e.g. ma_live_xxx. Defaults to ${DEFAULT_API_KEY_ENV} or .env when omitted.",
        )
        add_if_missing(
            command_parser,
            "--dev-key",
            default=argparse.SUPPRESS,
            help=(
                f"Developer auth key sent as X-Dev-Key. Defaults to ${DEFAULT_DEV_KEY_ENV}, "
                "then DEV_API_KEY, or matching .env values when omitted."
            ),
        )
        add_if_missing(command_parser, "--timeout", type=int, default=argparse.SUPPRESS, help="Per-request timeout in seconds")
        add_if_missing(command_parser, "--max-wait", type=int, default=argparse.SUPPRESS, help="Max polling wait in seconds")
        add_if_missing(command_parser, "--poll-interval", type=float, default=argparse.SUPPRESS, help="Polling interval in seconds")
        add_if_missing(
            command_parser,
            "--work-dir",
            "--work_dir",
            dest="work_dir",
            default=argparse.SUPPRESS,
            help="Base directory for per-run logs and metadata",
        )
        add_if_missing(
            command_parser,
            "--output-dir",
            "--output_dir",
            dest="output_dir",
            default=argparse.SUPPRESS,
            help="Directory to save generated files; defaults to this run directory",
        )
        add_if_missing(command_parser, "--no-download", action="store_true", default=argparse.SUPPRESS, help="Skip downloading remote files")
        add_if_missing(command_parser, "--insecure", action="store_true", default=argparse.SUPPRESS, help="Disable TLS verification")

    def add_shared_runtime_args(command_parser: argparse.ArgumentParser) -> None:
        add_if_missing(
            command_parser,
            "--no-bootstrap",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Run the bundled CLI without checking the remote bootstrap runner",
        )
        add_if_missing(
            command_parser,
            "--bootstrap-force",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Force re-downloading the remote bootstrap runner when a newer manifest is available",
        )
        add_if_missing(command_parser, "--timeout", type=int, default=argparse.SUPPRESS, help="Per-request timeout in seconds")
        add_if_missing(command_parser, "--max-wait", type=int, default=argparse.SUPPRESS, help="Max polling wait in seconds")
        add_if_missing(command_parser, "--poll-interval", type=float, default=argparse.SUPPRESS, help="Polling interval in seconds")
        add_if_missing(command_parser, "--no-download", action="store_true", default=argparse.SUPPRESS, help="Skip downloading remote files")
        add_if_missing(command_parser, "--insecure", action="store_true", default=argparse.SUPPRESS, help="Disable TLS verification")

    def add_map_preset_filter_args(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--query", default="", help="Search text, e.g. ocean, desert, grass, modern, road")
        command_parser.add_argument("--workflow-id", default="", help="Optional workflow id filter")
        command_parser.add_argument("--template-id", default="", help="Optional template id filter")
        command_parser.add_argument("--tile-size", default="", help="Optional tile size filter, e.g. 1x1, 2x2, 7-cell")
        command_parser.add_argument("--asset-kind", default="", help="Optional asset kind filter: reference or template")
        command_parser.add_argument("--group", default="", help="Optional preset group filter")
        command_parser.add_argument("--limit", type=int, default=20)

    def add_map_workflow_args(
        command_parser: argparse.ArgumentParser,
        *,
        modes: tuple[str, ...],
        include_template: bool = False,
        include_road: bool = False,
        include_style_quad: bool = False,
    ) -> None:
        command_parser.add_argument("--prompt", required=True, help="Map tile requirement")
        command_parser.add_argument("--reference-image", action="append", default=[], help="Reference image; can be repeated")
        command_parser.add_argument("--mode", default="standard", choices=modes)
        if include_template:
            command_parser.add_argument("--template", default="", help="HD map template id")
        command_parser.add_argument("--similar-tiles", action="store_true", default=None)
        command_parser.add_argument("--no-similar-tiles", action="store_false", dest="similar_tiles", default=None)
        command_parser.add_argument("--tile-only", action="store_true", default=None)
        command_parser.add_argument("--no-tile-only", action="store_false", dest="tile_only", default=None)
        if include_road:
            command_parser.add_argument("--road-template-id", default="")
            command_parser.add_argument("--road-width", type=int, default=None)
        if include_style_quad:
            command_parser.add_argument("--style-name", default="")
            command_parser.add_argument("--style-description", default="")
            command_parser.add_argument("--top-left", default="")
            command_parser.add_argument("--top-right", default="")
            command_parser.add_argument("--bottom-left", default="")
            command_parser.add_argument("--bottom-right", default="")
        command_parser.add_argument("--project-id", default=None)
        command_parser.add_argument("--thread-id", default=None)

    bootstrap_status_parser = subparsers.add_parser("bootstrap-status", help="Show bootstrap runner update status")
    bootstrap_status_parser.add_argument("--check", action="store_true", help="Fetch and display the remote bootstrap manifest")

    skill_doc_parser = subparsers.add_parser("skill-doc", help="Print the latest Meowa game-assets skill guide")
    skill_doc_parser.add_argument("--topic", default="", help="Optional guide topic, such as pixel-gen, hd-gen, texture, or music")
    skill_doc_parser.add_argument("--task", default="", help="Optional short description of the current user request")
    skill_doc_parser.add_argument("--refresh", action="store_true", help="Ignore fresh cache and fetch the remote guide")
    add_if_missing(skill_doc_parser, "--api-base", default=argparse.SUPPRESS, help="API base URL")
    add_if_missing(skill_doc_parser, "--timeout", type=int, default=argparse.SUPPRESS, help="Per-request timeout in seconds")
    add_if_missing(skill_doc_parser, "--insecure", action="store_true", default=argparse.SUPPRESS, help="Disable TLS verification")

    skill_doc_status_parser = subparsers.add_parser("skill-doc-status", help="Show Meowa game-assets skill guide cache status")
    skill_doc_status_parser.add_argument("--topic", default="", help="Optional guide topic")
    skill_doc_status_parser.add_argument("--check", action="store_true", help="Fetch and display remote guide status")
    add_if_missing(skill_doc_status_parser, "--api-base", default=argparse.SUPPRESS, help="API base URL")
    add_if_missing(skill_doc_status_parser, "--timeout", type=int, default=argparse.SUPPRESS, help="Per-request timeout in seconds")
    add_if_missing(skill_doc_status_parser, "--insecure", action="store_true", default=argparse.SUPPRESS, help="Disable TLS verification")

    map_preset_search = subparsers.add_parser("map-reference-search", aliases=["map-preset-search"], help="Search reusable map preset images")
    add_shared_path_args(map_preset_search)
    add_map_preset_filter_args(map_preset_search)
    map_preset_search.add_argument("--download", action="store_true", help="Download matched presets instead of only printing JSON")

    map_preset_download = subparsers.add_parser("map-reference-download", aliases=["map-preset-download"], help="Download map presets by id or search filters")
    add_shared_path_args(map_preset_download)
    add_map_preset_filter_args(map_preset_download)
    map_preset_download.add_argument("--preset-id", action="append", default=[], help="Preset id to download; can be repeated")

    pixel_templates = subparsers.add_parser("pixel-gen-template-info", help="Get pixel-gen template info")
    add_shared_path_args(pixel_templates)

    pixel_submit = subparsers.add_parser("pixel-gen-submit", help="Submit a pixel-gen job")
    add_shared_path_args(pixel_submit)
    pixel_submit.add_argument("--template-name", required=True)
    pixel_submit.add_argument("--requirement", required=True)
    pixel_submit.add_argument("--template-config", default="{}", help="JSON object string")
    pixel_submit.add_argument("--job-name", default="")
    pixel_submit.add_argument("--resolution", default="", help=argparse.SUPPRESS)
    pixel_submit.add_argument("--aspect-ratio", default="1:1")
    pixel_submit.add_argument("--reference-file", default="", help="Optional user reference image sent as reference_file")

    pixel_run = subparsers.add_parser("pixel-gen-run", help="Submit and wait for pixel-gen")
    for action in pixel_submit._actions[1:]:
        if action.dest not in {"help"}:
            pixel_run._add_action(action)
    pixel_run.add_argument("--dry-run", action="store_true", help="Print planned request/output paths without submitting a job")
    add_shared_runtime_args(pixel_run)

    pixel_poll = subparsers.add_parser("pixel-gen-poll", help="Poll one pixel-gen job")
    add_shared_path_args(pixel_poll)
    pixel_poll.add_argument("--api-job-id", required=True)

    pixel_history = subparsers.add_parser("pixel-gen-history", help="Query pixel-gen history")
    add_shared_path_args(pixel_history)
    pixel_history.add_argument("--limit", type=int, default=20)
    pixel_history.add_argument("--offset", type=int, default=0)
    pixel_history.add_argument("--status", default="")

    pixel_download = subparsers.add_parser("pixel-gen-download", help="Download pixel-gen output")
    add_shared_path_args(pixel_download)
    pixel_download.add_argument("--api-job-id", required=True)
    pixel_download.add_argument("--output-index", type=int, default=None)

    pixel_cancel = subparsers.add_parser("pixel-gen-cancel", help="Cancel one pixel-gen job")
    add_shared_path_args(pixel_cancel)
    pixel_cancel.add_argument("--api-job-id", required=True)

    hd_templates = subparsers.add_parser("hd-gen-template-info", help="Get HD-gen template info")
    add_shared_path_args(hd_templates)

    hd_submit = subparsers.add_parser("hd-gen-submit", help="Submit an HD-gen job")
    add_shared_path_args(hd_submit)
    hd_submit.add_argument("--template-name", required=True)
    hd_submit.add_argument("--requirement", required=True)
    hd_submit.add_argument("--template-config", default="{}", help="JSON object string")
    hd_submit.add_argument("--job-name", default="")
    hd_submit.add_argument("--model-name", default="gemini-3.1-flash-image-preview")
    hd_submit.add_argument("--resolution", default="", help="Optional resolution; empty uses template default")
    hd_submit.add_argument("--aspect-ratio", default="1:1")
    hd_submit.add_argument("--temperature", type=float, default=0.0)
    hd_submit.add_argument("--hd-remove-bg-mode", default="", help="Optional: batch or single")
    hd_submit.add_argument("--include-base64", action="store_true")
    hd_submit.add_argument("--reference-file", default="", help="Optional single user reference image")
    hd_submit.add_argument("--reference-files", action="append", default=[], help="Optional user reference image; can be repeated")
    hd_submit.add_argument("--project-id", default=None)
    hd_submit.add_argument("--thread-id", default=None)

    hd_run = subparsers.add_parser("hd-gen-run", help="Submit and wait for HD-gen")
    for action in hd_submit._actions[1:]:
        if action.dest not in {"help"}:
            hd_run._add_action(action)
    add_shared_runtime_args(hd_run)

    hd_poll = subparsers.add_parser("hd-gen-poll", help="Poll one HD-gen job")
    add_shared_path_args(hd_poll)
    hd_poll.add_argument("--api-job-id", required=True)

    hd_history = subparsers.add_parser("hd-gen-history", help="Query HD-gen history")
    add_shared_path_args(hd_history)
    hd_history.add_argument("--limit", type=int, default=20)
    hd_history.add_argument("--offset", type=int, default=0)
    hd_history.add_argument("--status", default="")

    hd_download = subparsers.add_parser("hd-gen-download", help="Download HD-gen output")
    add_shared_path_args(hd_download)
    hd_download.add_argument("--api-job-id", required=True)
    hd_download.add_argument("--output-index", type=int, default=None)
    hd_download.add_argument("--preview", action="store_true", help="Download preview instead of final output")

    hd_cancel = subparsers.add_parser("hd-gen-cancel", help="Cancel one HD-gen job")
    add_shared_path_args(hd_cancel)
    hd_cancel.add_argument("--api-job-id", required=True)

    remove_bg_submit = subparsers.add_parser("remove-background-submit", help="Submit a remove-background job")
    add_shared_path_args(remove_bg_submit)
    remove_bg_submit.add_argument("--image-file", required=True)
    remove_bg_submit.add_argument("--method", default="hd")
    remove_bg_submit.add_argument("--is-white-bg", action="store_true", default=True)
    remove_bg_submit.add_argument("--no-is-white-bg", action="store_false", dest="is_white_bg")
    remove_bg_submit.add_argument("--prompt", default="")

    remove_bg_run = subparsers.add_parser("remove-background-run", help="Submit and wait for remove-background")
    for action in remove_bg_submit._actions[1:]:
        if action.dest not in {"help"}:
            remove_bg_run._add_action(action)
    add_shared_runtime_args(remove_bg_run)

    pixelate_submit = subparsers.add_parser("pixelate-submit", help="Submit a pixelate job")
    add_shared_path_args(pixelate_submit)
    pixelate_submit.add_argument("--image-file", required=True)
    pixelate_submit.add_argument("--pixel-size", default="")

    pixelate_run = subparsers.add_parser("pixelate-run", help="Submit and wait for pixelate")
    for action in pixelate_submit._actions[1:]:
        if action.dest not in {"help"}:
            pixelate_run._add_action(action)
    add_shared_runtime_args(pixelate_run)

    self_loop_submit = subparsers.add_parser("self-loop-submit", help="Submit a pixel_gen_self_loop job")
    add_shared_path_args(self_loop_submit)
    self_loop_submit.add_argument("--image-file", required=True)
    self_loop_submit.add_argument("--job-name", default="")
    self_loop_submit.add_argument("--resolution", default="1K")
    self_loop_submit.add_argument("--mode", choices=["basic", "full"], default="basic")
    self_loop_submit.add_argument("--direction", default="horizontal")

    self_loop_run = subparsers.add_parser("self-loop-run", help="Submit and wait for pixel_gen_self_loop")
    for action in self_loop_submit._actions[1:]:
        if action.dest not in {"help", "requirement"}:
            self_loop_run._add_action(action)
    add_shared_runtime_args(self_loop_run)

    sound_submit = subparsers.add_parser("sound-submit", aliases=["sfx-submit", "sound-effect-submit"], help="Submit an ElevenLabs sound-effect job")
    add_shared_path_args(sound_submit)
    sound_submit.add_argument("--prompt", required=True, help="Sound effect requirement")
    sound_submit.add_argument("--duration", type=float, default=2, help="0.5 or integer seconds from 1 to 10")
    sound_submit.add_argument("--loop", action="store_true", help="Request a loopable sound")
    sound_submit.add_argument("--sound-pack", action="store_true", help="Generate a pack of different sounds")
    sound_submit.add_argument("--variants", action="store_true", help="Generate variants of the same sound")
    sound_submit.add_argument("--count", type=int, default=4, help="Number of pack items or variants")
    sound_submit.add_argument("--language", default="en", help="Name language; prompt generation stays English")
    sound_submit.add_argument("--temperature", type=float, default=0.3, help="Prompt influence, 0 to 1")
    sound_submit.add_argument("--normalize-volume", action="store_true", default=True)
    sound_submit.add_argument("--no-normalize-volume", action="store_false", dest="normalize_volume")
    sound_submit.add_argument("--target-peak-db", type=float, default=-3.0)
    sound_submit.add_argument("--max-gain-db", type=float, default=36.0)
    sound_submit.add_argument("--provider-api-key", default="", help="Optional ElevenLabs API key; backend env is used when omitted")
    sound_submit.add_argument("--base-url", default="", help="Optional ElevenLabs base URL")
    sound_submit.add_argument("--project-id", default=None)
    sound_submit.add_argument("--thread-id", default=None)

    sound_run = subparsers.add_parser("sound-run", aliases=["sfx-run", "sound-effect-run"], help="Submit and wait for ElevenLabs sound effects")
    for action in sound_submit._actions[1:]:
        if action.dest not in {"help"}:
            sound_run._add_action(action)
    add_shared_runtime_args(sound_run)

    sound_poll = subparsers.add_parser("sound-poll", aliases=["sfx-poll", "sound-effect-poll"], help="Poll one sound-effect workflow job")
    add_shared_path_args(sound_poll)
    sound_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    texture_submit = subparsers.add_parser("texture-gen-submit", help="Submit a texture_gen job")
    add_shared_path_args(texture_submit)
    texture_submit.add_argument("--prompt", default="", help="Texture requirement")
    texture_submit.add_argument("--texture-name", action="append", default=[], help="Reference texture name; can be repeated or comma-separated")
    texture_submit.add_argument("--padding-mode", default="no_padding", choices=["no_padding", "padded"])
    texture_submit.add_argument("--edge-fill-pixels", type=int, default=1)
    texture_submit.add_argument("--self-loop", action="store_true", default=True)
    texture_submit.add_argument("--no-self-loop", action="store_false", dest="self_loop")
    texture_submit.add_argument("--project-id", default=None)
    texture_submit.add_argument("--thread-id", default=None)

    texture_run = subparsers.add_parser("texture-gen-run", help="Submit and wait for texture_gen")
    for action in texture_submit._actions[1:]:
        if action.dest not in {"help"}:
            texture_run._add_action(action)
    add_shared_runtime_args(texture_run)

    texture_poll = subparsers.add_parser("texture-gen-poll", help="Poll one texture_gen workflow job")
    add_shared_path_args(texture_poll)
    texture_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    tileset_submit = subparsers.add_parser("tileset-gen-submit", help="Submit a tileset_gen job")
    add_shared_path_args(tileset_submit)
    tileset_submit.add_argument("--prompt", default="", help="Foreground/background terrain requirement")
    tileset_submit.add_argument("--tileset-mode", default="dual-grid-15")
    tileset_submit.add_argument("--foreground-texture", default="", help="Optional foreground texture reference image")
    tileset_submit.add_argument("--background-texture", default="", help="Optional background texture reference image")
    tileset_submit.add_argument("--texture-reference-size", type=int, default=None)
    tileset_submit.add_argument("--texture-reference-mode", default="white_region_fill", choices=["white_region_fill", "texture_block_fill"])
    tileset_submit.add_argument("--project-id", default=None)
    tileset_submit.add_argument("--thread-id", default=None)

    tileset_run = subparsers.add_parser("tileset-gen-run", help="Submit and wait for tileset_gen")
    for action in tileset_submit._actions[1:]:
        if action.dest not in {"help"}:
            tileset_run._add_action(action)
    add_shared_runtime_args(tileset_run)

    tileset_poll = subparsers.add_parser("tileset-gen-poll", help="Poll one tileset_gen workflow job")
    add_shared_path_args(tileset_poll)
    tileset_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    isometric_submit = subparsers.add_parser(
        "isometric-gen-submit",
        aliases=["pixel-isometric-gen-submit"],
        help="Submit pixel_isometric_gen",
    )
    add_shared_path_args(isometric_submit)
    add_map_workflow_args(
        isometric_submit,
        modes=("standard", "edit", "tetraploid", "road"),
        include_road=True,
    )

    isometric_run = subparsers.add_parser(
        "isometric-gen-run",
        aliases=["pixel-isometric-gen-run"],
        help="Submit and wait for pixel_isometric_gen",
    )
    for action in isometric_submit._actions[1:]:
        if action.dest not in {"help"}:
            isometric_run._add_action(action)
    add_shared_runtime_args(isometric_run)

    isometric_poll = subparsers.add_parser(
        "isometric-gen-poll",
        aliases=["pixel-isometric-gen-poll"],
        help="Poll one pixel_isometric_gen workflow job",
    )
    add_shared_path_args(isometric_poll)
    isometric_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    hex_isometric_submit = subparsers.add_parser(
        "hex-isometric-gen-submit",
        aliases=["pixel-hex-isometric-gen-submit"],
        help="Submit pixel_hex_isometric_gen",
    )
    add_shared_path_args(hex_isometric_submit)
    add_map_workflow_args(
        hex_isometric_submit,
        modes=("standard", "edit", "tetraploid", "heptaploid"),
    )

    hex_isometric_run = subparsers.add_parser(
        "hex-isometric-gen-run",
        aliases=["pixel-hex-isometric-gen-run"],
        help="Submit and wait for pixel_hex_isometric_gen",
    )
    for action in hex_isometric_submit._actions[1:]:
        if action.dest not in {"help"}:
            hex_isometric_run._add_action(action)
    add_shared_runtime_args(hex_isometric_run)

    hex_isometric_poll = subparsers.add_parser(
        "hex-isometric-gen-poll",
        aliases=["pixel-hex-isometric-gen-poll"],
        help="Poll one pixel_hex_isometric_gen workflow job",
    )
    add_shared_path_args(hex_isometric_poll)
    hex_isometric_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    hd_isometric_submit = subparsers.add_parser("hd-isometric-gen-submit", help="Submit hd_isometric_gen")
    add_shared_path_args(hd_isometric_submit)
    add_map_workflow_args(
        hd_isometric_submit,
        modes=("standard", "tetraploid", "style_quad"),
        include_template=True,
        include_style_quad=True,
    )

    hd_isometric_run = subparsers.add_parser("hd-isometric-gen-run", help="Submit and wait for hd_isometric_gen")
    for action in hd_isometric_submit._actions[1:]:
        if action.dest not in {"help"}:
            hd_isometric_run._add_action(action)
    add_shared_runtime_args(hd_isometric_run)

    hd_isometric_poll = subparsers.add_parser("hd-isometric-gen-poll", help="Poll one hd_isometric_gen workflow job")
    add_shared_path_args(hd_isometric_poll)
    hd_isometric_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    hd_hex_isometric_submit = subparsers.add_parser("hd-hex-isometric-gen-submit", help="Submit hd_hex_isometric_gen")
    add_shared_path_args(hd_hex_isometric_submit)
    add_map_workflow_args(
        hd_hex_isometric_submit,
        modes=("standard", "tetraploid"),
        include_template=True,
    )

    hd_hex_isometric_run = subparsers.add_parser("hd-hex-isometric-gen-run", help="Submit and wait for hd_hex_isometric_gen")
    for action in hd_hex_isometric_submit._actions[1:]:
        if action.dest not in {"help"}:
            hd_hex_isometric_run._add_action(action)
    add_shared_runtime_args(hd_hex_isometric_run)

    hd_hex_isometric_poll = subparsers.add_parser("hd-hex-isometric-gen-poll", help="Poll one hd_hex_isometric_gen workflow job")
    add_shared_path_args(hd_hex_isometric_poll)
    hd_hex_isometric_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    music_submit = subparsers.add_parser("music-submit", help="Submit a music_generator job")
    add_shared_path_args(music_submit)
    music_submit.add_argument("--prompt", default="", help="Music requirement text; optional when reference images are provided")
    music_submit.add_argument("--audio-generate", action="store_true", help="Generate audio instead of prompt-only metadata")
    music_submit.add_argument("--demo", action="store_true", help="Use the lower-cost demo audio model when --audio-generate is set")
    music_submit.add_argument("--reference-image", action="append", default=[], help="Optional reference image; can be repeated")
    music_submit.add_argument("--project-id", default=None)
    music_submit.add_argument("--thread-id", default=None)

    music_run = subparsers.add_parser("music-run", help="Submit and wait for music_generator")
    for action in music_submit._actions[1:]:
        if action.dest not in {"help"}:
            music_run._add_action(action)
    add_shared_runtime_args(music_run)

    music_poll = subparsers.add_parser("music-poll", help="Poll one music/workflow job")
    add_shared_path_args(music_poll)
    music_poll.add_argument("--api-job-id", "--job-id", dest="api_job_id", required=True)

    gemini_post = subparsers.add_parser("gemini-post", help="Call a generic Gemini proxy POST endpoint")
    add_shared_path_args(gemini_post)
    gemini_post.add_argument(
        "--path",
        required=True,
        help=f"Gemini proxy path, e.g. v1beta/models/{DEFAULT_GEMINI_MODEL}:generateContent",
    )
    gemini_post.add_argument("--json-body", required=True, help="Raw JSON string")

    gemini_generate = subparsers.add_parser("gemini-generate-content", help="Call Gemini generateContent")
    add_shared_path_args(gemini_generate)
    gemini_generate.add_argument("--model", default=DEFAULT_GEMINI_MODEL)
    gemini_generate.add_argument("--text", default="", help="Prompt text; optional when --image-file is provided")
    gemini_generate.add_argument(
        "--image-file",
        "--reference-image",
        "--reference-file",
        dest="image_files",
        action="append",
        default=[],
        help="Reference image file sent as inline_data; can be repeated",
    )
    gemini_generate.add_argument("--generation-config", default="", help="JSON object string")

    credits_balance = subparsers.add_parser("credits-balance", help="Get current credits balance")
    add_shared_path_args(credits_balance)

    animate_submit_parser = subparsers.add_parser("animate-submit", help="Submit an animate job")
    add_shared_path_args(animate_submit_parser)
    animate_submit_parser.add_argument("--image-file", required=True)
    animate_submit_parser.add_argument("--prompt", default="")
    animate_submit_parser.add_argument("--is-pixel", action="store_true")
    animate_submit_parser.add_argument("--output-frames", type=int, default=8)
    animate_submit_parser.add_argument("--output-format", default="webp")

    animate_run_parser = subparsers.add_parser("animate-run", help="Submit and wait for animate")
    for action in animate_submit_parser._actions[1:]:
        if action.dest not in {"help"}:
            animate_run_parser._add_action(action)
    add_shared_runtime_args(animate_run_parser)

    animate_poll_parser = subparsers.add_parser("animate-poll", help="Poll one animate job")
    add_shared_path_args(animate_poll_parser)
    animate_poll_parser.add_argument("--api-job-id", required=True)

    return parser.parse_args()


def _parse_json_arg(raw: str, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return payload


def _read_dotenv_value(key: str) -> str:
    candidate_paths = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    seen: set[Path] = set()
    for path in candidate_paths:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        for line in resolved.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() != key:
                continue
            return value.strip().strip("'\"")
    return ""


def _resolve_auth_token(raw_api_key: str, raw_dev_key: str = "") -> str:
    dev_key = (raw_dev_key or "").strip()
    if dev_key:
        return f"x-dev-key:{dev_key}"

    env_dev_key = os.getenv(DEFAULT_DEV_KEY_ENV, "").strip() or os.getenv("DEV_API_KEY", "").strip()
    if env_dev_key:
        return f"x-dev-key:{env_dev_key}"

    dotenv_dev_key = _read_dotenv_value(DEFAULT_DEV_KEY_ENV).strip() or _read_dotenv_value("DEV_API_KEY").strip()
    if dotenv_dev_key:
        return f"x-dev-key:{dotenv_dev_key}"

    api_key = (raw_api_key or "").strip()
    if api_key:
        return api_key

    env_api_key = os.getenv(DEFAULT_API_KEY_ENV, "").strip()
    if env_api_key:
        return env_api_key

    dotenv_api_key = _read_dotenv_value(DEFAULT_API_KEY_ENV).strip()
    if dotenv_api_key:
        return dotenv_api_key

    raise ValueError(
        f"missing auth key: pass --api-key/--dev-key, set {DEFAULT_API_KEY_ENV}/{DEFAULT_DEV_KEY_ENV}, "
        f"or add {DEFAULT_API_KEY_ENV}=... or {DEFAULT_DEV_KEY_ENV}=... to .env"
    )

def main() -> int:
    _configure_stdio()
    _bootstrap_maybe_exec(sys.argv)
    args = parse_args()
    verify = not args.insecure
    if args.command == "bootstrap-status":
        payload = bootstrap_status(check_remote=args.check)
        payload["skill_doc"] = skill_doc_status(
            api_base=args.api_base,
            timeout=args.timeout,
            verify=verify,
            check_remote=args.check,
        )
        print(_format_json_for_display(payload))
        return 0
    if args.command == "skill-doc":
        payload = skill_doc(
            api_base=args.api_base,
            topic=args.topic,
            task=args.task,
            timeout=args.timeout,
            verify=verify,
            refresh=args.refresh,
        )
        warning = str(payload.get("warning") or "").strip()
        if warning:
            print(f"[WARN] skill doc fallback: {warning}", file=sys.stderr)
        print(str(payload.get("content") or ""))
        return 0
    if args.command == "skill-doc-status":
        print(_format_json_for_display(skill_doc_status(
            api_base=args.api_base,
            topic=args.topic,
            timeout=args.timeout,
            verify=verify,
            check_remote=args.check,
        )))
        return 0

    started_at = datetime.now().isoformat(timespec="seconds")
    run_dir = _create_run_dir(args.work_dir, args.command)
    effective_output_dir = _resolve_output_dir(args.output_dir, run_dir)
    try:
        no_auth_commands = {
            "map-reference-search",
            "map-preset-search",
            "map-reference-download",
            "map-preset-download",
        }
        needs_api_key = args.command not in no_auth_commands and not (
            args.command == "pixel-gen-run" and getattr(args, "dry_run", False)
        )
        args.api_key = (
            _resolve_auth_token(args.api_key, getattr(args, "dev_key", ""))
            if needs_api_key
            else str(args.api_key or "").strip()
        )

        if args.command in {"map-reference-search", "map-preset-search"}:
            if args.download:
                search_payload, downloads = download_map_presets(
                    api_base=args.api_base,
                    query=args.query,
                    workflow_id=args.workflow_id,
                    template_id=args.template_id,
                    tile_size=args.tile_size,
                    asset_kind=args.asset_kind,
                    group=args.group,
                    limit=args.limit,
                    output_dir=str(effective_output_dir),
                    timeout=args.timeout,
                    verify=verify,
                )
                _write_meta(
                    run_dir=run_dir,
                    started_at=started_at,
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                    args=args,
                    request_payload={
                        "query": args.query,
                        "workflow_id": args.workflow_id,
                        "template_id": args.template_id,
                        "tile_size": args.tile_size,
                        "asset_kind": args.asset_kind,
                        "group": args.group,
                        "limit": args.limit,
                    },
                    response_payload=search_payload,
                    downloads=downloads,
                    effective_output_dir=str(effective_output_dir),
                )
                print(f"[INFO] saved_dir={effective_output_dir}")
                print(_format_json_for_display(search_payload))
                return 0

            payload = search_map_presets(
                api_base=args.api_base,
                query=args.query,
                workflow_id=args.workflow_id,
                template_id=args.template_id,
                tile_size=args.tile_size,
                asset_kind=args.asset_kind,
                group=args.group,
                limit=args.limit,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "query": args.query,
                    "workflow_id": args.workflow_id,
                    "template_id": args.template_id,
                    "tile_size": args.tile_size,
                    "asset_kind": args.asset_kind,
                    "group": args.group,
                    "limit": args.limit,
                },
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command in {"map-reference-download", "map-preset-download"}:
            search_payload, downloads = download_map_presets(
                api_base=args.api_base,
                query=args.query,
                preset_ids=list(args.preset_id or []),
                workflow_id=args.workflow_id,
                template_id=args.template_id,
                tile_size=args.tile_size,
                asset_kind=args.asset_kind,
                group=args.group,
                limit=args.limit,
                output_dir=str(effective_output_dir),
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "preset_ids": list(args.preset_id or []),
                    "query": args.query,
                    "workflow_id": args.workflow_id,
                    "template_id": args.template_id,
                    "tile_size": args.tile_size,
                    "asset_kind": args.asset_kind,
                    "group": args.group,
                    "limit": args.limit,
                },
                response_payload=search_payload,
                downloads=downloads,
                effective_output_dir=str(effective_output_dir),
            )
            print(f"[INFO] saved_dir={effective_output_dir}")
            print(_format_json_for_display(search_payload))
            return 0

        if args.command == "pixel-gen-template-info":
            payload = pixel_gen_template_info(
                api_base=args.api_base,
                api_key=args.api_key,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "pixel-gen-submit":
            payload = submit_pixel_gen(
                api_base=args.api_base,
                api_key=args.api_key,
                template_name=args.template_name,
                requirement=args.requirement,
                template_config=_parse_json_arg(args.template_config, name="template_config"),
                job_name=args.job_name,
                aspect_ratio=args.aspect_ratio,
                reference_file=args.reference_file,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "template_name": args.template_name,
                    "requirement": args.requirement,
                    "template_config": _parse_json_arg(args.template_config, name="template_config"),
                    "job_name": args.job_name,
                    "aspect_ratio": args.aspect_ratio,
                    "reference_file": args.reference_file,
                },
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "pixel-gen-run":
            template_config = _parse_json_arg(args.template_config, name="template_config")
            request_payload = {
                "template_name": args.template_name,
                "requirement": args.requirement,
                "template_config": template_config,
                "job_name": args.job_name,
                "aspect_ratio": args.aspect_ratio,
                "reference_file": args.reference_file,
            }
            predicted_output_dir = _predict_saved_dir(effective_output_dir, args.job_name or args.requirement)
            print(f"[INFO] planned_output_dir={predicted_output_dir}")
            if args.dry_run:
                dry_payload = {
                    "dry_run": True,
                    "submit_endpoint": _normalize_base_url(args.api_base, "/api/pixel-gen"),
                    "planned_output_dir": str(predicted_output_dir),
                    "request": request_payload,
                }
                _write_meta(
                    run_dir=run_dir,
                    started_at=started_at,
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                    args=args,
                    request_payload=request_payload,
                    response_payload=dry_payload,
                    downloads=[],
                    effective_output_dir=str(predicted_output_dir),
                )
                print(_format_json_for_display(dry_payload))
                return 0
            submit_payload = submit_pixel_gen(
                api_base=args.api_base,
                api_key=args.api_key,
                template_name=args.template_name,
                requirement=args.requirement,
                template_config=template_config,
                job_name=args.job_name,
                aspect_ratio=args.aspect_ratio,
                reference_file=args.reference_file,
                timeout=args.timeout,
                verify=verify,
            )
            api_job_id = str(submit_payload.get("api_job_id") or "").strip()
            if not api_job_id:
                raise RuntimeError("pixel-gen submit response missing api_job_id")
            _save_json(predicted_output_dir / "submit_response.json", _sanitize_for_meta(submit_payload))
            print(f"[INFO] submitted api_job_id={api_job_id}")
            print(f"[INFO] waiting_for_completion poll_interval={args.poll_interval}s max_wait={args.max_wait}s")
            final_payload = wait_pixel_gen_job(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=api_job_id,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=args.job_name or args.requirement,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "pixel-gen-poll":
            payload = poll_pixel_gen_job(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "pixel-gen-history":
            payload = pixel_gen_history(
                api_base=args.api_base,
                api_key=args.api_key,
                limit=args.limit,
                offset=args.offset,
                status=args.status,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"limit": args.limit, "offset": args.offset, "status": args.status},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "pixel-gen-download":
            path = pixel_gen_download(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                output_dir=args.output_dir or str(effective_output_dir),
                output_index=args.output_index,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id, "output_dir": args.output_dir, "output_index": args.output_index},
                response_payload={"downloaded_path": str(path)},
                downloads=[{"type": "explicit_download", "path": str(path)}],
                effective_output_dir=str(path.parent),
            )
            print(f"[INFO] downloaded={path}")
            return 0

        if args.command == "pixel-gen-cancel":
            payload = pixel_gen_cancel(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "hd-gen-template-info":
            payload = hd_gen_template_info(
                api_base=args.api_base,
                api_key=args.api_key,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "hd-gen-submit":
            template_config = _parse_json_arg(args.template_config, name="template_config")
            request_payload = {
                "template_name": args.template_name,
                "requirement": args.requirement,
                "template_config": template_config,
                "job_name": args.job_name,
                "model_name": args.model_name,
                "resolution": args.resolution,
                "aspect_ratio": args.aspect_ratio,
                "temperature": args.temperature,
                "hd_remove_bg_mode": args.hd_remove_bg_mode,
                "include_base64": args.include_base64,
                "reference_file": args.reference_file,
                "reference_files": list(args.reference_files or []),
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            payload = submit_hd_gen(
                api_base=args.api_base,
                api_key=args.api_key,
                template_name=args.template_name,
                requirement=args.requirement,
                template_config=template_config,
                job_name=args.job_name,
                model_name=args.model_name,
                resolution=args.resolution,
                aspect_ratio=args.aspect_ratio,
                temperature=args.temperature,
                hd_remove_bg_mode=args.hd_remove_bg_mode,
                include_base64=args.include_base64,
                reference_file=args.reference_file,
                reference_files=list(args.reference_files or []),
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "hd-gen-run":
            template_config = _parse_json_arg(args.template_config, name="template_config")
            slug_seed = args.job_name or args.requirement
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, slug_seed)}")
            request_payload = {
                "template_name": args.template_name,
                "requirement": args.requirement,
                "template_config": template_config,
                "job_name": args.job_name,
                "model_name": args.model_name,
                "resolution": args.resolution,
                "aspect_ratio": args.aspect_ratio,
                "temperature": args.temperature,
                "hd_remove_bg_mode": args.hd_remove_bg_mode,
                "include_base64": args.include_base64,
                "reference_file": args.reference_file,
                "reference_files": list(args.reference_files or []),
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            submit_payload, final_payload = run_hd_gen(
                api_base=args.api_base,
                api_key=args.api_key,
                template_name=args.template_name,
                requirement=args.requirement,
                template_config=template_config,
                job_name=args.job_name,
                model_name=args.model_name,
                resolution=args.resolution,
                aspect_ratio=args.aspect_ratio,
                temperature=args.temperature,
                hd_remove_bg_mode=args.hd_remove_bg_mode,
                include_base64=args.include_base64,
                reference_file=args.reference_file,
                reference_files=list(args.reference_files or []),
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=slug_seed,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "hd-gen-poll":
            payload = poll_hd_gen_job(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                timeout=args.timeout,
                verify=verify,
            )
            downloads: list[dict[str, Any]] = []
            effective_poll_output_dir = Path(str(effective_output_dir)).expanduser()
            if str(payload.get("status") or "").strip().lower() in TERMINAL_JOB_STATUSES:
                effective_poll_output_dir, downloads = _save_run_outputs(
                    output_root=str(effective_output_dir),
                    slug_seed=args.api_job_id,
                    submit_payload={"api_job_id": args.api_job_id},
                    final_payload=payload,
                    timeout=args.timeout,
                    verify=verify,
                    api_key=args.api_key,
                    no_download=args.no_download,
                )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id},
                response_payload=payload,
                downloads=downloads,
                effective_output_dir=str(effective_poll_output_dir),
            )
            if downloads:
                print(f"[INFO] saved_dir={effective_poll_output_dir}")
            print(_format_json_for_display(payload))
            return 0

        if args.command == "hd-gen-history":
            payload = hd_gen_history(
                api_base=args.api_base,
                api_key=args.api_key,
                limit=args.limit,
                offset=args.offset,
                status=args.status,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"limit": args.limit, "offset": args.offset, "status": args.status},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "hd-gen-download":
            path = hd_gen_download(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                output_dir=args.output_dir or str(effective_output_dir),
                output_index=args.output_index,
                preview=args.preview,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id, "output_index": args.output_index, "preview": args.preview},
                response_payload={"downloaded_path": str(path)},
                downloads=[{"type": "explicit_download", "path": str(path)}],
                effective_output_dir=str(path.parent),
            )
            print(f"[INFO] downloaded={path}")
            return 0

        if args.command == "hd-gen-cancel":
            payload = hd_gen_cancel(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "remove-background-submit":
            payload = submit_remove_background(
                api_base=args.api_base,
                api_key=args.api_key,
                image_file=args.image_file,
                method=args.method,
                is_white_bg=args.is_white_bg,
                prompt=args.prompt,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "image_file": args.image_file,
                    "method": args.method,
                    "is_white_bg": args.is_white_bg,
                    "prompt": args.prompt,
                },
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "remove-background-run":
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, args.prompt or Path(args.image_file).stem)}")
            submit_payload, final_payload = run_remove_background(
                api_base=args.api_base,
                api_key=args.api_key,
                image_file=args.image_file,
                method=args.method,
                is_white_bg=args.is_white_bg,
                prompt=args.prompt,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=args.prompt or Path(args.image_file).stem,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "image_file": args.image_file,
                    "method": args.method,
                    "is_white_bg": args.is_white_bg,
                    "prompt": args.prompt,
                },
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "pixelate-submit":
            payload = submit_pixelate(
                api_base=args.api_base,
                api_key=args.api_key,
                image_file=args.image_file,
                pixel_size=args.pixel_size,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"image_file": args.image_file},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "pixelate-run":
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, Path(args.image_file).stem)}")
            submit_payload, final_payload = run_pixelate(
                api_base=args.api_base,
                api_key=args.api_key,
                image_file=args.image_file,
                pixel_size=args.pixel_size,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=Path(args.image_file).stem,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"image_file": args.image_file},
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "self-loop-submit":
            payload = submit_pixel_gen_self_loop(
                api_base=args.api_base,
                api_key=args.api_key,
                image_file=args.image_file,
                job_name=args.job_name,
                resolution=args.resolution,
                mode=args.mode,
                direction=args.direction,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "image_file": args.image_file,
                    "mode": args.mode,
                    "direction": args.direction,
                },
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "self-loop-run":
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, args.job_name or Path(args.image_file).stem)}")
            submit_payload, final_payload = run_pixel_gen_self_loop(
                api_base=args.api_base,
                api_key=args.api_key,
                image_file=args.image_file,
                job_name=args.job_name,
                resolution=args.resolution,
                mode=args.mode,
                direction=args.direction,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=args.job_name or Path(args.image_file).stem,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "image_file": args.image_file,
                    "mode": args.mode,
                    "direction": args.direction,
                },
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command in {"sound-submit", "sfx-submit", "sound-effect-submit"}:
            request_payload = {
                "prompt": args.prompt,
                "duration": args.duration,
                "loop": args.loop,
                "sound_pack": args.sound_pack,
                "variants": args.variants,
                "count": args.count,
                "language": args.language,
                "temperature": args.temperature,
                "normalize_volume": args.normalize_volume,
                "target_peak_db": args.target_peak_db,
                "max_gain_db": args.max_gain_db,
                "provider_api_key": args.provider_api_key,
                "base_url": args.base_url,
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            payload = submit_sound_effect_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                duration=args.duration,
                loop=args.loop,
                sound_pack=args.sound_pack,
                variants=args.variants,
                count=args.count,
                language=args.language,
                temperature=args.temperature,
                normalize_volume=args.normalize_volume,
                target_peak_db=args.target_peak_db,
                max_gain_db=args.max_gain_db,
                provider_api_key=args.provider_api_key,
                base_url=args.base_url,
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command in {"sound-run", "sfx-run", "sound-effect-run"}:
            slug_seed = args.prompt
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, slug_seed)}")
            request_payload = {
                "prompt": args.prompt,
                "duration": args.duration,
                "loop": args.loop,
                "sound_pack": args.sound_pack,
                "variants": args.variants,
                "count": args.count,
                "language": args.language,
                "temperature": args.temperature,
                "normalize_volume": args.normalize_volume,
                "target_peak_db": args.target_peak_db,
                "max_gain_db": args.max_gain_db,
                "provider_api_key": args.provider_api_key,
                "base_url": args.base_url,
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            submit_payload, final_payload = run_sound_effect_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                duration=args.duration,
                loop=args.loop,
                sound_pack=args.sound_pack,
                variants=args.variants,
                count=args.count,
                language=args.language,
                temperature=args.temperature,
                normalize_volume=args.normalize_volume,
                target_peak_db=args.target_peak_db,
                max_gain_db=args.max_gain_db,
                provider_api_key=args.provider_api_key,
                base_url=args.base_url,
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=slug_seed,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command in {
            "sound-poll",
            "sfx-poll",
            "sound-effect-poll",
            "texture-gen-poll",
            "tileset-gen-poll",
        } or args.command in MAP_WORKFLOW_POLL_COMMANDS:
            payload = poll_job(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                timeout=args.timeout,
                verify=verify,
            )
            downloads: list[dict[str, Any]] = []
            effective_poll_output_dir = Path(str(effective_output_dir)).expanduser()
            if str(payload.get("status") or "").strip().lower() in TERMINAL_JOB_STATUSES:
                effective_poll_output_dir, downloads = _save_run_outputs(
                    output_root=str(effective_output_dir),
                    slug_seed=args.api_job_id,
                    submit_payload={"api_job_id": args.api_job_id},
                    final_payload=payload,
                    timeout=args.timeout,
                    verify=verify,
                    api_key=args.api_key,
                    no_download=args.no_download,
                )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id},
                response_payload=payload,
                downloads=downloads,
                effective_output_dir=str(effective_poll_output_dir),
            )
            if downloads:
                print(f"[INFO] saved_dir={effective_poll_output_dir}")
            print(_format_json_for_display(payload))
            return 0

        if args.command == "texture-gen-submit":
            request_payload = {
                "prompt": args.prompt,
                "texture_names": list(args.texture_name or []),
                "padding_mode": args.padding_mode,
                "edge_fill_pixels": args.edge_fill_pixels,
                "self_loop": args.self_loop,
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            payload = submit_texture_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                texture_names=list(args.texture_name or []),
                padding_mode=args.padding_mode,
                edge_fill_pixels=args.edge_fill_pixels,
                self_loop=args.self_loop,
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "texture-gen-run":
            slug_seed = args.prompt or "texture"
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, slug_seed)}")
            request_payload = {
                "prompt": args.prompt,
                "texture_names": list(args.texture_name or []),
                "padding_mode": args.padding_mode,
                "edge_fill_pixels": args.edge_fill_pixels,
                "self_loop": args.self_loop,
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            submit_payload, final_payload = run_texture_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                texture_names=list(args.texture_name or []),
                padding_mode=args.padding_mode,
                edge_fill_pixels=args.edge_fill_pixels,
                self_loop=args.self_loop,
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=slug_seed,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "tileset-gen-submit":
            request_payload = {
                "prompt": args.prompt,
                "tileset_mode": args.tileset_mode,
                "foreground_texture": args.foreground_texture,
                "background_texture": args.background_texture,
                "texture_reference_size": args.texture_reference_size,
                "texture_reference_mode": args.texture_reference_mode,
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            payload = submit_tileset_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                tileset_mode=args.tileset_mode,
                foreground_texture=args.foreground_texture,
                background_texture=args.background_texture,
                texture_reference_size=args.texture_reference_size,
                texture_reference_mode=args.texture_reference_mode,
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "tileset-gen-run":
            slug_seed = args.prompt or "tileset"
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, slug_seed)}")
            request_payload = {
                "prompt": args.prompt,
                "tileset_mode": args.tileset_mode,
                "foreground_texture": args.foreground_texture,
                "background_texture": args.background_texture,
                "texture_reference_size": args.texture_reference_size,
                "texture_reference_mode": args.texture_reference_mode,
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            submit_payload, final_payload = run_tileset_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                tileset_mode=args.tileset_mode,
                foreground_texture=args.foreground_texture,
                background_texture=args.background_texture,
                texture_reference_size=args.texture_reference_size,
                texture_reference_mode=args.texture_reference_mode,
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=slug_seed,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command in MAP_WORKFLOW_COMMANDS and args.command not in MAP_WORKFLOW_POLL_COMMANDS:
            workflow_id = MAP_WORKFLOW_COMMANDS[args.command]
            reference_images = list(getattr(args, "reference_image", []) or [])
            request_payload = {
                "workflow_id": workflow_id,
                "prompt": args.prompt,
                "reference_images": reference_images,
                "mode": args.mode,
                "template": getattr(args, "template", ""),
                "similar_tiles": getattr(args, "similar_tiles", None),
                "tile_only": getattr(args, "tile_only", None),
                "road_template_id": getattr(args, "road_template_id", ""),
                "road_width": getattr(args, "road_width", None),
                "style_name": getattr(args, "style_name", ""),
                "style_description": getattr(args, "style_description", ""),
                "top_left": getattr(args, "top_left", ""),
                "top_right": getattr(args, "top_right", ""),
                "bottom_left": getattr(args, "bottom_left", ""),
                "bottom_right": getattr(args, "bottom_right", ""),
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            if args.command.endswith("-submit"):
                payload = submit_map_workflow(
                    api_base=args.api_base,
                    api_key=args.api_key,
                    workflow_id=workflow_id,
                    prompt=args.prompt,
                    reference_images=reference_images,
                    mode=args.mode,
                    template=getattr(args, "template", ""),
                    similar_tiles=getattr(args, "similar_tiles", None),
                    tile_only=getattr(args, "tile_only", None),
                    road_template_id=getattr(args, "road_template_id", ""),
                    road_width=getattr(args, "road_width", None),
                    style_name=getattr(args, "style_name", ""),
                    style_description=getattr(args, "style_description", ""),
                    top_left=getattr(args, "top_left", ""),
                    top_right=getattr(args, "top_right", ""),
                    bottom_left=getattr(args, "bottom_left", ""),
                    bottom_right=getattr(args, "bottom_right", ""),
                    project_id=args.project_id,
                    thread_id=args.thread_id,
                    timeout=args.timeout,
                    verify=verify,
                )
                _write_meta(
                    run_dir=run_dir,
                    started_at=started_at,
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                    args=args,
                    request_payload=request_payload,
                    response_payload=payload,
                    downloads=[],
                    effective_output_dir=str(effective_output_dir),
                )
                print(_format_json_for_display(payload))
                return 0

            slug_seed = args.prompt or workflow_id
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, slug_seed)}")
            submit_payload, final_payload = run_map_workflow(
                api_base=args.api_base,
                api_key=args.api_key,
                workflow_id=workflow_id,
                prompt=args.prompt,
                reference_images=reference_images,
                mode=args.mode,
                template=getattr(args, "template", ""),
                similar_tiles=getattr(args, "similar_tiles", None),
                tile_only=getattr(args, "tile_only", None),
                road_template_id=getattr(args, "road_template_id", ""),
                road_width=getattr(args, "road_width", None),
                style_name=getattr(args, "style_name", ""),
                style_description=getattr(args, "style_description", ""),
                top_left=getattr(args, "top_left", ""),
                top_right=getattr(args, "top_right", ""),
                bottom_left=getattr(args, "bottom_left", ""),
                bottom_right=getattr(args, "bottom_right", ""),
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=slug_seed,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "music-submit":
            request_payload = {
                "prompt": args.prompt,
                "audio_generate": args.audio_generate,
                "demo": args.demo,
                "reference_images": list(args.reference_image or []),
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            payload = submit_music_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                audio_generate=args.audio_generate,
                demo=args.demo,
                reference_images=list(args.reference_image or []),
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "music-run":
            slug_seed = args.prompt or (Path(args.reference_image[0]).stem if args.reference_image else "music")
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, slug_seed)}")
            request_payload = {
                "prompt": args.prompt,
                "audio_generate": args.audio_generate,
                "demo": args.demo,
                "reference_images": list(args.reference_image or []),
                "project_id": args.project_id,
                "thread_id": args.thread_id,
            }
            submit_payload, final_payload = run_music_generator(
                api_base=args.api_base,
                api_key=args.api_key,
                prompt=args.prompt,
                audio_generate=args.audio_generate,
                demo=args.demo,
                reference_images=list(args.reference_image or []),
                project_id=args.project_id,
                thread_id=args.thread_id,
                timeout=args.timeout,
                max_wait=args.max_wait,
                poll_interval=args.poll_interval,
                verify=verify,
            )
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=slug_seed,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload=request_payload,
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "music-poll":
            payload = poll_job(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                timeout=args.timeout,
                verify=verify,
            )
            downloads: list[dict[str, Any]] = []
            effective_poll_output_dir = Path(str(effective_output_dir)).expanduser()
            if str(payload.get("status") or "").strip().lower() in TERMINAL_JOB_STATUSES:
                effective_poll_output_dir, downloads = _save_run_outputs(
                    output_root=str(effective_output_dir),
                    slug_seed=args.api_job_id,
                    submit_payload={"api_job_id": args.api_job_id},
                    final_payload=payload,
                    timeout=args.timeout,
                    verify=verify,
                    api_key=args.api_key,
                    no_download=args.no_download,
                )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id},
                response_payload=payload,
                downloads=downloads,
                effective_output_dir=str(effective_poll_output_dir),
            )
            if downloads:
                print(f"[INFO] saved_dir={effective_poll_output_dir}")
            print(_format_json_for_display(payload))
            return 0

        if args.command == "gemini-post":
            payload = gemini_proxy_request(
                api_base=args.api_base,
                api_key=args.api_key,
                path=args.path,
                method="POST",
                json_body=_parse_json_arg(args.json_body, name="json_body"),
                timeout=args.timeout,
                verify=verify,
            )
            output_dir, downloads = _save_gemini_response_assets(
                payload=payload,
                output_dir=str(effective_output_dir),
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"path": args.path, "json_body": _parse_json_arg(args.json_body, name="json_body")},
                response_payload=payload,
                downloads=downloads,
                effective_output_dir=str(output_dir or effective_output_dir),
            )
            if output_dir is not None:
                print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(payload))
            return 0

        if args.command == "gemini-generate-content":
            generation_config = _parse_json_arg(args.generation_config or "{}", name="generation_config")
            contents = build_gemini_generate_content_contents(
                text=args.text,
                image_files=list(args.image_files or []),
            )
            payload = gemini_generate_content(
                api_base=args.api_base,
                api_key=args.api_key,
                model=args.model,
                contents=contents,
                generation_config=generation_config or None,
                timeout=args.timeout,
                verify=verify,
            )
            output_dir, downloads = _save_gemini_response_assets(
                payload=payload,
                output_dir=str(effective_output_dir),
                timeout=args.timeout,
                verify=verify,
                api_key=args.api_key,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={
                    "model": args.model,
                    "text": args.text,
                    "image_files": list(args.image_files or []),
                    "generation_config": generation_config,
                },
                response_payload=payload,
                downloads=downloads,
                effective_output_dir=str(output_dir or effective_output_dir),
            )
            if output_dir is not None:
                print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(payload))
            return 0

        if args.command == "credits-balance":
            payload = get_credits_balance(
                api_base=args.api_base,
                api_key=args.api_key,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "animate-submit":
            payload = submit_animate(
                api_base=args.api_base,
                api_key=args.api_key,
                image_data_url=image_file_to_data_url(args.image_file),
                prompt=args.prompt,
                is_pixel=args.is_pixel,
                output_frames=args.output_frames,
                output_format=args.output_format,
                timeout=args.timeout,
                verify=verify,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"image_file": args.image_file, "prompt": args.prompt, "is_pixel": args.is_pixel},
                response_payload=payload,
                downloads=[],
                effective_output_dir=str(effective_output_dir),
            )
            print(_format_json_for_display(payload))
            return 0

        if args.command == "animate-run":
            print(f"[INFO] planned_output_dir={_predict_saved_dir(effective_output_dir, args.prompt or Path(args.image_file).stem)}")
            submit_payload = submit_animate(
                api_base=args.api_base,
                api_key=args.api_key,
                image_data_url=image_file_to_data_url(args.image_file),
                prompt=args.prompt,
                is_pixel=args.is_pixel,
                output_frames=args.output_frames,
                output_format=args.output_format,
                timeout=args.timeout,
                verify=verify,
            )
            api_job_id = str(submit_payload.get("api_job_id") or "").strip()
            if not api_job_id:
                raise RuntimeError("animate submit response missing api_job_id")
            print(f"[INFO] submitted api_job_id={api_job_id}")
            try:
                final_payload = wait_animate_job(
                    api_base=args.api_base,
                    api_key=args.api_key,
                    api_job_id=api_job_id,
                    timeout=args.timeout,
                    max_wait=args.max_wait,
                    poll_interval=args.poll_interval,
                    verify=verify,
                )
            except (RuntimeError, TimeoutError) as exc:
                output_dir = Path(str(effective_output_dir)).expanduser() / _safe_slug(args.prompt or Path(args.image_file).stem)
                _save_json(output_dir / "submit_response.json", _sanitize_for_meta(submit_payload))
                downloads = [{"type": "json", "path": str(output_dir / "submit_response.json")}]
                _write_meta(
                    run_dir=run_dir,
                    started_at=started_at,
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                    args=args,
                    request_payload={"image_file": args.image_file, "prompt": args.prompt, "is_pixel": args.is_pixel},
                    response_payload={"submit": submit_payload},
                    downloads=downloads,
                    effective_output_dir=str(output_dir),
                    error=str(exc),
                )
                print(f"[WARN] animate submitted but polling did not complete: {exc}")
                print(f"[INFO] saved_dir={output_dir}")
                print(_format_json_for_display(submit_payload))
                return 1
            output_dir, downloads = _save_run_outputs(
                output_root=str(effective_output_dir),
                slug_seed=args.prompt or Path(args.image_file).stem,
                submit_payload=submit_payload,
                final_payload=final_payload,
                timeout=args.timeout,
                verify=verify,
                no_download=args.no_download,
            )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"image_file": args.image_file, "prompt": args.prompt, "is_pixel": args.is_pixel},
                response_payload={"submit": submit_payload, "final": final_payload},
                downloads=downloads,
                effective_output_dir=str(output_dir),
            )
            print(f"[INFO] saved_dir={output_dir}")
            print(_format_json_for_display(final_payload))
            return 0

        if args.command == "animate-poll":
            payload = poll_animate_job(
                api_base=args.api_base,
                api_key=args.api_key,
                api_job_id=args.api_job_id,
                timeout=args.timeout,
                verify=verify,
            )
            downloads: list[dict[str, Any]] = []
            effective_poll_output_dir = Path(str(effective_output_dir)).expanduser()
            if str(payload.get("status") or "").strip().lower() in SUCCESS_ANIMATE_STATUSES:
                effective_poll_output_dir, downloads = _save_run_outputs(
                    output_root=str(effective_output_dir),
                    slug_seed=args.api_job_id,
                    submit_payload={"api_job_id": args.api_job_id},
                    final_payload=payload,
                    timeout=args.timeout,
                    verify=verify,
                    no_download=args.no_download,
                )
            _write_meta(
                run_dir=run_dir,
                started_at=started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                args=args,
                request_payload={"api_job_id": args.api_job_id},
                response_payload=payload,
                downloads=downloads,
                effective_output_dir=str(effective_poll_output_dir),
            )
            if downloads:
                print(f"[INFO] saved_dir={effective_poll_output_dir}")
            print(_format_json_for_display(payload))
            return 0

        print(f"[ERROR] unknown command: {args.command}", file=sys.stderr)
        return 2
    except (RuntimeError, ValueError, FileNotFoundError, TimeoutError) as exc:
        _write_meta(
            run_dir=run_dir,
            started_at=started_at,
            finished_at=datetime.now().isoformat(timespec="seconds"),
            args=args,
            request_payload={},
            response_payload=None,
            downloads=[],
            effective_output_dir=str(effective_output_dir),
            error=str(exc),
        )
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
