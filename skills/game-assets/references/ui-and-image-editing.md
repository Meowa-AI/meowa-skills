# UI and image editing

## Contents

- Important guidance
- Purpose and capability boundaries
- UI generation and extraction
- Still-image and animated-frame editing
- Validation

## Important guidance

### UI generation and extraction

- To match an existing game style, provide a game screenshot, a UI layout reference, or even a rough layout sketch. Match the reference canvas to the requested output whenever possible: for a 1:1 canvas, use 1024×1024 for 1K or 2048×2048 for 2K.
- Keep generation prompts focused on the main content and visual direction. Excessively detailed instructions can restrict useful variation and reduce quality.
- When a UI already exists and only its elements need to be reorganized, use extract mode and describe the extraction goal clearly. Extract mode targets all visible UI elements by default.

### Still-image editing

- Prefer no more than one additional reference image. More references can divide the model's attention.
- Edit mode keeps the output canvas close to the input canvas, so low-resolution assets can be edited directly without first enlarging them. This is usually the most efficient path and the result can normally return directly to the game.
- Because the canvas stays close to the source, edit mode cannot perform large-scale enlargement or major proportion changes. For unrestricted enlargement, height changes, or recomposition, use a general Nano Banana or Image-2 generation path instead.

### Animated-frame editing

- Prefer only one additional reference image; multiple references can reduce instruction comprehension.
- Keep animated WebP or GIF inputs compact. A source with frames around 96×96 and roughly eight frames can usually stay within a 1K working canvas. Larger frames or more frames may require 2K processing, raise cost, and reduce consistency.
- Describe the exact cross-frame change, for example replacing the character skin with a named animation character or changing a weapon effect from fire to lightning.

## Purpose

Use this module to generate a UI or general asset sheet with automatic background removal and component segmentation, extract an aggregate UI layout, or modify existing still or animated artwork. Generation is prompt-driven: it can create ordinary game assets or a sprite sheet when the prompt asks for them, even though the module is named for UI.

| Capability | Command | Final role | Main limitation |
|---|---|---|---|
| Generate or extract UI and asset sheets | `ui-gen-run` | Produce one transparent aggregate sheet plus component segmentation data | Does not return separate cropped component media files |
| Edit still images | `image-edit-run` | Modify one or more existing visual assets | HD mode keeps its background; remove it afterward when needed |
| Edit existing animation frames | `animation-edit-run` | Restyle or modify an animated GIF or WebP | Preserve the source frame timing and layout |

Use this module after base-asset generation when the task is refinement rather than a new asset family. Send a finalized still asset to animation or video only after the edit is approved.

## Generate or extract game UI

Generate a UI sheet:

```bash
python3 skills/game-assets/meowart_api.py ui-gen-run \
  --prompt "A cohesive fantasy inventory UI sheet with panels, tabs, item slots, and buttons" \
  --mode generate \
  --resolution 2K \
  --aspect-ratio 4:3 \
  --quality detailed \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

Extract and arrange reusable-looking components from an existing UI image into one final sheet:

```bash
python3 skills/game-assets/meowart_api.py ui-gen-run \
  --prompt "Extract the reusable panels, buttons, icons, and tabs" \
  --mode extract \
  --reference-image <ui-sheet.png> \
  --resolution 2K \
  --aspect-ratio 4:3 \
  --quality detailed \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- Repeat `--reference-image` for up to eight references.
- Extract mode requires at least one reference image.
- Supported aspect ratios are 4:3, 3:4, 16:9, 9:16, and 1:1.
- Treat `1K` and `2K` as service resolution tiers, not promises of one universal pixel dimension; inspect the saved image for its actual dimensions.
- Use `standard` for quick drafts, `detailed` for normal production work, and `ultimate` for a final asset whose small text or dense ornament needs the highest fidelity.
- Use `standard` background removal for simple, high-contrast edges and `advanced` for transparency around detailed or visually complex edges.
- Describe the whole UI system: genre, hierarchy, palette, materials, states, and required components.
- Generation is not limited to interface graphics. Describe an ordinary asset batch or sprite sheet when that is the desired output.
- The workflow can remove the sheet background and automatically detect component bounds. The current public final media remains one aggregate sheet accompanied by component segmentation data; it does not return each component as a separate media file.

## Edit still images

```bash
python3 skills/game-assets/meowart_api.py image-edit-run \
  --reference-image <source.png> \
  --prompt "Replace the wooden shield with a round bronze shield while preserving the pose" \
  --mode pixel \
  --strict \
  --resolution 1K \
  --aspect-ratio auto \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- Provide one to eight reference images.
- Use pixel mode for pixel assets and HD mode for smooth artwork.
- Use `--strict` only when pixel structure must remain exact.
- Pixel mode supports `none`, `standard`, and `advanced` background removal. HD edits keep their normal background unless the dedicated background-removal command is used afterward.

## Edit animated frames

```bash
python3 skills/game-assets/meowart_api.py animation-edit-run \
  --animation-file <walk.webp> \
  --reference-image <armor-reference.png> \
  --prompt "Apply the armor design consistently to every frame" \
  --mode pixel \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- The source must be an animated GIF or WebP.
- Provide at most eight visual references.
- Describe changes that must remain consistent across every frame.
- Validate frame count, canvas size, timing, loop behavior, and alignment after editing.

## Validate

- Open every final image and verify that no reference image was returned as an output.
- For UI extraction or generated asset sheets, confirm the components are visually separated, have usable transparency, and have plausible segmentation bounds. Do not claim that individual component media files were produced.
- For edits, compare subject identity, pose, layout, and palette against the source.
- Deliver only files listed in `final_outputs.json`.
