# UI and image editing

## Contents

- Important guidance
- Purpose and capability boundaries
- UI generation and extraction
- Consistent upgrades and variants
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
| Create consistent upgrades or variants | `one-click-upgrade-prompts`, `one-click-upgrade-run` | Quickly produce one to eight related outputs from one source | Requires one reviewed prompt per output and enough source canvas for the largest change |
| Edit still images | `image-edit-run` | Modify one or more existing visual assets | HD mode keeps its background; remove it afterward when needed |
| Edit existing animation frames | `animation-edit-run` | Restyle or modify an animated GIF or WebP | Preserve the source frame timing and layout |
| Apply the public style preset | `style-gen-run` | Produce one styled game asset | Uses the preset, model, variant, and speed exposed by the web product |
| Create Pindou bead art | `pindou-run` | Convert a pixel source at source size or generate an HD sized design | HD mode requires a supported target size |
| Reskin a built-in Spine character | `spine-run` | Produce the public Spine-agent final package | Requires the project/thread message context used by the web workflow |
| Reskin uploaded Spine parts | `spine-inspect`, `spine-edit-run` | Accept a 3.8/4.2 package and replace 1-10 selected Atlas parts | Source projects must be ZIPs containing one `.spine` file and its images |

Use this module after base-asset generation when the task is refinement rather than a new asset family. Send a finalized still asset to animation or video only after the edit is approved.

For Spine reskinning, choose the same template exposed by the web product. `--template-name character_template_slim` is the default four-head-tall template. The two-head-tall choices are `character_template_2head_celestial_librarian`, `character_template_2head_moon_jellyfish_cartographer`, `character_template_2head_clockwork_orchard_warden`, `character_template_2head_desert_glassblower_alchemist`, and `character_template_2head_deep_sea_choir_conductor`; the raw two-head base template is internal and is not a public choice. The command returns only the final Spine package.

For an uploaded runtime or source-project ZIP, first run `spine-inspect --source-spine-package <package.zip> --project-id <project>` and save its safe JSON output. Select 1-10 entries from `selected_parts`, then pass that JSON to `spine-edit-run --selected-parts-json <selection.json>`. Runtime ZIPs contain one JSON/SKEL, one Atlas, and its texture pages. Source-project ZIPs contain one `.spine` file and its referenced images. Runtime packages keep their 3.8/4.2 version; 3.8 source projects are upgraded to a 4.2 runtime for web preview. The command returns only the final runtime ZIP.

## Generate or extract game UI

Generate a UI sheet:

```bash
python3 skills/game-assets/meowart_api.py ui-gen-run \
  --prompt "A cohesive fantasy inventory UI sheet with panels, tabs, item slots, and buttons" \
  --mode generate \
  --resolution 2K \
  --aspect-ratio 4:3 \
  --quality detailed \
  --generation-model image-2 \
  --generation-speed normal \
  --background-color '#cccccc' \
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
- Select `--generation-model nano-banana` or `--generation-model image-2`; use `--generation-speed` for the Nano Banana path. Background removal and component splitting are enabled by default and can be disabled with `--no-remove-background` and `--no-split-components`.
- Use `standard` background removal for simple, high-contrast edges and `advanced` for transparency around detailed or visually complex edges.
- Describe the whole UI system: genre, hierarchy, palette, materials, states, and required components.
- Generation is not limited to interface graphics. Describe an ordinary asset batch or sprite sheet when that is the desired output.
- The workflow can remove the sheet background and automatically detect component bounds. The current public final media remains one aggregate sheet accompanied by component segmentation data; it does not return each component as a separate media file.

## Create consistent upgrades or variants

Use one-click upgrade to quickly improve one item or character, create a progression, or obtain several variants that retain a similar style, scale, and canvas. Use `image-edit-run` instead when only one exact, tightly controlled edit is needed.

Start with the free prompt-only step:

```bash
python3 skills/game-assets/meowart_api.py one-click-upgrade-prompts \
  --reference-image <source.png> \
  --prompt "Create three increasingly ornate equipment upgrades" \
  --count 3 \
  --language en
```

Review the returned prompt list before generation. Correct any unwanted direction, remove redundant wording, and keep each prompt concise. Then pass one reviewed prompt for each output:

The prompt-only command automatically makes at most three attempts, waiting five seconds after each retryable failure. Authentication and invalid-input errors fail immediately.

```bash
python3 skills/game-assets/meowart_api.py one-click-upgrade-run \
  --reference-image <prepared-source.png> \
  --variant-prompt "Add reinforced leather panels and a small bronze clasp while preserving the style" \
  --variant-prompt "Add layered steel plates and restrained blue trim while preserving the style" \
  --variant-prompt "Add ornate silver plates and a compact blue crystal crest while preserving the style" \
  --mode pixel \
  --remove-bg-method none \
  --output-dir <output-dir>
```

- Supply one to eight `--variant-prompt` values. Their count is the output count.
- Preserve one visual identity and style across the prompt list. Describe only the concrete change for each output; avoid long quality phrases.
- Inspect the source canvas before prompt generation. If the largest requested variant becomes taller, wider, or adds a weapon or effect beyond the current bounds, add only the transparent margin required along that motion or growth direction. Keep the subject at its original scale and anchor. Do not enlarge the canvas when the requested changes already fit.
- Use the same prepared source for every variant. A prompt cannot create reliable space outside the supplied canvas.
- Pixel mode defaults to a 1K service tier and HD mode to 2K. Omit `--resolution` unless the asset contract requires a different tier.
- Background removal defaults to `none`. Use `standard` or `advanced` for pixel outputs that must be isolated; HD mode supports `none` or `standard`.
- Open every result and compare style, approximate subject size, anchor, silhouette, transparency, and actual canvas dimensions.

## Edit still images

```bash
python3 skills/game-assets/meowart_api.py image-edit-run \
  --reference-image <source.png> \
  --prompt "Replace the wooden shield with a round bronze shield while preserving the pose" \
  --mode pixel \
  --strict \
  --generation-model nano-banana \
  --generation-speed normal \
  --resolution 1K \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- Provide one to eight reference images.
- Use pixel mode for pixel assets and HD mode for smooth artwork.
- Use `--strict` only when pixel structure must remain exact.
- Use `--regional-pixelation` for a multi-asset image whose detected regions need separate pixel-size handling. It is mutually exclusive with `--strict` and adds the same 2-credit product add-on shown on the web.
- Omitted options follow the web editor's mode defaults: pixel editing uses Nano Banana at 1K, while HD editing uses Image2 at 2K. An explicit `--generation-model` or `--resolution` overrides that mode default.
- `--quality standard|detailed|ultimate` applies to Image-2. `--generation-speed normal|fast` applies to Nano Banana.
- Pixel mode supports `none`, `standard`, and `advanced` background removal. HD edits keep their normal background unless the dedicated background-removal command is used afterward.

## Edit animated frames

```bash
python3 skills/game-assets/meowart_api.py animation-edit-run \
  --animation-file <walk.webp> \
  --reference-image <armor-reference.png> \
  --prompt "Apply the armor design consistently to every frame" \
  --mode pixel \
  --generation-speed normal \
  --remove-bg-method advanced \
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
