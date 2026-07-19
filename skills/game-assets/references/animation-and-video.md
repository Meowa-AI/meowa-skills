# Animation and video

## Important guidance

### Seamless images

Use seamless-image processing mainly for horizontally scrolling backgrounds, vertically scrolling backgrounds, or large repeating maps such as those used by survivor-style games.

### Sprite animation

- Treat the supplied image as the first animation frame. For walking, prepare a walking start pose first with `image-edit-run`, or use an eight-direction character set to prepare several viewing angles. For an attack, prepare the attack's starting pose first.
- The source image dimensions become the animation canvas, so leave enough empty space in the movement direction. A rightward slash needs room on the right; a jump needs room above; every other action needs space along its motion path. Insufficient canvas space is one of the most common causes of poor animation output. Review the source and expand its canvas before generation when needed.
- Re-edit a generated GIF or WebP with `animation-edit-run` to change character appearance or effects at lower cost. Frame editing can reskin the animation, but it generally cannot change the underlying motion.

### Short video

Use video for HD material or unusually complex motion when higher visual detail is required. Prefer sprite animation for ordinary game animation whenever it can represent the action.

## Purpose

Use this module only after the source still asset is visually stable. Choose seamless processing for a repeating background, sprite animation for frame-oriented game motion, or short video for a rendered clip.

| Capability | Command | Final role | Main limitation |
|---|---|---|---|
| Make an image seamless | `self-loop-run` | Produce a horizontally, vertically, or four-way repeating image | Inspect the repeated seam; mode names are not interchangeable |
| Create sprite animation | `animate-run` | Produce WebP, GIF, or a sprite sheet | Requires stable silhouette, anchor, and transparency |
| Create a short video clip | `video-run` | Animate a first frame or a first-to-last-frame transition | Video is not a sprite-sheet replacement |

Use `animation-edit-run` from the UI and image-editing module when the source is already an animated GIF or WebP and the user wants to preserve its timing rather than design a new motion.

## Seamless image motion

```bash
python3 skills/game-assets/meowart_api.py self-loop-run \
  --image-file <background.png> \
  --mode full \
  --direction horizontal \
  --resolution 1K \
  --output-dir <output-dir>
```

- Use `basic` for single-direction seam completion, `full` for four-way continuity, and `texture` for four-way continuity with texture-specific fixed processing.
- Use `horizontal` for side-scrolling backgrounds and `vertical` for vertical motion.
- Inspect the seam by repeating the output at least twice in the loop direction.

## Sprite animation

```bash
python3 skills/game-assets/meowart_api.py animate-run \
  --image-file <character.png> \
  --prompt "A compact eight-frame idle animation with subtle breathing and cloth movement" \
  --is-pixel \
  --output-frames 8 \
  --output-format webp \
  --animation-type idle \
  --remove-bg-method standard \
  --output-dir <output-dir>
```

Output formats are WebP, GIF, or spritesheet. Stable animation types are `idle`, `walk`, `run`, `jump`, `attack`, `hit`, `defeated`, and `other`.

Use the default eight output frames unless the user requests a different animation budget. Frame counts must be even: pixel animation supports 2–16 frames and HD animation supports 2–24 frames. The compatibility CLI does not enforce these ranges before submission, so validate them before running.

Keep prompts motion-focused. Specify the action, intensity, camera behavior, loop requirement, and what must stay fixed. For pixel art, preserve the source silhouette, palette, and hard edges.

## Short video

Create from a first frame:

```bash
python3 skills/game-assets/meowart_api.py video-run \
  --first-frame <start.png> \
  --prompt "The knight raises the shield, braces, and returns to the starting stance; locked camera" \
  --resolution 480p \
  --aspect-ratio 1:1 \
  --frame-count 32 \
  --animation-type idle \
  --output-dir <output-dir>
```

Create a transition with an explicit last frame:

```bash
python3 skills/game-assets/meowart_api.py video-run \
  --first-frame <start.png> \
  --last-frame <end.png> \
  --prompt "A clean attack transition from the first pose to the final pose; locked camera" \
  --resolution 720p \
  --aspect-ratio 16:9 \
  --frame-count 48 \
  --animation-type attack \
  --output-dir <output-dir>
```

Supported frame counts are 32, 40, and 48. Supported aspect ratios are 16:9, 4:3, 1:1, 3:4, and 9:16. Use `--pixel` for pixel-art motion.

Instead of a free-form prompt, action templates may be selected with both `--action` and `--direction`. Never pass only one of the pair.

## Validate

- Play the final animation or video from start to finish.
- Check frame count, duration, dimensions, alpha, and output format.
- Check the loop boundary for idle, walk, run, or looping background motion.
- Confirm the camera does not drift unless the prompt explicitly requests it.
- Confirm pixel animation remains crisp at integer zoom.
- Deliver only files listed in `final_outputs.json`.
