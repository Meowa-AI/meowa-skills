# Maps, tiles, and textures

## Contents

- Validated small pixel-isometric path
- Purpose and capability boundaries
- Reusable map references
- Seamless textures and terrain tilesets
- Isometric and hex map tiles
- Side-scrolling maps
- Validation

## Validated small pixel-isometric path

- Use `isometric-gen-run --mode standard` for the tested small pixel-isometric path. It uses a logical side length of 64 and height of 32, requires exactly two reference images, and produces two independent final tiles plus a pack preview.
- Inspect `map-reference-search --categories --type pixel-isometric`, then select an exact theme and layout such as `--theme grassland --layout single`. Use free-text `--query` only as an optional refinement.
- Download two selected preset ids with `map-reference-download` and pass both downloaded PNG files through repeated `--reference-image` options.
- Expect transparent padding around each final RGBA tile. Validate the visible subject bounds and logical geometry rather than assuming the outer PNG canvas is exactly 64×64.
- Compare visible bounds and anchor placement across every tile. Different transparent outer-canvas sizes are acceptable when the logical geometry and placement anchor remain correct.
- Treat `tile_pack_preview.png` as a review layout. Use the independent tile files in the game and do not pixelate them again.

## Purpose

Use this module to create environment materials and map-ready assets: seamless textures, terrain atlases, isometric or hex tiles, and layered side-scrolling scenes.

| Capability | Command | Final role | Main limitation |
|---|---|---|---|
| Discover reusable map references | `map-reference-search`, `map-reference-download` | Supply planning or supported reference inputs | Not every map command accepts downloaded references |
| Generate flat or isometric textures | `texture-gen-run`, `isometric-texture-run` | Produce repeatable material tiles | Validate seams before tileset use |
| Generate flat or isometric tilesets | `tileset-gen-run`, `isometric-tileset-run` | Produce terrain transition atlases | Single- and dual-terrain modes have different contracts |
| Generate isometric or hex map tiles | `isometric-gen-run`, `hex-isometric-gen-run`, HD variants | Produce map-ready projected tile sets | Mode names and supported references vary by command |
| Generate side-scrolling layers | `side-scrolling-map-run`, `hd-side-scrolling-map-run` | Produce aligned foreground, midground, and background layers | Uses text descriptions rather than downloaded map presets |

Use a texture as a tileset reference only when the tileset command accepts it. Treat side-scrolling generation as a separate layered-scene path, not the final stage of the texture or tileset pipeline.

## Search reusable map references when supported

Start with the catalog instead of guessing search words:

```bash
python3 skills/game-assets/meowart_api.py map-reference-search \
  --categories

python3 skills/game-assets/meowart_api.py map-reference-search \
  --categories \
  --type hd-isometric
```

Supported types are `pixel-isometric`, `pixel-hex-isometric`, `hd-isometric`, `hd-hex-isometric`, and `tileset`. The catalog response lists the valid themes and layouts for each type. Query one exact branch with structured filters:

```bash
python3 skills/game-assets/meowart_api.py map-reference-search \
  --type pixel-isometric \
  --theme grassland \
  --layout single \
  --limit 12

python3 skills/game-assets/meowart_api.py map-reference-search \
  --type hd-isometric \
  --theme modern \
  --layout single \
  --limit 12
```

Layouts are type-specific: square isometric types use `single` or `2x2`; pixel hex also supports `7-cell` and `template`; tilesets use `template`. `--layout` therefore requires `--type`. Use `--group` only for an advanced exact catalog-group filter.

Add `--query` after structured filters when a material or object refinement is useful. Search first requires all query words; if that produces no matches, it automatically falls back to results containing any query word and reports `match_mode: any-fallback`.

Download selected references into a task directory:

```bash
python3 skills/game-assets/meowart_api.py map-reference-download \
  --preset-id <reference-id> \
  --output-dir <output-dir>
```

The download command accepts the same `--type`, `--theme`, `--layout`, `--query`, and limit filters. Prefer explicit `--preset-id` values after reviewing search results so the chosen references remain deterministic.

Treat downloaded references as inputs, never as newly generated deliverables. Pass them only to a command that documents a reference or preset option. Side-scrolling commands do not accept these files; use search results only as planning inspiration for their text descriptions.

## Seamless textures

Flat texture:

```bash
python3 skills/game-assets/meowart_api.py texture-gen-run \
  --prompt "Weathered blue-gray dungeon flagstones with sparse moss" \
  --self-loop \
  --output-dir <output-dir>
```

Isometric texture:

```bash
python3 skills/game-assets/meowart_api.py isometric-texture-run \
  --prompt "Warm sandstone blocks with small cracks" \
  --reference-image <material-reference.png> \
  --self-loop \
  --output-dir <output-dir>
```

Use the isometric command when the final texture must already be projected as a 2:1 isometric tile. Keep `--self-loop` enabled for repeatable terrain unless the user explicitly wants a non-tiling sample.

Do not guess `--texture-name` from a semantic material name. It must match an installed reference name exactly, and the public runner does not currently provide a reference-name catalog. Prefer a prompt and optional image reference unless a valid name is already known.

## Terrain tilesets

Flat dual-terrain tileset:

```bash
python3 skills/game-assets/meowart_api.py tileset-gen-run \
  --prompt "Bright grass transitioning into shallow clear water" \
  --terrain-mode dual \
  --foreground-color "#67B84F" \
  --background-color "#3D8EDB" \
  --output-dir <output-dir>
```

Isometric single-terrain tileset:

```bash
python3 skills/game-assets/meowart_api.py isometric-tileset-run \
  --prompt "Volcanic basalt terrain with glowing red cracks" \
  --terrain-mode single \
  --single-terrain-region foreground \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- Use `dual` for foreground/background transitions and `single` for one isolated terrain family.
- In single mode, select `foreground` or `background` as the occupied region.
- Background removal applies only to single-terrain output. Dual terrain keeps both terrain regions and ignores the selected removal level.
- In single mode, use `none`, `standard`, or `advanced` for background removal. Do not select a provider.
- Supply texture references only through `--foreground-texture` and `--background-texture`.

## Isometric and hex map tiles

Pixel isometric:

```bash
python3 skills/game-assets/meowart_api.py isometric-gen-run \
  --prompt "A mossy stone dungeon floor tile with matching wall edges" \
  --mode standard \
  --remove-bg-method standard \
  --reference-image <floor-reference.png> \
  --reference-image <wall-reference.png> \
  --output-dir <output-dir>
```

Pixel hex-isometric:

```bash
python3 skills/game-assets/meowart_api.py hex-isometric-gen-run \
  --prompt "A desert oasis hex tile with palms and a small blue pool" \
  --mode standard \
  --remove-bg-method standard \
  --reference-image <terrain-reference.png> \
  --reference-image <detail-reference.png> \
  --output-dir <output-dir>
```

Use `hd-isometric-gen-run` and `hd-hex-isometric-gen-run` for smooth HD map tiles. Reference counts are hard request contracts:

- Pixel isometric: `standard` requires 2 references; `edit` 1; `tetraploid` 3; `road` 2; `wall` 1.
- Pixel hex-isometric: `standard` requires 2 references; `edit` 1; `tetraploid` 2–4; `heptaploid` 2–7.
- HD isometric `tetraploid` requires 2–4 references.
- HD hex-isometric `tetraploid` can use its template defaults or 1–4 uploaded references.

The names `tetraploid` and `heptaploid` are compatibility mode names for multi-tile layouts, not art styles. Use them only when that layout is explicitly required.

## Side-scrolling maps

Pixel map:

```bash
python3 skills/game-assets/meowart_api.py side-scrolling-map-run \
  --midground "Dense enchanted forest paths and playable platforms" \
  --background "Layered blue mountains and a pale dawn sky" \
  --foreground "Dark leafy silhouettes and roots along the bottom edge" \
  --remove-bg-method standard \
  --loop-midground \
  --loop-background \
  --loop-foreground \
  --output-dir <output-dir>
```

HD map:

```bash
python3 skills/game-assets/meowart_api.py hd-side-scrolling-map-run \
  --midground "A readable coastal village path with shops and stairs" \
  --background "Ocean cliffs, distant islands, and soft clouds" \
  --foreground "Flowers, fence silhouettes, and rocks along the bottom" \
  --art-style 2d_hd \
  --loop-midground \
  --loop-background \
  --loop-foreground \
  --output-dir <output-dir>
```

The side-scrolling commands produce 1K-tier, 16:9 layer sets; inspect the saved files for their actual pixel dimensions. Every loop flag requests a horizontal end-to-start seam. Pixel side-scrolling requires foreground and midground background removal and therefore offers only `standard` and `advanced`; use `advanced` for difficult edges. Supported HD styles are `2d_hd`, `2d_cartoon`, `2d_ink`, `clay`, `low_poly_3d`, `steampunk`, and `anime_hd`. A non-empty `--custom-art-style` overrides the selected preset style; use it only when none of the presets matches.

## Validate

- Verify tile dimensions and grid alignment.
- Inspect seams by repeating textures in both axes.
- Confirm isometric tiles use the expected 2:1 projection and consistent anchor points.
- Confirm side-scrolling layers align at the same canvas size and loop without a visible seam when looping was requested.
- Preview pixel assets at integer zoom with nearest-neighbor sampling.
- Deliver only files listed in `final_outputs.json`.
