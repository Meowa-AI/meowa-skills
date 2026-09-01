# Animation and video

## Choose the animation route

Use this order rather than routing directly to video:

1. Use `animate-run` for most motion. It is the primary path and returns directly usable frame animation.
2. For an ordinary but complex action, create two or more important poses and use `keyframes-run`. Keyframes constrain the action while preserving frame-animation output, making this preferable to video for attacks, turns, jumps, dodges, and other game actions that need a specific transition.
3. Use `video-run` only when ordinary animation and keyframe control remain insufficient, or when the deliverable genuinely needs higher-resolution video.

## How to create a high-quality animation

Follow this preparation sequence before every `animate-run` or `keyframes-run`:

1. **Start from the action's first pose.** The source image becomes the first animation frame, so do not default to a neutral standing pose for every action. For an attack, start with the character holding the weapon in a ready-to-strike pose. For walking or running, start with the legs already separated, one forward and one back. Jump and idle animations are less sensitive to the starting pose. A correct action-ready first frame lets the model spend its frame budget on the action and return naturally to the starting pose; beginning from an unrelated idle pose creates wind-up or transition frames that often look like waste frames and make a clean loop harder.
2. **Prepare the pose with the appropriate still-image tool.** Use `image-edit-run` when one precise action pose is required; it is the highest-precision route. Use `character-multi-view-run` with an explicit action requirement in `--extra-constraint` when the same pose is needed across several directions. Eight-direction generation is faster for batching, but pose accuracy and directional consistency are usually lower than a focused still edit. Review the pose before animation.
3. **Describe the motion simply.** Use a short, direct action description rather than a complicated story. Good inputs include `The character slashes to the right, with flames on the sword`, `The character makes a small jump in place`, and `The character runs forward`. State the principal action, direction, and one important effect; give the animation model room to resolve the motion.
4. **Use the default prompt enhancement.** `animate-run` and `keyframes-run` enable prompt enhancement by default. The backend reads the source image and the user's motion description, translates non-English input into English, and rewrites it into language that the animation model can understand more reliably. Keep the user's input focused on intent; do not manually add a long technical prompt unless the enhanced result has been reviewed and needs a specific correction.
5. **Route by source size.** `animate-run` reads the source dimensions and automatically uses pixel mode for a PNG whose width and height are both no greater than 256 pixels. When either dimension exceeds 256 pixels, it uses general animation mode. Pixel mode applies pixel-specific motion and edge handling. General mode supports larger pixel artwork, chibi characters, and small HD or 2D characters, but it does not apply pixel-specific optimization, so large pixel-art edges may be less sharp. General-mode inputs must still satisfy its minimum dimensions; pad a narrow source when necessary instead of stretching its content.
6. **Reserve transparent motion space.** The source image dimensions become the animation canvas, and canvas preparation is one of the strongest constraints on final quality. When image or multimodal inspection is available, inspect the source first: identify the visible character bounds, current anchor, facing direction, weapon reach, and likely motion path. A jump needs some room above the head; an attack needs some room in front of the character for the body, weapon, and effects; a backward jump, retreat, or dodge needs room behind. If attack direction is not stated, infer it from the prompt and the character's facing direction when the image makes that clear; otherwise ask or reserve modest space on both sides. The model cannot reliably move into space that does not exist, but excessive empty canvas also makes the subject unnecessarily small relative to the frame. Add enough space for the intended action without maximizing every side. Prompt enhancement cannot compensate for missing canvas space.
7. **Keep pixel characters compact, then pad.** Keep the pixel character content at 128×128 or smaller whenever practical, then expand the transparent canvas without resampling the character. Set top, down, left, and right padding independently for the actual motion path. For a 64px pixel character, prefer a final padded canvas no larger than 128×128. A pixel-animation canvas above 256px on either axis is invalid and will fail, so calculate the final width as `source width + left + right` and final height as `source height + top + down` before submitting. Preserve the subject's anchor, and verify that the subject, weapon, and effects will not touch a required edge during the motion.
8. **Review the prepared source before generation.** Check the visible content bounds, transparent margins, action direction, first pose, scale, and anchor. For keyframe animation, ensure every keyframe uses the same canvas dimensions, anchor, and padding. Insufficient motion space and unsuitable poses are among the most common causes of failed or low-quality animation.

## Capability-specific guidance

### Seamless images

Use seamless-image processing mainly for horizontally scrolling backgrounds, vertically scrolling backgrounds, or large repeating maps such as those used by survivor-style games.

### Sprite animation

- Apply the complete high-quality animation workflow above before generation.
- Use `animate-run` for most game animation. It returns directly usable frame animation, but the general frame mode outputs at no more than 480p even when the source image is much larger.
- Re-edit a generated GIF or WebP with `animation-edit-run` to change character appearance or effects at lower cost. Frame editing can reskin the animation, but it generally cannot change the underlying motion.

### Short video

Use `video-run` only after ordinary animation and keyframe control are unsuitable, or for highly detailed material that needs more resolution than frame animation can provide.

## Purpose

Use this module only after the source still asset is visually stable. Choose seamless processing for a repeating background, sprite animation for frame-oriented game motion, or short video for a rendered clip.

| Capability | Command | Final role | Main limitation |
|---|---|---|---|
| Make an image seamless | `self-loop-run` | Produce a horizontally, vertically, or four-way repeating image | Inspect the repeated seam |
| Create sprite animation | `animate-run` | Produce WebP, GIF, or a sprite sheet | Requires stable silhouette, anchor, and transparency |
| Control frame animation with key poses | `keyframes-run` | Produce frame animation constrained by two or more poses | Every keyframe must share dimensions, anchor, and padding |
| Inspect recommended video prompts | `video-prompt-list` | Review built-in action and direction prompts before generation | Select the same motion mode intended for generation |
| Create a short video clip | `video-run` | Animate a first frame or references into a higher-resolution clip | Returns raw video, not ready-to-use game frames |

Use `animation-edit-run` from the UI and image-editing module when the source is already an animated GIF or WebP and the user wants to preserve its timing rather than design a new motion.

## Seamless image motion

```bash
python3 skills/game-assets/meowart_api.py self-loop-run \
  --image-file <background.png> \
  --variant four-way \
  --generation-speed normal \
  --resolution 1K \
  --output-dir <output-dir>
```

- Use `horizontal` for side-scrolling backgrounds, `vertical` for vertical motion, and `four-way` for continuity on both axes.
- Generation speed mirrors the web control: `normal` or `fast`.
- Inspect the seam by repeating the output at least twice in the loop direction.

## Sprite animation

Do not run this command until the input has passed the preparation sequence above. The runner selects pixel or general animation mode from the PNG source dimensions; do not rely on manually supplying the mode for the 256-pixel boundary.

```bash
python3 skills/game-assets/meowart_api.py animate-run \
  --image-file <character.png> \
  --prompt "A compact eight-frame idle animation with subtle breathing and cloth movement" \
  --output-frames 8 \
  --output-format webp \
  --animation-type idle \
  --animation-model pixel-engine-v1.1 \
  --optimize-prompt \
  --color-count 32 \
  --padding-top 16 \
  --padding-down 8 \
  --padding-left 12 \
  --padding-right 20 \
  --remove-bg-method advanced \
  --background-color '#c6c6c6' \
  --output-dir <output-dir>
```

Output formats are WebP, GIF, or spritesheet. Stable animation types are `idle`, `walk`, `run`, `jump`, `attack`, `hit`, `defeated`, and `other`.

The public model choices are `pixel-engine-v1.1` and `frame-engine-v1.1`. If omitted, the runner mirrors the web source-size default: pixel engine for a PNG at most 256×256, otherwise frame engine. Prompt optimization is enabled by default; use `--no-optimize-prompt` only when the supplied prompt is already final.

For pixel animation, `--color-count` accepts 2–64. The four padding options accept independent non-negative pixel counts and add transparent canvas without resizing the source. The runner validates the resulting pixel canvas before submission, preventing a paid request when either axis would exceed 256px. A 64px character can technically use a canvas above 128px, but 128×128 or smaller is recommended for more consistent animation.

Choose directional padding from the actual action rather than applying the same value everywhere. For example, a compact jump usually needs top padding but little extra horizontal space, while a right-facing sword attack usually needs right padding and only modest padding elsewhere. Visually inspect the prepared source again before submission: the required motion path should have clear transparent space, while the character should still occupy a useful portion of the canvas.

Use 8 frames for most common actions. Use 12 or 16 frames when an action genuinely needs more phases or a slower transition. A 16-frame run has twice the temporal budget of an 8-frame run, so the model may invent an extra motion beat instead of simply improving the same action. When using 16 frames, slow the intended action explicitly with wording such as `jumps gently`, `attacks slowly`, or `moves gradually` to reduce unwanted extra motion. Prefer keyframes when exact intermediate poses matter more than free motion. Frame counts must be even: pixel animation supports 2–16 frames and HD animation supports 2–24 frames. Validate the requested count before running.

Keep prompts motion-focused. Specify the action, intensity, camera behavior, loop requirement, and what must stay fixed. For pixel art, preserve the source silhouette, palette, and hard edges.

## Frame animation (new)

```bash
python3 skills/game-assets/meowart_api.py meowa-animation-run \
  --image-file <character.png> \
  --prompt "Character performs one attack and returns to the starting pose" \
  --style-mode pixel \
  --resolution 480p \
  --alpha-mode sharp \
  --output-frames 16 \
  --quality-mode standard \
  --remove-bg-method standard \
  --background-color '#c6c6c6' \
  --animation-mode loop \
  --optimize-prompt \
  --padding 16 \
  --padding-alignment center \
  --output-dir <output-dir>
```

The defaults mirror the web UI: 16 frames (2 seconds), Pixel Style, 480P, Detailed quality for Pixel and Standard quality for HD, standard background removal, a `#c6c6c6` solid background, loop motion, and prompt optimization enabled. Frame choices are 8, 16, 24, and 32. Pixel inputs must not exceed 256 pixels on the longest side and use 480P; HD inputs do not use that dimension limit and support 480P or 720P. HD 720P costs 10 extra credits. Pixel always uses sharp alpha edges. HD defaults to `--alpha-mode soft` and also supports `sharp`. Background removal choices are `none` and `standard`; `advanced` remains visible but is temporarily unavailable. Standard and Detailed output quality are available; Ultimate remains visible in the product but is still in development.

Add `--last-image-file <last-frame.png>` for first-to-last-frame control. The two images must have identical dimensions. When a last frame is supplied, the runner ignores `--animation-mode loop` and submits `non_loop`, because the exact last frame is the endpoint.

Use `--style-mode hd` for smooth high-definition output. HD supports `none` and `standard` background removal; `advanced` is temporarily unavailable. Source padding stays independent from style and is applied before generation. The final downloaded WebP always loops; `--animation-mode` controls the motion design rather than the playback metadata.

## Keyframe-controlled animation

Use keyframes for ordinary complex actions before falling back to video. Include frame `0`, add one or more important intermediate or final poses, and keep every image on the same canvas with the same character scale, anchor, and transparent padding.

```bash
python3 skills/game-assets/meowart_api.py keyframes-run \
  --keyframe 0=<attack-start.png> \
  --keyframe 4=<attack-impact.png> \
  --keyframe 7=<attack-recovery.png> \
  --keyframe-strength 4=0.85 \
  --prompt "The character performs one clear rightward sword attack and returns to the starting stance" \
  --total-frames 8 \
  --output-format webp \
  --animation-type attack \
  --color-count 32 \
  --padding-top 8 \
  --padding-down 8 \
  --padding-left 4 \
  --padding-right 24 \
  --remove-bg-method advanced \
  --output-dir <output-dir>
```

Frame indices begin at `0` and must be smaller than `--total-frames`. Supply at least two unique keyframes, including frame `0`. Use an even total frame count. Keep the prompt simple and describe the transition shared by the supplied poses.

Repeat `--keyframe-strength INDEX=STRENGTH` for any keyframe that needs a non-default strength from 0 to 1. Keyframe runs expose the same animation model and prompt-optimization controls as ordinary animation.

## Short video

Review the built-in action prompts before writing a custom prompt:

```bash
python3 skills/game-assets/meowart_api.py video-prompt-list \
  --motion-mode controlled
```

Use `controlled` when the final keyframe must be followed closely. Use `complex` when the motion is more complex and general video quality matters more than strict first-to-last-keyframe control.

Keep video prompts short, clear, and literal. Video models follow long or complicated instructions less reliably than language or image-generation models. Describe the subject, one principal action, its direction, and at most one important effect. Use a built-in `--action` and `--direction` prompt when it already matches the request.

Create from a first frame:

```bash
python3 skills/game-assets/meowart_api.py video-run \
  --start-keyframe <start.png> \
  --prompt "The knight raises the shield, braces, and returns to the starting stance; locked camera" \
  --resolution 480p \
  --frame-count 32 \
  --motion-mode complex \
  --animation-type idle \
  --output-dir <output-dir>
```

Create a transition controlled by explicit start and end keyframes:

```bash
python3 skills/game-assets/meowart_api.py video-run \
  --start-keyframe <start.png> \
  --end-keyframe <end.png> \
  --prompt "A clean attack transition from the first pose to the final pose; locked camera" \
  --resolution 720p \
  --frame-count 48 \
  --motion-mode controlled \
  --animation-type attack \
  --output-dir <output-dir>
```

`--first-frame` and `--last-frame` remain aliases for `--start-keyframe` and `--end-keyframe`. Supplying only a start keyframe uses it as the visual reference. Supplying both selects first-to-last keyframe control. The service chooses the output canvas automatically from the prepared references; do not pass or invent an aspect ratio. Supported frame counts are 32, 40, and 48. Use `--pixel` for pixel-art motion. Public `video-run` generations do not generate audio.

Instead of a free-form prompt, action templates may be selected with both `--action` and `--direction`. Never pass only one of the pair.

`video-run` returns the raw generated video. It does not automatically extract frames or remove their backgrounds. Those steps require manual timing, frame selection, and cleanup that AI does not yet handle reliably. Import or drag the video into [Meowa](https://meowa.ai/) for manual editing when game-ready animation frames are required.

## Validate

- Play the final animation or video from start to finish.
- Check frame count, duration, dimensions, alpha, and output format.
- Check the loop boundary for idle, walk, run, or looping background motion.
- Confirm the camera does not drift unless the prompt explicitly requests it.
- Confirm pixel animation remains crisp at integer zoom.
- Deliver only files listed in `final_outputs.json`.
