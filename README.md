# Game Assets Generation Skill for Meowa

Create game-ready 2D assets with Meowa from inside Codex: pixel sprites, HD
assets, props, backgrounds, seamless loops, texture tiles, terrain tilesets,
transparent PNGs, simple animations, UI mockups, sound effects, and
loop-friendly game music drafts.

This repository contains a Codex skill plus a small Python CLI wrapper around
the Meowa API. The skill teaches an agent how to choose the right generation
path, keep pixel assets crisp, manage output directories, and validate generated
files before handing them back to a game project.

## What It Can Generate

- Pixel characters, enemies, props, items, icons, and sprite batches
- HD transparent characters, icons, props, and asset packs
- Backgrounds, scene concepts, and 16:9 or other fixed-ratio game art
- Seamless horizontal, vertical, or four-way looping backgrounds and textures
- Single texture tiles and dual-grid terrain tilesets
- Transparent PNG assets through pixel or HD background removal
- Pixel-cleaned versions of larger AI-generated images
- Short character or object animations as WebP, GIF, or spritesheets
- UI, combat, pickup, ambient, and skill sound effects
- Game BGM directions, 30 second demos, or full music generations
- UI concept mockups and extractable UI sprites from game screenshots

## Repository Layout

```text
.
|-- README.md
`-- skills/
    `-- game-assets/
        |-- SKILL.md          # Codex skill instructions
        |-- meowart_api.md    # Quick API usage guide
        |-- meowart_api.bootstrap.json
        `-- meowart_api.py    # Meowa API helper CLI
```

## Install

Clone the repository and copy the skill into your Codex skills directory:

```bash
git clone https://github.com/Meowa-AI/meowa-skills.git
cd meowa-skills

export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills/game-assets"
cp -R skills/game-assets/. "$CODEX_HOME/skills/game-assets/"
```

Install the Python dependency used by the helper CLI:

```bash
python3 -m pip install requests
python3 skills/game-assets/meowart_api.py --help
```

## Automatic CLI Updates

`meowart_api.py` includes a bootstrap wrapper. On normal command runs it checks
the checksummed manifest at:

```text
https://raw.githubusercontent.com/Meowa-AI/meowa-skills/main/skills/game-assets/meowart_api.bootstrap.json
```

If the manifest advertises a newer runner, the script downloads the new
`meowart_api.py`, verifies its SHA-256, caches it under
`~/.cache/meowa-skills/game-assets/`, and executes that cached runner. If the
network is unavailable, the manifest is invalid, or the checksum fails, it
continues with the bundled script.

Useful controls:

```bash
python3 skills/game-assets/meowart_api.py bootstrap-status
python3 skills/game-assets/meowart_api.py bootstrap-status --check
MEOWART_BOOTSTRAP=0 python3 skills/game-assets/meowart_api.py credits-balance
python3 skills/game-assets/meowart_api.py --no-bootstrap credits-balance
python3 skills/game-assets/meowart_api.py --bootstrap-force credits-balance
```

The bootstrap updates the CLI runner only. Changes to `SKILL.md` routing
instructions still require reinstalling/updating the skill and restarting Codex.

## Dynamic Skill Guide

`SKILL.md` is intentionally small and stable. Before choosing commands for a
game asset task, ask the CLI for the current Meowa guide:

```bash
python3 skills/game-assets/meowart_api.py skill-doc --task "Create 64x64 pixel item icons"
python3 skills/game-assets/meowart_api.py skill-doc --topic pixel-gen
python3 skills/game-assets/meowart_api.py skill-doc-status --check
```

The guide is fetched from the public Meowa API, cached under
`~/.cache/meowa-skills/game-assets/docs/`, and falls back to the bundled
`meowart_api.md` if the network or API is unavailable.

## Authentication

Create an API key in Meowa:

https://meowa.ai/#/api-keys

Then set it as an environment variable:

```bash
export MEOWART_API_KEY="ma_live_xxxxxxxxxxxxxxxxxxxx"
```

For internal or self-hosted backend debugging, the CLI also supports developer
auth through `MEOWART_DEV_KEY` or `DEV_API_KEY`, which is sent as `X-Dev-Key`.

Do not commit API keys. Prefer environment variables or a local `.env` file.

## Quick Start

Endpoint contract:

- Pixel assets use `POST /api/pixel-gen`, then `GET /api/pixel-gen/jobs?id=<api_job_id>`.
- HD assets use `POST /api/hd-gen`, then `GET /api/hd-gen/jobs?id=<api_job_id>`.
- Generic Gemini calls use `POST /api/gemini/...` through the `gemini-*` commands.
- Meowa does not expose `POST /generate` or `POST /api/generate`. A 404 for `/generate` means the client endpoint is wrong, not that the API key is valid or invalid.

Check available commands:

```bash
python3 skills/game-assets/meowart_api.py --help
```

Check your credit balance:

```bash
python3 skills/game-assets/meowart_api.py credits-balance
```

List pixel generation templates:

```bash
python3 skills/game-assets/meowart_api.py pixel-gen-template-info
```

List HD generation templates:

```bash
python3 skills/game-assets/meowart_api.py hd-gen-template-info
```

Dry run a pixel sprite batch without spending credits:

```bash
python3 skills/game-assets/meowart_api.py \
  pixel-gen-run \
  --template-name "cat_2" \
  --requirement "calico, orange tabby, tuxedo, siamese, british shorthair, american shorthair, brown tabby, white cat" \
  --dry-run
```

Generate a side-facing pixel character:

```bash
python3 skills/game-assets/meowart_api.py \
  pixel-gen-run \
  --template-name "pixel_character_large" \
  --requirement "A fox rogue with twin daggers" \
  --template-config '{"direction":"left"}' \
  --output-dir ./outputs/fox_rogue
```

Generate a transparent HD character:

```bash
python3 skills/game-assets/meowart_api.py \
  hd-gen-run \
  --template-name "hd_char_1" \
  --requirement "A cheerful fantasy alchemist girl with green cloak" \
  --template-config '{"direction":"front"}' \
  --output-dir ./outputs/hd_alchemist
```

Generate a 16:9 non-pixel game background concept:

```bash
python3 skills/game-assets/meowart_api.py \
  gemini-generate-content \
  --text "Generate a 2K 16:9 night market background concept for a cozy RPG." \
  --generation-config '{"responseModalities":["TEXT","IMAGE"],"imageConfig":{"aspectRatio":"16:9","imageSize":"2K"}}' \
  --output-dir ./outputs/night_market
```

For pixel sprites, props, icons, small tile sprites, or character assets, use
`pixel-gen-template-info` and `pixel-gen-run` first. Only use general generation
as a fallback, then run `pixelate-run` before treating the result as a final
pixel asset.

Create a seamless horizontal loop from an existing background:

```bash
python3 skills/game-assets/meowart_api.py \
  self-loop-run \
  --image-file ./outputs/night_market/background.png \
  --direction horizontal \
  --output-dir ./outputs/night_market_loop
```

Generate a single seamless texture tile:

```bash
python3 skills/game-assets/meowart_api.py \
  texture-gen-run \
  --prompt "mossy cracked stone floor" \
  --texture-name "砖墙" \
  --texture-name "破碎小石块" \
  --output-dir ./outputs/mossy_stone_texture
```

Generate a dual-grid terrain tileset:

```bash
python3 skills/game-assets/meowart_api.py \
  tileset-gen-run \
  --prompt "lush grass foreground plus shallow blue water background" \
  --output-dir ./outputs/grass_water_tileset
```

Remove a white background from a pixel sprite:

```bash
python3 skills/game-assets/meowart_api.py \
  remove-background-run \
  --image-file ./outputs/fox_rogue/sprite.png \
  --method pixel \
  --output-dir ./outputs/fox_rogue_transparent
```

Generate a short animation:

```bash
python3 skills/game-assets/meowart_api.py \
  animate-run \
  --image-file ./outputs/fox_rogue_transparent/sprite.png \
  --prompt "fox rogue idle breathing animation" \
  --is-pixel \
  --output-format spritesheet \
  --output-dir ./outputs/fox_rogue_idle
```

Generate a short sound effect:

```bash
python3 skills/game-assets/meowart_api.py \
  sound-run \
  --prompt "soft wooden UI button click for cozy pixel RPG" \
  --duration 1 \
  --output-dir ./outputs/ui_click
```

Generate a small sound pack:

```bash
python3 skills/game-assets/meowart_api.py \
  sound-run \
  --prompt "8-bit fantasy combat sound pack: sword slash, shield block, coin pickup, potion drink" \
  --sound-pack \
  --count 4 \
  --duration 1 \
  --output-dir ./outputs/combat_sfx_pack
```

Draft loop-friendly game music:

```bash
python3 skills/game-assets/meowart_api.py \
  music-run \
  --prompt "A cozy pixel RPG village theme with flute, kalimba, soft strings, no vocals, loop-friendly"
```

Generate a 30 second music demo:

```bash
python3 skills/game-assets/meowart_api.py \
  music-run \
  --prompt "A cozy pixel RPG village theme with flute, kalimba, soft strings, no vocals, loop-friendly" \
  --audio-generate \
  --demo \
  --output-dir ./outputs/village_theme_demo
```

## Using It With Codex

After the skill is installed, ask Codex for production-oriented game asset work:

```text
Use Meowa to generate eight 64x64 potion icons for a pixel roguelike.
```

```text
Create a side-scrolling forest background, then turn it into a seamless horizontal loop.
```

```text
Generate a mossy stone floor texture and a matching grass-water dual-grid tileset.
```

```text
Generate a transparent idle spritesheet for this character reference.
```

```text
Create four short UI and combat sound effects for this game.
```

```text
Create a 30 second loop-friendly demo track for a rainy cyberpunk town scene.
```

The skill will guide Codex to:

- Pick the right Meowa command for the requested asset type
- Use dry runs before expensive generation when useful
- Keep pixel art on stable canvas sizes
- Prefer nearest-neighbor resizing for pixel assets
- Save outputs and metadata into explicit task directories
- Validate dimensions, transparency, frame counts, audio files, and downloaded files

## Output Directories

Most `*-run` commands create metadata and output files. For predictable project
integration, pass `--output-dir` for final assets and optionally `--work-dir`
for logs:

```bash
python3 skills/game-assets/meowart_api.py \
  pixel-gen-run \
  --template-name "object" \
  --requirement "eight fantasy key icons, distinct shapes and metals" \
  --work-dir ./.meowart-test/key_icons \
  --output-dir ./assets/generated/key_icons
```

Typical saved files include:

- `meta.json`
- `submit_response.json`
- `job_response.json`
- Downloaded PNG, GIF, WebP, spritesheet, MP3, WAV, or OGG files when available

## Production Notes

- Start with one or two assets before generating a full pack.
- Keep one art direction document for style, palette, camera angle, and target sizes.
- For pixel sprites, avoid non-integer scaling and use nearest-neighbor sampling.
- For local edits, keep input and output canvas dimensions stable.
- For batch templates, write the whole batch request, not a single-object prompt.
- For HD assets, choose an HD template first instead of using generic image generation.
- For texture tiles and terrain tilesets, use `texture-gen-run` or `tileset-gen-run` before falling back to generic image generation.
- For sound effects, keep prompts concrete and short, then use `--sound-pack` or `--variants` only when you really need multiple outputs.
- For music, start with prompt-only mode, then generate a 30 second demo before a full track.
- Always inspect generated assets before committing them to a game pipeline.

## Documentation

- [Skill instructions](skills/game-assets/SKILL.md)
- [Meowa API quick guide](skills/game-assets/meowart_api.md)
- [Meowa API helper CLI](skills/game-assets/meowart_api.py)

## License

No license file is currently included. Add one before redistributing this
repository as an open-source package.
