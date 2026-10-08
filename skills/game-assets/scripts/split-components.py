#!/usr/bin/env python3
"""Split complex patterns locally into transparent PNGs; Python standard library only."""

import argparse
from array import array
import json
from pathlib import Path
import re
from statistics import median
import time

from _png import MAX_PIXELS, read_png, write_png

MAX_COMPONENTS = 256
MAX_OUTPUT_BYTES = 24 * 1024 * 1024


def label_runs(mask, width, height, connectivity, min_area=1):
    """Label horizontal runs with union-find, avoiding a Python object per pixel."""
    parents = array("I", [0])
    stats = [array("I", [0]) for _ in range(5)]  # area, left, top, right, bottom
    runs = array("I")  # y, left, right, provisional label

    def root(label):
        while parents[label] != label:
            parents[label] = parents[parents[label]]
            label = parents[label]
        return label

    previous = []
    diagonal = int(connectivity == 8)
    for y in range(height):
        current = []
        cursor = 0
        for match in re.finditer(b"\x01+", mask[y * width:(y + 1) * width]):
            left, right = match.span()
            while cursor < len(previous) and previous[cursor][1] <= left - diagonal:
                cursor += 1
            label = 0
            for index in range(cursor, len(previous)):
                px0, px1, candidate = previous[index]
                if px0 >= right + diagonal:
                    break
                candidate = root(candidate)
                if not label:
                    label = candidate
                elif candidate != label:
                    parents[candidate] = label
                    stats[0][label] += stats[0][candidate]
                    for field in (1, 2):
                        stats[field][label] = min(stats[field][label], stats[field][candidate])
                    for field in (3, 4):
                        stats[field][label] = max(stats[field][label], stats[field][candidate])
            if not label:
                label = len(parents)
                parents.append(label)
                for field, value in zip(stats, (0, left, y, right, y + 1)):
                    field.append(value)
            stats[0][label] += right - left
            stats[1][label] = min(stats[1][label], left)
            stats[3][label] = max(stats[3][label], right)
            stats[4][label] = y + 1
            current.append((left, right, label))
            runs.extend((y, left, right, label))
        previous = current
    for offset in range(3, len(runs), 4):
        runs[offset] = root(runs[offset])
    components = [
        (label, *(field[label] for field in stats))
        for label in range(1, len(parents)) if parents[label] == label and stats[0][label] >= min_area
    ]
    return runs, components


def foreground_mask(rgba, width, height, alpha_threshold, background_tolerance):
    alpha = rgba[3::4]
    if min(alpha) < 255:
        return alpha.translate(bytes(int(value > alpha_threshold) for value in range(256)))
    channels = [rgba[channel::4] for channel in range(3)]
    bounds = []
    for channel in channels:
        border = channel[:width] + channel[-width:] + channel[::width] + channel[width - 1::width]
        background = median(border)
        bounds.append((max(0, int(background - background_tolerance)), min(255, int(background + background_tolerance))))
    candidates = bytearray(
        int(bounds[0][0] <= red <= bounds[0][1]
            and bounds[1][0] <= green <= bounds[1][1]
            and bounds[2][0] <= blue <= bounds[2][1])
        for red, green, blue in zip(*channels)
    )
    runs, components = label_runs(candidates, width, height, 8)
    exterior = {label for label, area, left, top, right, bottom in components
                if left == 0 or top == 0 or right == width or bottom == height}
    mask = bytearray(b"\x01") * (width * height)
    for offset in range(0, len(runs), 4):
        y, left, right, label = runs[offset:offset + 4]
        if label in exterior:
            mask[y * width + left:y * width + right] = b"\0" * (right - left)
    return mask


def group_components(components, merge, max_area, max_ratio):
    components.sort(key=lambda c: (-c[1], c[3], c[2]))
    groups = [[component] for component in components]
    removed = set()
    if merge:
        for child_index in range(len(components) - 1, -1, -1):
            child = components[child_index]
            if child[1] > max_area or max_ratio == 0:
                continue
            candidates = []
            for parent_index, parent in enumerate(components):
                if parent[1] <= child[1] or child[1] > parent[1] * max_ratio:
                    break  # Remaining parents are smaller in this area-sorted list.
                if parent_index == child_index or parent_index in removed:
                    continue
                if (child[2] >= parent[2] and child[3] >= parent[3]
                        and child[4] <= parent[4] and child[5] <= parent[5]):
                    candidates.append(parent_index)
            if candidates:
                parent_index = min(candidates, key=lambda i: components[i][1])
                groups[parent_index].append(child)
                removed.add(child_index)
    groups = [group for index, group in enumerate(groups) if index not in removed]
    groups.sort(key=lambda g: (-sum(c[1] for c in g), min(c[3] for c in g), min(c[2] for c in g)))
    return groups


def split_image(input_image, output_dir, *, alpha_threshold=8, background_tolerance=8,
                connectivity=8, min_component_area=16, padding_px=0,
                merge_contained_fragments=True, fragment_max_area=256,
                fragment_max_area_ratio=0.02):
    output_dir = Path(output_dir)
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("output directory must be new or empty; source files are never overwritten")
    started = time.perf_counter()
    width, height, rgba = read_png(input_image)
    mask = foreground_mask(rgba, width, height, alpha_threshold, background_tolerance)
    runs, components = label_runs(mask, width, height, connectivity, min_component_area)
    groups = group_components(components,
                              merge_contained_fragments, fragment_max_area, fragment_max_area_ratio)
    warnings = ["component_limit_reached"] if len(groups) > MAX_COMPONENTS else []
    groups = groups[:MAX_COMPONENTS]
    records, destinations = [], {}
    total_pixels = 0
    for index, group in enumerate(groups, 1):
        x0 = max(0, min(c[2] for c in group) - padding_px)
        y0 = max(0, min(c[3] for c in group) - padding_px)
        x1 = min(width, max(c[4] for c in group) + padding_px)
        y1 = min(height, max(c[5] for c in group) + padding_px)
        total_pixels += (x1 - x0) * (y1 - y0)
        if total_pixels > MAX_PIXELS:
            raise ValueError("total component output exceeds the pixel limit; reduce padding or component count")
        records.append({"id": f"component_{index:03d}", "file": f"component_{index:03d}.png",
                        "bbox": [x0, y0, x1, y1], "width": x1 - x0, "height": y1 - y0,
                        "pixel_count": sum(c[1] for c in group)})
        for component in group:
            destinations[component[0]] = index - 1
    # Store only selected runs; render one crop at a time to bound raster memory.
    selected_runs = [array("I") for _ in groups]
    for offset in range(0, len(runs), 4):
        y, left, right, label = runs[offset:offset + 4]
        destination = destinations.get(label)
        if destination is not None:
            selected_runs[destination].extend((y, left, right))
    output_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for record, crop_runs in zip(records, selected_runs):
        x0, y0, x1, y1 = record["bbox"]
        crop = bytearray(record["width"] * record["height"] * 4)
        for offset in range(0, len(crop_runs), 3):
            y, left, right = crop_runs[offset:offset + 3]
            source = (y * width + left) * 4
            target = ((y - y0) * record["width"] + left - x0) * 4
            size = (right - left) * 4
            crop[target:target + size] = rgba[source:source + size]
        path = output_dir / record["file"]
        write_png(path, record["width"], record["height"], crop)
        total_bytes += path.stat().st_size
        if total_bytes > MAX_OUTPUT_BYTES:
            raise ValueError("total component PNGs exceed 24 MiB; reduce image size or component count")
    result = {"image_size": [width, height], "component_count": len(records),
              "parameters": {"alpha_threshold": alpha_threshold, "background_tolerance": background_tolerance,
                             "connectivity": connectivity, "min_component_area": min_component_area,
                             "padding_px": padding_px, "merge_contained_fragments": merge_contained_fragments,
                             "fragment_max_area": fragment_max_area, "fragment_max_area_ratio": fragment_max_area_ratio},
              "warnings": warnings, "components": records,
              "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
    (output_dir / "final_outputs.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _bounded_number(converter, minimum, maximum):
    def parse(value):
        number = converter(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between {minimum} and {maximum}")
        return number
    return parse


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_image", type=Path, help="Static PNG with transparency or a solid background")
    parser.add_argument("--output-dir", type=Path, required=True, help="New or empty output directory")
    for name, default, minimum, maximum in (
        ("alpha-threshold", 8, 0, 255), ("background-tolerance", 8, 0, 255),
        ("min-component-area", 16, 1, 100000), ("padding-px", 0, 0, 512),
        ("fragment-max-area", 256, 1, 100000),
    ):
        parser.add_argument("--" + name, type=_bounded_number(int, minimum, maximum), default=default)
    parser.add_argument("--connectivity", type=int, choices=(4, 8), default=8)
    parser.set_defaults(merge_contained_fragments=True)
    parser.add_argument("--no-merge-contained-fragments", action="store_false", dest="merge_contained_fragments")
    parser.add_argument("--fragment-max-area-ratio", type=_bounded_number(float, 0, 1), default=0.02)
    return parser


def main():
    parser = build_parser()
    options = vars(parser.parse_args())
    try:
        result = split_image(**options)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
