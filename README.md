# Meowa Game Assets Skill

A production-oriented Codex skill for creating and preparing game art and audio with Meowa.

It covers pixel and HD assets, multi-view characters, UI sheets and extraction, image and animated-frame editing, seamless textures, terrain tilesets, isometric and side-scrolling maps, sprite animation, short video, sound effects, and game music.

## Design

The skill keeps its public surface product-focused:

- `SKILL.md` contains routing and non-negotiable safety rules.
- `references/` contains one focused guide per capability family.
- `meowart_api.py` provides curated commands with safe defaults.
- `agents/openai.yaml` provides the Codex UI metadata.

Provider credentials, provider selection, model names, sampling controls, internal workflow stages, debug payloads, raw request JSON, and custom service endpoints are not public parameters.

## Install

Copy the skill into your Codex skills directory and install the runner dependency:

```bash
git clone https://github.com/Meowa-AI/meowa-skills.git
cd meowa-skills

mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/game-assets"
cp -R skills/game-assets/. "${CODEX_HOME:-$HOME/.codex}/skills/game-assets/"
python3 -m pip install requests
```

Create a key from [Meowa API Keys](https://meowa.ai/#/api-keys), then configure it locally:

```bash
export MEOWART_API_KEY="ma_live_xxxxxxxxxxxxxxxxxxxx"
```

Alternatively, place `MEOWART_API_KEY="ma_live_xxxxxxxxxxxxxxxxxxxx"` in a local `.env` that is excluded from Git. Never paste the key into chat or pass it on the command line. See the [CLI setup and authentication guide](skills/game-assets/meowart_api.md) for Windows instructions, verification, and troubleshooting.

## Start

```bash
python3 skills/game-assets/meowart_api.py --help
python3 skills/game-assets/meowart_api.py pixel-gen-template-info
```

Generate beneath an explicit output root:

```bash
python3 skills/game-assets/meowart_api.py pixel-gen-run \
  --template-name <preset> \
  --requirement "A readable pixel-art forest potion icon" \
  --aspect-ratio 1:1 \
  --output-dir ./outputs/forest-potion
```

Each completed task creates one slug-named subdirectory beneath the selected output root. It stores only validated final media and a sanitized `final_outputs.json` manifest. The runner rejects non-HTTPS media, rejects non-media response types before writing, and never persists raw job or provider responses.

## Repository layout

```text
skills/game-assets/
├── SKILL.md
├── meowart_api.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── animation-and-video.md
│   ├── audio.md
│   ├── capability-routing.md
│   ├── maps-tiles-and-textures.md
│   ├── pixel-and-hd-assets.md
│   ├── running-and-outputs.md
│   └── ui-and-image-editing.md
└── meowart_api.py
```

See [SKILL.md](skills/game-assets/SKILL.md) for routing and operating rules.
