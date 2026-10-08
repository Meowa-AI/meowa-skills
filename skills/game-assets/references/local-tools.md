# Local tools

Executable tools live in `scripts/`. Run `python3 <skill-dir>/scripts/<tool>.py --help`; underscore-prefixed files are shared helpers, not commands. Install or update the complete Skill directory so helpers remain available. Local tools do not need an API key or network access.

## Complex-pattern splitting

```bash
python3 <skill-dir>/scripts/split-components.py sheet.png --output-dir components
```

Use for separated irregular assets on a transparent or solid-color background. This reproduces the web complex-pattern splitter: alpha takes precedence when any pixel is translucent; otherwise the median border color identifies exterior background. Enclosed background-colored details remain intact. Connected/touching shapes remain one component; this is not semantic segmentation or fixed-grid SpriteSheet splitting.

Only Python standard-library modules are used. Input must be a static, non-interlaced PNG: 8-bit RGB/RGBA/grayscale/grayscale-alpha, or 1/2/4/8-bit indexed/grayscale. Convert JPEG/WebP, animated or 16-bit/interlaced PNGs to a supported static PNG first using an available image editor. Do not install dependencies automatically or send the image to an API for this tool.

Defaults match the web splitter:

| Option | Default | Meaning |
|---|---|---|
| `--alpha-threshold` | 8 | Keep pixels with alpha greater than this value (0–255) |
| `--background-tolerance` | 8 | Per-channel tolerance around the border color (0–255) |
| `--connectivity` | 8 | Diagonal pixels connect; use 4 for edge adjacency only |
| `--min-component-area` | 16 | Ignore smaller regions (1–100000 pixels) |
| `--padding-px` | 0 | Crop margin, clipped to the source (0–512 pixels) |
| `--no-merge-contained-fragments` | Merging enabled | Disable attaching small islands contained within a larger region's bounding box |
| `--fragment-max-area` | 256 | Largest mergeable island (1–100000 pixels) |
| `--fragment-max-area-ratio` | 0.02 | Island-to-parent area limit (0–1) |

The source is unchanged; output must be a new or empty directory. Limits match the backend: 16,777,216 source pixels, 256 components, 16,777,216 total crop pixels, and 24 MiB of output PNGs. Excess components are omitted with `component_limit_reached` in `warnings`; do not claim a complete split when that warning appears. A size/encoding failure exits nonzero and may leave partial PNGs without a completed manifest; retry in a new directory.

Outputs are `component_001.png`, etc., sorted by descending foreground area, then top and left. `final_outputs.json` lists each final file, its `bbox` (`[x0,y0,x1,y1]`, exclusive right/bottom), dimensions and foreground `pixel_count`, plus canonical parameters and warnings. Place a crop back at `(x0,y0)` to preserve the source layout. The manifest contains no source path, raw responses, masks or intermediate media. Inspect outputs at native size or an integer nearest-neighbor zoom before handing them off.
