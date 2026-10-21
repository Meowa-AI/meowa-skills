# UI and image editing

## Contents

- Important guidance
- Purpose and capability boundaries
- UI generation and extraction
- Consistent upgrades and variants
- Still-image and animated-frame editing
- [User-supplied mask editing](#edit-a-user-marked-region-with-nano-banana)
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
| Split an existing complex-pattern PNG locally | `scripts/split-components.py` | Produce individual transparent PNG crops and placement data without an API | Requires separated shapes on transparency or a solid background; see [local tools](local-tools.md) |
| Create consistent upgrades or variants | `one-click-upgrade-prompts`, `one-click-upgrade-run` | Quickly produce one to eight related outputs from one source | Requires one reviewed prompt per output and enough source canvas for the largest change |
| Edit still images | `image-edit-run` | Modify one or more existing visual assets | Pixel and HD default to standard background removal; use none to retain the background |
| Clone an asset sheet | `asset-clone-run` | Generate 1, 4, 9, 16, 25, or 36 same-style assets in one grid | Returns complete sheets without splitting cells |
| Edit existing animation frames | `animation-edit-run` | Restyle or modify an animated GIF or WebP | Preserve the source frame timing and layout |
| Create Pindou bead art | `pindou-run` | Convert a pixel source at source size or generate an HD sized design | HD mode requires a supported target size |
| Reskin a built-in Spine character | `spine-run` | Produce the public Spine-agent final package | Automatically creates recoverable project/thread context when omitted |
| Reskin uploaded Spine parts | `spine-inspect`, `spine-edit-run` | Accept Spine 3.6-4.2, or experimental 4.3, and replace 1-40 selected Atlas parts | Every import becomes a Spine 4.2 runtime |
| Replace one uploaded Spine part directly | `spine-inspect`, `spine-replace-run` | Put one static PNG/JPEG/WebP/AVIF into one selected Atlas region without AI generation | Optional Standard background removal costs 5 credits; otherwise 0 |
| Clean editor frames from a Spine atlas | `spine-cleanup-run` | Remove layout frames and labels from atlas geometry without color matching | Returns a new final runtime ZIP and keeps the source unchanged |
| Reskin a complete uploaded Spine package | `spine-reskin-run` | Pack all meaningful textured modules into one sheet at the selected 1K or 2K resolution | Modules smaller than 1400px² keep their original artwork |

Use this module after base-asset generation when the task is refinement rather than a new asset family. Send a finalized still asset to animation or video only after the edit is approved.


For Spine reskinning, run `spine-run --prompt <look> --output-dir <output-dir>` without copying IDs from the web product. The runner creates a recoverable project, thread, and source message automatically. Use optional `--project-id` and `--thread-id` only to attach the run to existing context. Choose the same template exposed by the web product. The default is the two-head-tall `character_template_2head_celestial_librarian`; `character_template_slim` remains the four-head-tall choice. The other two-head-tall choices are `character_template_2head_moon_jellyfish_cartographer`, `character_template_2head_clockwork_orchard_warden`, `character_template_2head_desert_glassblower_alchemist`, and `character_template_2head_deep_sea_choir_conductor`; the raw two-head base template is internal and is not a public choice. Two-head generation defaults to GPT Image 2.5 with the Detailed package (35 credits). All images use Standard quality; `--quality` selects the generation package. `--export-version` mirrors the web export selector and defaults to `4.2`; choose `3.8.99` for Cocos compatibility or `3.8.75` only for legacy compatibility. The downgrade removes animated bone inheritance and may simplify or lose other 4.2-only features. The command returns only the selected final Spine package.

For an uploaded runtime or source-project ZIP up to 50 MB, first run `spine-inspect --source-spine-package <package.zip> --project-id <project>` and save its safe JSON output. Select 1-40 entries from `selected_parts`, then pass that JSON to `spine-edit-run --selected-parts-json <selection.json>`. Add one optional `--reference-image <image>` to guide character, outfit, weapon, material, color, or style while preserving every selected part's size, position, orientation, and count. Runtime ZIPs contain one `.json` (Spine 3.6-4.3) or `.skel` (Spine 3.7-4.3), one `.atlas` or `.atlas.txt`, and PNG/JPG/JPEG/WebP texture pages. Spine 3.6 binary `.skel` is not supported; use its JSON export or source project. Source-project ZIPs contain exactly one `.spine` file and its PNG/JPG/JPEG/WebP images. Spine 3.6, 3.7, 3.8, 4.0, 4.1, and 4.2 are stable inputs; Spine 4.3 conversion is experimental and returns a warning. Every successful import is normalized to a Spine 4.2 runtime. The command returns only the selected final runtime ZIP; `--export-version` defaults to `4.2`, with `3.8.99` recommended for Cocos and `3.8.75` available for legacy compatibility. Both 3.8 choices remove animated bone inheritance and may simplify or lose other 4.2-only features.

To bypass AI generation, select exactly one inspected part and run `spine-replace-run --replacement-image <image> --selected-parts-json <selection.json>`. The image is contained inside the original region; `--scale-percent` (10-100), `--offset-x-percent` / `--offset-y-percent` (-100 to 100), and `--rotation-degrees` (-180 to 180) control its layout. Defaults are 100, 0, 0, and 0. `--remove-bg-method none` is the default and costs 0 credits; `standard` removes the background for 5 credits. Inputs must be static PNG, JPEG, WebP, or AVIF files no larger than 25 MB or 16 MP. The command returns only the final Spine ZIP.

Use `spine-cleanup-run --source-spine-package <package.zip> --project-id <project> --thread-id <thread>` when an editor layout package contains visible frames or labels. Cleanup uses atlas region coordinates and embedded layout frame width, never pixel color, removes editor-only `spineviewer-*` metadata, and returns only a new final Spine ZIP. The source package is not changed.

Use `spine-reskin-run --source-spine-package <package.zip> --prompt <look> --project-id <project> --thread-id <thread>` for a complete uploaded-package reskin. It uses textured attachments across all skins, keeps atlas modules smaller than 1400px² unchanged, and packs every remaining module into one sheet. The sheet is 1024×1024 for `--resolution 1K` and 2048×2048 for `--resolution 2K`; modules are proportionally scaled down only when needed to fit. Generation and backfill use the same size-and-position-preserving path as `spine-edit-run`. Defaults match the web product: Nano Banana, 2K, and Standard quality. `--skin-name` selects the attachments and one optional `--reference-image` guides appearance.

## Generate or extract game UI

Generate a UI sheet:

```bash
python3 skills/game-assets/meowart_api.py ui-gen-run \
  --prompt "A cohesive fantasy inventory UI sheet with panels, tabs, item slots, and buttons" \
  --mode generate \
  --resolution 2K \
  --aspect-ratio 4:3 \
  --quality standard \
  --generation-model image-2.5 \
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
  --quality standard \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- Repeat `--reference-image` for up to eight references.
- Extract mode requires at least one reference image.
- Supported aspect ratios are 4:3, 3:4, 16:9, 9:16, and 1:1.
- Treat `1K` and `2K` as service resolution tiers, not promises of one universal pixel dimension; inspect the saved image for its actual dimensions.
- Use `standard` for quick drafts, `detailed` for normal production work, and `ultimate` for a final asset whose small text or dense ornament needs the highest fidelity.
- The default model is `image-2.5` with `--quality standard`. Select `--generation-model nano-banana` or `image-2` to switch models; Image 2 defaults to `--quality detailed`. Image 2.5 charges 1/5/10 credits at 1K or 2/10/20 at 2K plus 2 credits per reference, and provides native standard background removal at no extra cost; `advanced` is unavailable. Background removal and component splitting are enabled by default and can be disabled with `--no-remove-background` and `--no-split-components`.
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
- Model and resolution defaults are concrete in the parsed request: Pixel uses Nano Banana / 1K, HD uses Image2 / 2K. Explicit choices are preserved.

## Clone assets

Use `asset-clone-run --reference-image <source.png> --clone-count 4 --prompt "A sword, a dagger, a red gem, a blue shield" --output-dir <output-dir>` for a complete 2×2 sheet. Repeat `--reference-image` for more references. Inputs must share dimensions; when they do not, specify `--cell-width`, `--cell-height`, and `--fit-mode pad|crop` for centered correction without scaling. Pixel and HD both default to Image2.5, 1K, and Detailed quality with standard background removal. Pixel mode enables regional quantization and three complete pixelation variants. Nano Banana uses fixed Standard quality and defaults to no background removal; Image2.5 defaults to standard background removal. Use `--quality standard|detailed|ultimate` for Image2.5. Canvas selection follows Universal Edit. Pixel scale must be at least 2; HD scale must be at least 0.5. Oversize references are rejected before composition or charging.

Model selection for asset cloning:

- **Color fidelity:** GPT Image2.5 offers richer, more vivid colors and better reproduction of the reference palette. Nano Banana uses more conservative palettes and may depart from the reference colors.
- **Shape control:** Nano Banana provides stronger control over silhouettes, crisp pixel edges, and consistent volume and scale, making it preferable for pixel assets with strict shape and size constraints. GPT Image2.5 has weaker pixel texture and is more prone to size variation.
- **Background removal:** GPT Image2.5 adds no background-removal credits. Nano Banana charges extra when background removal is enabled; use the current quote.

Generation skips prompt optimization by default (`--skip-prompt-optimization` is already enabled). Omit `--prompt` to use `参考图 1 的布局，生成1 个不同外观的美术资产，保持美术风格一致。`, with its quantity replaced by `--clone-count` (default 1). An explicit `--prompt` replaces the entire default and is used verbatim. Use `asset-clone-prompt --clone-count 4 --prompt "..."` only when polishing is requested; it generates no image but rewrites the base quantity to that count. Inspect its result and pass it to `asset-clone-run --prompt <polished-prompt>`.

### Match the count to the input

`--clone-count` controls reference-grid cells and accepts only **1, 4, 9, 16, 25, or 36** (n²).

- **Separate images:** match their count where possible; four one-object images normally use `4`. For non-square counts, default to the next supported square and explain that missing cells repeat references; excess references are ignored.
- **One composite image:** count its actual N objects in the prompt. Keep `--clone-count 1` to preserve the whole layout, but change `生成1 个` to `生成N 个`. Setting the flag to N repeats the entire image across N cells; it does not split objects.
- **Prompt/grid mismatch:** pass a complete prompt with the intended N; generation preserves it. Example: one image of four props uses `--clone-count 1 --prompt "参考图 1 的布局，生成4 个不同外观的道具，保持美术风格一致。"`. Avoid `asset-clone-prompt` here because polishing rewrites the base count to the flag's value.

### Help the user adjust the prompt

For `--clone-count 4`, the built-in prompt is `参考图 1 的布局，生成4 个不同外观的美术资产，保持美术风格一致。`. For custom requirements, start from this sentence, replace `美术资产` with `角色`, `道具`, `图标`, or `UI` if needed, append only the desired changes, and pass the full text through `--prompt`.

Offer only examples relevant to the request:

| Goal | Short text to append |
|---|---|
| Preserve proportions and scale | `保持参考物体的宽高比例、视角和在格子中的大小，不拉伸。` |
| Set a shared palette | `所有物体以蓝色和银色为主。` |
| Vary one object type | `四颗不同外观的宝石：红色菱形，蓝色水滴形，绿色六边形，紫色圆形。` |
| Specify four different objects | `红色短剑，蓝色圆盾，绿色药瓶，金色钥匙。` |

Combine a shared constraint and a comma-separated list when needed: `参考图 1 的布局，生成4 个不同外观的道具，保持美术风格一致。保持参考物体的宽高比例、视角和在格子中的大小，不拉伸。红色短剑，蓝色圆盾，绿色药瓶，金色钥匙。`

Keep `--clone-count` for the reference grid and the prompt for the intended object count as explained above. When specifying every object, list exactly the intended N; a broad request such as `四个不同外观的药瓶` needs no invented item list. Proportion wording guides generation and does not guarantee exact pixel dimensions or geometry. Cell dimensions and `--fit-mode` control reference preparation, not the generated silhouette.

Show the final prompt before generation; it will be used directly. Polish only when requested, and inspect that proportions, colors, and item descriptions survived. Showing the prompt does not require an extra approval round when generation is already authorized.

## Edit still images

Pixel and HD both default to `--remove-bg-method standard`; choose `none` to preserve the background. HD defaults to Image2.5 / 2K with free native removal. See [Transparent asset tips](pixel-and-hd-assets.md#image25-transparent-asset-tips) for limits and existing-image costs.

```bash
python3 skills/game-assets/meowart_api.py image-edit-run \
  --reference-image <source.png> \
  --prompt "Replace the wooden shield with a round bronze shield while preserving the pose" \
  --mode pixel \
  --strict \
  --generation-model nano-banana \
  --resolution 1K \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

- Provide one to eight reference images.
- Use pixel mode for pixel assets and HD mode for smooth artwork.
- Use `--strict` only when pixel structure must remain exact.
- Use `--regional-pixelation` for a multi-asset image whose detected regions need separate pixel-size handling. It is mutually exclusive with `--strict` and adds the same 2-credit product add-on shown on the web.
- Use `--multi-pixelation` to receive three pixelated results at no extra charge. Regional pixelation enables it by default; add `--no-multi-pixelation` to receive one result. It also works without regional pixelation.
- Omitted options follow the web editor's mode defaults: pixel editing uses Nano Banana at 1K, while HD editing uses Image2.5 at 2K. An explicit `--generation-model` or `--resolution` overrides that mode default.
- `--quality standard|detailed|ultimate` applies to Image-2. Nano Banana has no speed option.
- Pixel mode supports `none`, `standard`, and `advanced` background removal. HD edits keep their normal background unless the dedicated background-removal command is used afterward.

## Edit a user-marked region with Nano Banana

When the user supplies an original image and a mask, pass both as ordinary reference images through `general-image-run --generation-model nano-banana`. The mask guides the edit through the prompt; no separate mask parameter is needed.

- Keep the original and mask on the same canvas, with matching dimensions and orientation. Do not resize or crop them independently.
- Send the original first and the mask second. State which image is which and what the mask colors mean. For a black-and-white mask, use white for the edit region and black for the preserved region; follow the user's convention if different, and clarify ambiguous markings before submitting.
- Describe only the requested change, the edit boundary, and what to preserve. Tell the model to return the edited original without the mask or markings.

```bash
python3 skills/game-assets/meowart_api.py general-image-run \
  --generation-model nano-banana \
  --reference-image <original.png> \
  --reference-image <mask.png> \
  --prompt "Image 1 is the original; image 2 is its mask. Replace the sofa only where the mask is white with a brown leather sofa. Preserve everything under black. Return the edited original without mask markings." \
  --resolution 1K \
  --aspect-ratio 1:1 \
  --output-dir <output-dir>
```

Choose the supported aspect ratio that matches the original. If the user also supplies a copy of the original with a translucent colored overlay, send original → overlay → black-and-white mask and update the prompt's image numbers and color meanings. This optional three-image technique comes from [NanoBananaEditor](https://github.com/markfulton/NanoBananaEditor/blob/main/docs/architecture.md#masked-edits); it is not required for the two-image use case.

Compare the result with the original inside and outside the mask, checking alignment, unwanted changes, and residual markings. Prompt guidance does not guarantee pixel-identical preservation outside the mask; exact preservation requires compositing the generated edit onto the original with the mask. Keep the original and mask as inputs, not deliverables. Recover interrupted jobs with `general-image-poll` and the original job ID.

## Edit animated frames

```bash
python3 skills/game-assets/meowart_api.py animation-edit-run \
  --animation-file <walk.webp> \
  --reference-image <armor-reference.png> \
  --prompt "Apply the armor design consistently to every frame" \
  --mode pixel \
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

### 通用生成 Image 2.5

通用生成使用 `general-image-run --generation-model image-2.5|image-2|nano-banana`；默认 Image2.5，旧命令继续兼容。模型选项与条件参数见 [生成指南](pixel-and-hd-assets.md#general-generation-hd-or-pixel-style)。

`general-image-run --prompt "..."` 使用 Image 2.5 Sunburst；默认 `--quality standard`。
质量仅支持 `standard/detailed/ultimate`，对应网页 普通/精细/极致 与 canonical `low/medium/high`。
`--resolution 1K|2K` 默认 1K；`--aspect-ratio` 默认 1:1，支持 1:1、3:4、4:3、9:16、16:9。
可重复 `--reference-image` 传参考图；失败或中断用 `general-image-poll --job-id ...` 恢复，勿重复提交。
1K 基础积分为 1/5/10，2K 为 2/10/20；每张参考图另加 2 积分，由服务端结算。

万能编辑支持 `image-edit-run --generation-model image-2.5`，参数与 `image-2` 相同。普通／精细／极致基础积分：1K 为 1/5/10，2K 为 2/10/20；每张参考图 +2。Image2.5 去背景免费，只提供普通抠图；失败则不去背景、不扣附加费。分区像素化沿用现有附加费。


Image2.5 通用生成支持 `--remove-bg-method none|standard`，默认 `none`，与网页去背景开关一致。开启后尝试原生透明 PNG，免费；失败则保留原背景、不后处理、不扣附加费。万能编辑选择 Image2.5 时同样免费，高级抠图不可用。重新打开项目或轮询原任务不会再次提交生成。

Two-head Spine uses GPT Image 2.5 (`image-2.5`, default) or GPT Image 2 (`image-2`). `--quality standard/detailed/ultimate` selects a 25/35/55-credit package. Every image is generated at Standard quality. Export size does not add credits. The four-head template and existing part-edit/full-reskin commands retain their original model and pricing contracts.

## Full Spine editor

`spine-editor-open --project-id ID --node-id ID` returns the authenticated web workbench URL. Use it for translate/rotate keys, animation creation/copy/deletion, linear/stepped interpolation, pose-key resampling, project drafts, atlas editing and validated joint rebinding. Parameters and defaults come from the web editor; do not build a separate CLI parameter surface. Rebind candidates require comparison and explicit acceptance before applying to the canvas.
