# Pixel and HD assets

## Contents

- Important guidance
- Purpose and capability boundaries
- Preset-driven pixel and HD generation
- General HD generation
- Custom-size pixel generation
- Large-pixel and Pixel Universal generation
- Directional characters
- Background removal and pixel cleanup
- Validation

## Important guidance

### Eight-direction characters

- Control the source pose for the intended animation. For a walking animation, add this requirement or its exact meaning: `角色行走动作，迈开双腿，一前一后`.
- For a running animation, add this requirement or its exact meaning: `角色奔跑动作，迈开双腿，一前一后`.
- Confirm that the legs, silhouette, equipment, and anchor remain readable in every direction before starting animation.

### Background removal

- When the source is not on a white background and advanced removal is required, always describe exactly what must be preserved. Supplying that subject description makes the runner treat the source as non-white-background input, equivalent to setting the white-background option to false.
- Before advanced pixel-art background removal, ensure the source is already perfectly pixelated and preferably smaller than 512×512.
- Advanced removal disables its built-in perfect-pixel preprocessing. If the source still needs pixel cleanup, run standalone pixelation first, review that result, and only then remove the background. Perfect-pixel detection can fail on extremely simple or extremely complex images; combining both operations can waste the background-removal cost when preprocessing fails.

### Standalone pixelation

- Pixelate one object at a time whenever possible. A batch image, especially an AI-generated sheet, may contain different effective pixel sizes in different regions; one global pass can leave some objects sharp and others blurred.
- Do not repeat pixelation on Meowa-generated pixel assets. As a practical clue, assets smaller than 256×256 are usually already perfectly pixelated, although some Meowa tools intentionally produce larger pixel assets.
- Review every pixelation result. Very simple images, solid-color blocks, or highly abstract objects may be misread because their clusters are too large; extremely complex scenes and background maps may fail because their clusters are too small.

## Purpose

Use this module to create the base still asset for a character, prop, item, icon, or sprite pack, or to perform a visual-format operation such as multi-view generation, background removal, or pixel conversion.

| Capability | Command | Final role | Main limitation |
|---|---|---|---|
| Discover pixel or HD presets | `pixel-gen-template-info`, `hd-gen-template-info` | Choose a supported size, count, and asset family | Discovery does not generate an asset |
| Generate pixel or HD assets | `pixel-gen-run`, `hd-gen-run` | Produce the base still asset or pack | Preset size and count are fixed contracts |
| Generate unrestricted HD assets | `nano-banana-run`, `image-2-run` | Produce a scene, illustration, sprite sheet, or batch of assets | Prompt controls the arrangement; no preset asset contract |
| Discover large-pixel presets | `large-pixel-template-info` | Choose a supported large canvas shape | Lists only the large-pixel family |
| Generate a large pixel asset | `large-pixel-gen-run` | Produce a scene, illustration, portrait, building, or other large pixel composition | Requires a preset from large-pixel discovery |
| Generate a general-purpose 4:3 pixel image or asset pack | `pixel-universal-gen-run` | Produce a normal-view or top-down pixel composition without choosing a preset | Uses the fixed large 4:3 `xlarge` canvas contract |
| Generate one pixel object at a custom size | `custom-size-pixel-gen-run` | Produce one object, or regenerate one source image, at a user-specified width and height | Not suitable for asset packs; less reliable than a matching fixed-size preset |
| Generate directional character views | `character-multi-view-run` | Produce an eight-direction character set | Requires a stable character reference |
| Remove a background | `remove-background-run` | Produce a transparent version of an existing asset | Edge quality depends on source complexity |
| Convert existing artwork to pixel art | `pixelate-run` | Produce a new pixel-style asset | Does not guarantee a hand-authored sprite or preset size |

Use a generated still asset as input to image editing, directional-view generation, sprite animation, or video only after its identity, scale, silhouette, and transparency are stable.

For pixel sprites, choose by production goal:

- Use preset-driven `pixel-gen-run` when exact dimensions or the highest available pixel quality matter.
- Use `custom-size-pixel-gen-run` only when the requested width and height do not match a suitable fixed preset. It targets the requested dimensions but is less reliable than 32px, 64px, and other preset-driven templates.
- Use `custom-size-pixel-gen-run` for one object or to regenerate one source image at a specified pixel size. Do not use it to generate an asset pack.
- Use the general pixel canvas through `pixel-universal-gen-run` for asset packs, low-cost high-volume sprite batches, and fast prototypes. Its built-in 4:3 `xlarge` mode includes asset-pack optimizations and allows many assets with different sizes to share one freer canvas. Expect lower fidelity and weaker exact-size control than preset-driven generation.

## Preset-driven generation

List presets before choosing one:

```bash
python3 skills/game-assets/meowart_api.py pixel-gen-template-info
python3 skills/game-assets/meowart_api.py hd-gen-template-info
```

Create a pixel asset:

```bash
python3 skills/game-assets/meowart_api.py pixel-gen-run \
  --template-name <preset> \
  --requirement "<asset description>" \
  --aspect-ratio 1:1 \
  --output-dir <output-dir>
```

Create an HD asset:

```bash
python3 skills/game-assets/meowart_api.py hd-gen-run \
  --template-name <preset> \
  --requirement "<asset description>" \
  --resolution 2K \
  --aspect-ratio 1:1 \
  --quality detailed \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

Use `--reference-file` for one reference and repeat `--reference-files` for additional references. Do not pass raw preset configuration JSON; choose a supported preset and product-level options. Preset discovery reports only product fields such as output size and default count. Treat those as fixed: if they do not match the request, choose another preset or report that the exact contract is unavailable.

Quality labels are:

| Command value | User-facing label |
|---|---|
| `standard` | Standard |
| `detailed` | Detailed |
| `ultimate` | Ultimate |

## General HD generation

Use Nano Banana for flexible composition, broad aspect-ratio support, and reference-guided generation:

```bash
python3 skills/game-assets/meowart_api.py nano-banana-run \
  --prompt "A coherent HD fantasy item sheet with twelve clearly separated potions and scrolls" \
  --resolution 1K \
  --aspect-ratio 1:1 \
  --output-dir <output-dir>
```

Use Image-2 when its quality tiers and direct HD asset generation fit the task:

```bash
python3 skills/game-assets/meowart_api.py image-2-run \
  --prompt "A clean HD game asset sheet with eight clearly separated sci-fi props" \
  --resolution 1K \
  --aspect-ratio 1:1 \
  --quality standard \
  --output-dir <output-dir>
```

- Default both commands to the shared 1K, 1:1 square working canvas. Treat it as the common 1024×1024-tier contract when moving a composition between Nano Banana and Image-2, and inspect the saved file for its actual delivered dimensions.
- Start Image-2 prompt iteration with `standard` (`Standard`), which is inexpensive. After the wording and composition are approved, rerun the same prompt with `detailed` (`Detailed`) for the production candidate. Use `ultimate` only when the final asset genuinely benefits from the additional quality and cost.
- Repeat `--reference-image` for up to eight visual references.
- Nano Banana supports 1K, 2K, and 4K plus its listed aspect ratios. Image-2 supports 1K and 2K with 1:1, 3:4, 4:3, 9:16, or 16:9.
- For batch generation, describe the asset count, shared style, spacing, background, and sheet arrangement. Review that every asset is complete and non-overlapping.
- Inspect for unintended labels or decorative lettering even when the prompt says `no text`; asset sheets can still introduce short item labels and may need regeneration or editing.
- Use `ui-gen-run` instead when the generated sheet also needs automatic background removal and component segmentation. That module is prompt-driven and can generate ordinary art assets or sprite sheets in addition to interface graphics.

## Custom-size pixel generation

Use this mode when one object's final pixel dimensions are explicit and no fixed-size preset fits, or when one source image should be regenerated as pixel art at a specified size:

```bash
python3 skills/game-assets/meowart_api.py custom-size-pixel-gen-run \
  --prompt "A minimal standing forest ranger, simple color blocks, no complex textures" \
  --width 48 \
  --height 80 \
  --generation-model nano-banana \
  --output-dir <output-dir>
```

Add one or more references only when identity, pose, or art direction must be retained:

```bash
python3 skills/game-assets/meowart_api.py custom-size-pixel-gen-run \
  --prompt "Keep the character recognizable, but keep the design minimal and replace complex textures with simple color blocks" \
  --width 48 \
  --height 80 \
  --reference-image <character.png> \
  --strong-pixelation \
  --output-dir <output-dir>
```

- Prefer a matching fixed-size preset whenever one exists. User-specified dimensions are supported when they fit the generation canvas, but generation is less reliable than a purpose-built 32px, 64px, or similar preset.
- Generate one object at a time. This mode is also suitable for converting one specified-size source image into a new pixel-art result, but it is not suitable for an asset pack.
- For an asset pack, use `pixel-universal-gen-run`. Its built-in 4:3 `xlarge` mode contains asset-pack optimizations and offers enough freedom to produce many differently sized assets in one image. Prefer a basic fixed template when one fits, because it remains more reliable than the freer large canvas.
- Text-only generation is relatively stable. Reference-guided generation is less stable, especially for complex references, so expect to test and refine the prompt.
- Reduce reference complexity explicitly when needed. Useful constraints include “keep the design minimal” and “reduce complex textures and express the character with simple color blocks.” Describe one subject and preserve only the visual details that matter.
- Use Nano Banana by default. `--generation-model image-2` is available for comparison when the default result is unsuitable.
- Background removal is intentionally disabled in this command. First approve the generated image, then call `remove-background-run`; this avoids paying for background removal on generations that will be discarded.
- Fill-canvas is enabled by default. It asks the subject to occupy as much of the target frame as its shape allows, which can bring the result closer to the requested size. It cannot make incompatible geometry fit: a standing character may still leave horizontal space on a wide canvas. Pass `--no-fill-canvas` when preserving breathing room or proportions matters more.
- `--strong-pixelation` requires at least one reference. Try it when the reference is low quality or already pixelated, because those sources can encourage copying instead of regeneration. Strong pixelation applies a more forceful redraw step, but it still cannot guarantee a successful result.
- Inspect the final dimensions, silhouette, readable pixel clusters, and reference fidelity. If the first result is too detailed or too close to the source, simplify the prompt before changing models.

## Large-pixel and Pixel Universal generation

Use the large-pixel preset family when a small exact-size character or prop preset does not provide enough canvas space:

```bash
python3 skills/game-assets/meowart_api.py large-pixel-template-info

python3 skills/game-assets/meowart_api.py large-pixel-gen-run \
  --template-name <large-pixel-preset> \
  --prompt "<scene, illustration, portrait, or large asset description>" \
  --reference-image <optional-style-reference.png> \
  --output-dir <output-dir>
```

- Select the preset from `large-pixel-template-info`; do not guess its name or expose internal configuration.
- Background removal defaults to `none` so complete scenes and illustrations remain intact. Use `standard` only when the desired final asset is an isolated subject on transparency.
- References may supply style, identity, layout, or source artwork. State what each reference should control in the prompt.

Use Pixel Universal Generation for a flexible 4:3 pixel composition without choosing a preset:

```bash
python3 skills/game-assets/meowart_api.py pixel-universal-gen-run \
  --prompt "A top-down pixel-art market district with readable paths and compact stalls" \
  --view top-down \
  --reference-image <optional-reference.png> \
  --remove-bg-method none \
  --output-dir <output-dir>
```

Available views are:

| View | Use |
|---|---|
| `standard` | Normal composition for scenes, portraits, characters, buildings, and illustrations |
| `top-down` | Overhead game view for maps, rooms, environments, objects, and characters designed from above |

This is the pixel-art counterpart to a general Nano Banana-style image workflow. Suitable tasks include:

- Reinterpreting an HD reference as a new pixel-art composition.
- Generating a pixel scene, environment concept, character illustration, or portrait.
- Designing a building-upgrade progression or another multi-stage visual in one coherent composition.
- Creating top-down game assets while preserving an overhead camera convention.

The command fixes the large 4:3 canvas and defaults to keeping the background because most general compositions are complete scenes. Request standard background removal only for an isolated subject.

## Eight-direction characters

```bash
python3 skills/game-assets/meowart_api.py character-multi-view-run \
  --reference-image <character.png> \
  --mode pixel \
  --canvas-resolution 1K \
  --direction-mode mirror \
  --aspect-ratio 1:1 \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- Use `mirror` to generate five directions and mirror the compatible views into a complete eight-direction set.
- Use `ninegrid` to generate the eight directions in one nine-grid layout. It is a generation layout, not a nine-view deliverable.
- Pixel mode supports 1K or 2K. HD mode uses the service's fixed 2K canvas behavior even though the compatibility CLI still accepts `--canvas-resolution`.
- Use `--output-size` only when the requested final sprite size is explicit.
- Put pose, clothing, silhouette, or consistency requirements in `--extra-constraint`.

## Background removal

```bash
python3 skills/game-assets/meowart_api.py remove-background-run \
  --image-file <asset.png> \
  --mode pixel \
  --quality advanced \
  --prompt "Keep the armored character; remove the complex forest background" \
  --output-dir <output-dir>
```

- Choose `pixel` or `hd` to match the source artwork.
- Choose `standard` for a clean, simple background and `advanced` for difficult edges or a complex background.
- Add a subject prompt whenever an advanced-removal source is not white-backed or the background is complex.
- Do not name or select a background-removal provider.

## Pixel cleanup

```bash
python3 skills/game-assets/meowart_api.py pixelate-run \
  --image-file <source.png> \
  --output-dir <output-dir>
```

Use the generated file directly. For previews, enlarge only with nearest-neighbor sampling; never shrink a pixel asset merely to make it fit the response.

The public command always uses automatic pixel-size detection. Review the result before using it in production.

## Validate

- Confirm the final dimensions and aspect ratio.
- Confirm alpha transparency when requested.
- Inspect edges at an integer zoom with nearest-neighbor sampling.
- Check that sprite sheets contain complete, non-overlapping cells.
- Check `final_outputs.json` and deliver only the listed final media.
