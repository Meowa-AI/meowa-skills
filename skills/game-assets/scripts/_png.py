"""Small standard-library codec for static, non-interlaced 1/2/4/8-bit PNGs."""

import struct
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PIXELS = 4096 * 4096


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_png(path, width, height, rgba):
    stride = width * 4
    compressor = zlib.compressobj()
    encoded = bytearray()
    for offset in range(0, len(rgba), stride):
        encoded.extend(compressor.compress(b"\0" + rgba[offset:offset + stride]))
    encoded.extend(compressor.flush())
    Path(path).write_bytes(
        SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", encoded) + _chunk(b"IEND", b"")
    )


def read_png(path):
    with Path(path).open("rb") as stream:
        if stream.read(8) != SIGNATURE:
            raise ValueError("input must be a static PNG; convert JPEG/WebP to PNG first")
        compressed = bytearray()
        palette = transparency = b""
        header = None
        while True:
            prefix = stream.read(8)
            if len(prefix) != 8:
                raise ValueError("truncated PNG")
            size, kind = struct.unpack(">I4s", prefix)
            if size > MAX_PIXELS * 5:
                raise ValueError("PNG chunk is too large")
            data, checksum = stream.read(size), stream.read(4)
            if len(data) != size or len(checksum) != 4:
                raise ValueError("truncated PNG chunk")
            if zlib.crc32(kind + data) != struct.unpack(">I", checksum)[0]:
                raise ValueError("invalid PNG checksum")
            if kind == b"IHDR":
                if header is not None or size != 13:
                    raise ValueError("invalid PNG header")
                header = struct.unpack(">IIBBBBB", data)
                width, height, depth, color, compression, filtering, interlace = header
                if not width or not height or width * height > MAX_PIXELS:
                    raise ValueError(f"PNG exceeds the {MAX_PIXELS}-pixel limit or has invalid dimensions")
                if (color not in (0, 2, 3, 4, 6) or depth not in (1, 2, 4, 8)
                        or (depth != 8 and color not in (0, 3))
                        or compression or filtering or interlace):
                    raise ValueError("use a non-interlaced 8-bit PNG (indexed/grayscale also allow 1/2/4-bit)")
            elif header is None:
                raise ValueError("PNG header must be first")
            elif kind == b"acTL":
                raise ValueError("animated PNG is unsupported; export a static frame first")
            elif kind == b"PLTE":
                palette = data
            elif kind == b"tRNS":
                transparency = data
            elif kind == b"IDAT":
                compressed.extend(data)
                if len(compressed) > MAX_PIXELS * 5:
                    raise ValueError("compressed PNG is too large")
            elif kind == b"IEND":
                break
            elif not kind[0] & 32:
                raise ValueError("unsupported critical PNG chunk")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    stride = (width * channels * depth + 7) // 8
    expected = (stride + 1) * height
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(compressed, expected + 1)
    except zlib.error as exc:
        raise ValueError("invalid PNG compressed data") from exc
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError("invalid PNG pixel data")
    bpp = max(1, channels * depth // 8)
    rgba = bytearray(width * height * 4)
    previous = bytearray(stride)
    if transparency and color in (0, 2) and len(transparency) != channels * 2:
        raise ValueError("invalid PNG transparency data")
    transparent_sample = tuple(struct.unpack(">" + "H" * (len(transparency) // 2), transparency)) if color in (0, 2) else ()
    for y in range(height):
        start = y * (stride + 1)
        method = raw[start]
        row = bytearray(raw[start + 1:start + 1 + stride])
        if method not in range(5):
            raise ValueError("invalid PNG filter")
        if method == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif method == 2:
            row = bytearray((value + above) & 255 for value, above in zip(row, previous))
        elif method:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                above = previous[i]
                upper_left = previous[i - bpp] if i >= bpp else 0
                if method == 3:
                    prediction = (left + above) // 2
                else:
                    p = left + above - upper_left
                    pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                    prediction = left if pa <= pb and pa <= pc else (above if pb <= pc else upper_left)
                row[i] = (row[i] + prediction) & 255
        previous = row
        target = y * width * 4
        if color == 6:
            rgba[target:target + width * 4] = row
            continue
        if depth == 8 and color in (0, 2, 4) and not transparency:
            for channel in range(3):
                rgba[target + channel:target + width * 4:4] = row[channel::3] if color == 2 else row[::channels]
            rgba[target + 3:target + width * 4:4] = row[1::2] if color == 4 else b"\xff" * width
            continue
        for x in range(width):
            values = tuple(row[x * channels:(x + 1) * channels])
            if depth < 8:
                values = ((row[x * depth // 8] >> (8 - depth - x * depth % 8)) & ((1 << depth) - 1),)
            if color == 3:
                index = values[0]
                if index * 3 + 3 > len(palette):
                    raise ValueError("invalid PNG palette index")
                pixel = palette[index * 3:index * 3 + 3] + bytes([transparency[index] if index < len(transparency) else 255])
            elif color in (0, 4):
                gray = values[0] * 255 // ((1 << depth) - 1)
                alpha = values[1] if color == 4 else (0 if values == transparent_sample else 255)
                pixel = bytes((gray, gray, gray, alpha))
            else:
                pixel = bytes(values + (0 if values == transparent_sample else 255,))
            rgba[target + x * 4:target + x * 4 + 4] = pixel
    return width, height, rgba
