# Audio

## Important guidance

- Keep most gameplay sound effects around one to two seconds; that duration covers most interaction, combat, and pickup needs.
- A 30-second music preview cannot be extended into the same three-minute track later. Every render is independent, so generate the three-minute version directly when the final deliverable needs full length.

## Purpose

Use this module to create gameplay sound effects, coherent effect packs, variations of one effect, music direction, rendered game music, or spoken character lines.

| Capability | Command | Final role | Main limitation |
|---|---|---|---|
| Create sound effects | `sound-run` | Produce one effect, a coherent pack, or variants | Pack and variant modes are mutually exclusive |
| Draft or render music | `music-run` | Produce a demo or production track | Select the web product's `demo` or `pro` output mode |
| Speak one line | `tts-run` | Produce one spoken clip from a voice description, or clone a voice with `--reference-audio` | One line per job, up to 200 characters; up to 5 reference clips, 1-300 seconds joined |

Finalize gameplay timing, action, and loop intent before generating audio. Visual references may guide music mood, but they do not replace an explicit description of instrumentation, energy, and loop behavior.

## Sound effects

Create one sound:

```bash
python3 skills/game-assets/meowart_api.py sound-run \
  --prompt "A short bright crystal pickup chime with a soft magical tail" \
  --duration 2 \
  --output-dir <output-dir>
```

Create a coherent pack:

```bash
python3 skills/game-assets/meowart_api.py sound-run \
  --prompt "Wooden UI clicks for hover, confirm, cancel, locked, and error states" \
  --sound-pack \
  --count 5 \
  --duration 0.5 \
  --output-dir <output-dir>
```

Create variants of one sound with `--variants`. `--sound-pack` and `--variants` are mutually exclusive. Add `--loop` only when the final effect must loop continuously.

Duration may be 0.5 seconds or an integer from 1 through 10 seconds. Count applies only to packs or variants, may be from 1 through 10, and defaults to 4. Keep prompts concrete: source, material, action, intensity, perspective, ambience, tail, and loop requirement.

The skill never requests or accepts a third-party audio-service credential. Authentication and audio implementation remain server-managed.

## Music

Draft a music direction without rendering audio:

```bash
python3 skills/game-assets/meowart_api.py music-run \
  --prompt "Warm pastoral exploration theme with wooden flute, pizzicato strings, and gentle hand percussion" \
  --output-dir <output-dir>
```

Render a track:

```bash
python3 skills/game-assets/meowart_api.py music-run \
  --prompt "Tense clockwork boss theme with driving strings, metallic percussion, and a clear loop point" \
  --output-mode pro \
  --output-dir <output-dir>
```

Use `--output-mode demo` only when the user explicitly wants the web product's preview mode. Repeat `--reference-image` when visual references should influence mood or instrumentation.

## Speech (TTS)

Speak one character line:

```bash
python3 skills/game-assets/meowart_api.py tts-run \
  --text "一闪一闪亮晶晶，满天都是小星星。" \
  --voice "可爱的小女孩，明亮欢快" \
  --language Chinese \
  --output-dir <output-dir>
```

`--text` is the exact line to speak, counted after trimming, up to 200 characters; longer scripts must be split into one job per line. `--voice` is a natural-language voice description and defaults to `可爱的小女孩，明亮欢快`, the same default the web Speech Generation tab opens with. `--language` defaults to `Chinese` and accepts `Auto`, `English`, `Japanese`, `Korean`, `French`, `German`, `Spanish`, `Portuguese`, `Russian`, or `Italian`.

Add `--optimize-prompt` to mirror the web **AI polish** button (free, description mode only). It first adds natural punctuation and pauses to `--text` without changing any word, and expands a short `--voice` hint such as `女孩，可爱` into a full voice description (gender/age, pitch, pace, timbre, emotion, use), then synthesizes with the polished values. The speech model does not support inline emotion tags such as `[excited]`; emotion is expressed through the voice description instead.

```bash
python3 skills/game-assets/meowart_api.py tts-run \
  --text "今天天气真不错我们一起出去玩吧" \
  --voice "女孩，可爱" \
  --optimize-prompt \
  --output-dir <output-dir>
```

Speech jobs belong to a project. Pass `--project-id` (and optionally `--thread-id`) to reuse an existing project; omit it to create one titled by `--project-title`. Cost is 5 credits per 50 characters (5 / 10 / 15 / 20 credits for up to 50 / 100 / 150 / 200 characters). Recover an interrupted job with `tts-poll --job-id <job-id>`; recovery never resubmits or charges again.

### Clone a voice from reference audio

Add `--reference-audio` to the same command to imitate an existing voice instead of describing one:

```bash
python3 skills/game-assets/meowart_api.py tts-run \
  --text "一闪一闪亮晶晶，满天都是小星星。" \
  --reference-audio ./voice/line-01.wav \
  --reference-audio ./voice/line-02.mp3 \
  --language ZH \
  --output-dir <output-dir>
```

Repeat `--reference-audio` for up to 5 clips (`mp3`, `wav`, `m4a`, `aac`, `flac`, `ogg`, `opus`, `webm`, `mp4`, 25 MB each). Clips are joined in the given order into one reference track that must last 1 to 300 seconds; use clean speech of the target voice without music. In this mode `--voice` must be omitted, and `--language` accepts `ZH`, `EN`, `JA`, `ES`, or `AR` (`Chinese`, `English`, `Japanese`, and `Spanish` are accepted as aliases, so the default `Chinese` becomes `ZH`). Pricing, the 200-character limit, and `tts-poll` recovery are the same as description mode.

## Validate

- Confirm every audio file opens and has the expected duration.
- Listen for clipping, abrupt tails, unintended silence, and obvious seams.
- For loops, test the end-to-start transition in a repeating player.
- For packs, confirm each file is distinct and named or ordered consistently.
- Deliver only files listed in `final_outputs.json`.
