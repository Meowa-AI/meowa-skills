---
name: game-assets
version: "2026.07.15.2"
description: Create, edit, and pipeline game assets with Meowa for pixel sprites, general large pixel characters/assets, character eight-direction multi-view sheets, HD assets, backgrounds, UI sheets and HUD elements, seamless loops, texture tiles, dual-grid tilesets, reusable map presets, isometric and hex map tiles, background removal, pixel cleanup, simple animation, sound effects, and music/BGM generation. Use when Codex needs to produce or refine game art or audio in this project, especially when choosing Meowa commands, searching preset map assets before generation, sizing canvases, selecting templates, generating UI sheets, generating music or SFX audio, or turning generated assets into game-ready files.
---

# Meowa Game Assets

This skill is a stable loader for the current Meowa game-assets guide.

## Required First Step

Before choosing any Meowa command or workflow, fetch the latest guide:

```bash
python3 meowart_api.py skill-doc --task "<brief user request>"
```

If you are already in the `skills/game-assets/` directory, use:

```bash
python3 ./meowart_api.py skill-doc --task "<brief user request>"
```

If you are calling the script from the skill repository root, use:

```bash
python3 skills/game-assets/meowart_api.py skill-doc --task "<brief user request>"
```

Follow the returned Markdown for command selection, API details, templates,
output directories, and validation steps. The command automatically falls back
to bundled `meowart_api.md` if the remote guide is unavailable.

## Diagnostics

Use these commands when the dynamic guide or runner version needs inspection:

```bash
python3 meowart_api.py skill-doc-status --check
python3 meowart_api.py bootstrap-status --check
```

`meowart_api.py` also has a bootstrap wrapper. Normal command runs silently
check the remote runner manifest, download a newer checksummed runner when
available, and execute that cached runner. This updates the CLI runner only.
Changes to this loader file still require reinstalling/updating the skill and
restarting Codex.

## Fixed Rules

- Do not expose API keys, developer keys, signed URLs, or other secrets in chat.
- Prefer environment variables or a local `.env` for credentials.
- Do not call bare `/generate` or `/api/generate`; use the current guide for the correct Meowa endpoint.
- For pixel assets, previews and manual resizing must use nearest-neighbor sampling.
- Do not manually shrink pixel art for display; if a smaller final asset is needed, use the workflow or post-processing path specified by the current guide.
- Generated outputs should be placed in an explicit task directory so the files are easy to inspect and reuse.
- `*-run` and `*-poll` may download only exact final-output fields returned for frontend use. Never download template, generated-grid, source/reference, metadata, manifest, stage, or debug URLs from a job payload; a public bucket or signed URL does not make an intermediate an output.
- Never persist a raw job/provider response. `submit_response.json`, `job_response.json`, `meta.json`, terminal generation output, and Gemini output manifests must contain only sanitized final-output references and safe status fields; omit intermediate JSON, metadata/manifests, server paths, signed/non-final URLs, and inline/base64 data.
- Media downloads must verify an `image/*`, `audio/*`, or `video/*` Content-Type before writing. Reject JSON, HTML, or missing Content-Type even when the URL has an image/audio/video extension.
- Bootstrap updates fail closed: execute a remote/cached runner only when its manifest/state declares the required `artifact_policy_version` as well as a valid version and SHA-256.
