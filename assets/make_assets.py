"""Generate assets/slime.bmp: a 7-frame 64x64 indexed sprite sheet.

Run: python3 assets/make_assets.py
"""

import math

from PIL import Image, ImageDraw

FRAME = 64
POSES = [
    "content",
    "sleepy",
    "curious",
    "happy",
    "contemplative",
    "dizzy",
    "resting",
    "puddle",
    "loaf",
    "explorer",
    "crowned",
    "wisp",
    "spring_form",
    "summer_form",
    "autumn_form",
    "winter_form",
    "melting",
    "hiding",
]
BLACK, GRAY, LIGHT, WHITE = 0, 1, 2, 3  # palette indices


def _blob(d, ox):
    # rounded body
    d.rectangle([ox + 16, 14, ox + 48, 56], fill=BLACK)
    d.rectangle([ox + 10, 22, ox + 54, 56], fill=BLACK)
    d.rectangle([ox + 14, 20, ox + 50, 54], fill=GRAY)


def _eyes(d, ox, y, w=4, h=10, open_=True):
    for ex in (ox + 22, ox + 38):
        if open_:
            d.rectangle([ex, y, ex + w, y + h], fill=BLACK)
        else:
            d.rectangle([ex, y + h // 2, ex + w + 4, y + h // 2 + 2], fill=BLACK)


def draw_pose(d, ox, pose):
    _blob(d, ox)
    if pose == "sleepy":
        _eyes(d, ox, 36, open_=False)
        d.rectangle([ox + 30, 46, ox + 36, 49], fill=BLACK)
    elif pose == "curious":
        _eyes(d, ox, 30, h=12)
        d.rectangle([ox + 30, 46, ox + 36, 50], fill=BLACK)
    elif pose == "happy":
        d.arc([ox + 20, 28, ox + 30, 38], 180, 360, fill=BLACK, width=3)
        d.arc([ox + 36, 28, ox + 46, 38], 180, 360, fill=BLACK, width=3)
        d.arc([ox + 26, 40, ox + 42, 52], 0, 180, fill=BLACK, width=3)
    elif pose == "contemplative":
        _eyes(d, ox, 34, open_=False)
        d.rectangle([ox + 30, 47, ox + 38, 49], fill=BLACK)
    elif pose == "dizzy":
        for ex in (ox + 22, ox + 38):
            d.line([ex, 32, ex + 6, 40], fill=BLACK, width=2)
            d.line([ex + 6, 32, ex, 40], fill=BLACK, width=2)
        d.ellipse([ox + 28, 44, ox + 38, 52], outline=BLACK, width=2)
    elif pose == "resting":
        _eyes(d, ox, 38, open_=False)
    elif pose == "puddle":
        d.rectangle([ox + 8, 44, ox + 56, 56], fill=BLACK)
        d.rectangle([ox + 10, 46, ox + 54, 54], fill=GRAY)
        d.rectangle([ox + 24, 49, ox + 28, 51], fill=BLACK)
        d.rectangle([ox + 36, 49, ox + 40, 51], fill=BLACK)
    elif pose == "loaf":
        d.rectangle([ox + 14, 26, ox + 50, 56], fill=BLACK)
        d.rectangle([ox + 16, 28, ox + 48, 54], fill=GRAY)
        d.rectangle([ox + 24, 40, ox + 32, 42], fill=BLACK)
        d.rectangle([ox + 36, 40, ox + 44, 42], fill=BLACK)
    elif pose == "explorer":
        _blob(d, ox)
        d.rectangle([ox + 22, 8, ox + 42, 16], fill=BLACK)
        d.rectangle([ox + 18, 14, ox + 46, 18], fill=BLACK)
        _eyes(d, ox, 30, h=12)
    elif pose == "crowned":
        _blob(d, ox)
        d.polygon(
            [
                (ox + 22, 14),
                (ox + 28, 4),
                (ox + 32, 12),
                (ox + 38, 2),
                (ox + 44, 12),
                (ox + 50, 4),
                (ox + 44, 14),
            ],
            fill=BLACK,
        )
        _eyes(d, ox, 32)
    elif pose == "wisp":
        d.rectangle([ox + 18, 16, ox + 46, 48], fill=LIGHT)
        d.rectangle([ox + 20, 18, ox + 44, 46], fill=GRAY)
        for wx in (ox + 20, ox + 30, ox + 40):
            d.rectangle([wx, 50, wx + 6, 54], fill=GRAY)
        d.rectangle([ox + 26, 30, ox + 30, 36], fill=BLACK)
        d.rectangle([ox + 36, 30, ox + 40, 36], fill=BLACK)
    elif pose == "spring_form":
        _blob(d, ox)
        d.rectangle([ox + 30, 6, ox + 34, 16], fill=BLACK)  # stem
        d.ellipse([ox + 22, 0, ox + 34, 10], fill=GRAY, outline=BLACK)  # leaf
        _eyes(d, ox, 32)
    elif pose == "summer_form":
        _blob(d, ox)
        d.rectangle([ox + 20, 30, ox + 44, 38], fill=BLACK)  # shades
        d.rectangle([ox + 30, 32, ox + 34, 36], fill=GRAY)
    elif pose == "autumn_form":
        _blob(d, ox)
        d.polygon([(ox + 32, 4), (ox + 26, 14), (ox + 38, 14)], fill=GRAY, outline=BLACK)  # leaf
        _eyes(d, ox, 32)
    elif pose == "winter_form":
        _blob(d, ox)
        d.rectangle([ox + 10, 44, ox + 54, 52], fill=BLACK)  # scarf
        _eyes(d, ox, 32)
    elif pose == "melting":
        d.rectangle([ox + 12, 40, ox + 52, 58], fill=BLACK)
        d.rectangle([ox + 14, 42, ox + 50, 56], fill=GRAY)
        d.rectangle([ox + 20, 56, ox + 24, 62], fill=GRAY)  # drips
        d.rectangle([ox + 40, 56, ox + 44, 62], fill=GRAY)
        d.rectangle([ox + 26, 48, ox + 32, 51], fill=BLACK)
        d.rectangle([ox + 36, 48, ox + 42, 51], fill=BLACK)
    elif pose == "hiding":
        d.rectangle([ox + 16, 30, ox + 48, 58], fill=BLACK)
        d.rectangle([ox + 18, 32, ox + 46, 56], fill=GRAY)
        d.rectangle([ox + 22, 44, ox + 42, 50], fill=BLACK)  # peeking slit
        d.rectangle([ox + 28, 46, ox + 32, 49], fill=GRAY)
        d.rectangle([ox + 34, 46, ox + 38, 49], fill=GRAY)
    else:  # content
        _eyes(d, ox, 34)
        d.rectangle([ox + 28, 47, ox + 40, 50], fill=BLACK)


def _status_icons():
    """10 grayscale 12x12 tiles: sun, cloud, rain, storm, heat, moon, wifi-live, wifi-stale,
    mail-unread, mail-fresh."""
    n, sz = 10, 12
    img = Image.new("P", (sz * n, sz), WHITE)
    img.putpalette([0, 0, 0, 90, 90, 90, 170, 170, 170, 255, 255, 255] + [0] * (256 * 3 - 12))
    d = ImageDraw.Draw(img)

    def ox(i):
        return i * sz

    # 0 sun: disc + rays
    cx, cy = ox(0) + 6, 6
    d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=BLACK)
    for ang in range(0, 360, 45):
        x2 = int(cx + 5 * math.cos(math.radians(ang)))
        y2 = int(cy + 5 * math.sin(math.radians(ang)))
        d.line([cx, cy, x2, y2], fill=BLACK)

    # 1 cloud: two stacked blobs
    d.ellipse([ox(1) + 1, 5, ox(1) + 7, 10], fill=GRAY, outline=BLACK)
    d.ellipse([ox(1) + 4, 3, ox(1) + 11, 9], fill=GRAY, outline=BLACK)
    d.rectangle([ox(1) + 1, 8, ox(1) + 10, 10], fill=GRAY)

    # 2 rain: cloud + drops
    d.ellipse([ox(2) + 1, 2, ox(2) + 10, 7], fill=GRAY, outline=BLACK)
    for dx in (2, 5, 8):
        d.line([ox(2) + dx, 8, ox(2) + dx - 1, 11], fill=BLACK)

    # 3 storm: cloud + bolt
    d.ellipse([ox(3) + 1, 1, ox(3) + 10, 6], fill=GRAY, outline=BLACK)
    d.line([ox(3) + 6, 6, ox(3) + 4, 9], fill=BLACK)
    d.line([ox(3) + 4, 9, ox(3) + 7, 9], fill=BLACK)
    d.line([ox(3) + 7, 9, ox(3) + 5, 11], fill=BLACK)

    # 4 heat: sun low + heat waves
    d.ellipse([ox(4) + 3, 1, ox(4) + 9, 7], fill=BLACK)
    for wy in (9, 11):
        d.line([ox(4) + 1, wy, ox(4) + 10, wy], fill=GRAY)

    # 5 moon: crescent
    d.ellipse([ox(5) + 2, 1, ox(5) + 10, 10], fill=GRAY, outline=BLACK)
    d.ellipse([ox(5) + 4, 0, ox(5) + 12, 9], fill=WHITE)

    # 6 wifi-live: three arcs + dot
    cx = ox(6) + 6
    d.arc([cx - 5, 2, cx + 5, 14], 200, 340, fill=BLACK)
    d.arc([cx - 3, 4, cx + 3, 12], 200, 340, fill=BLACK)
    d.rectangle([cx - 1, 9, cx + 1, 11], fill=BLACK)

    # 7 wifi-stale: same arcs, faint, with a slash
    d.arc([cx + sz - 5, 2, cx + sz + 5, 14], 200, 340, fill=GRAY)
    d.arc([cx + sz - 3, 4, cx + sz + 3, 12], 200, 340, fill=GRAY)
    d.rectangle([cx + sz - 1, 9, cx + sz + 1, 11], fill=GRAY)
    d.line([ox(7) + 1, 11, ox(7) + 11, 1], fill=BLACK)

    # 8 mail-unread: envelope (body + flap)
    d.rectangle([ox(8) + 1, 3, ox(8) + 10, 9], outline=BLACK, fill=GRAY)
    d.line([ox(8) + 1, 3, ox(8) + 6, 7], fill=BLACK)
    d.line([ox(8) + 10, 3, ox(8) + 6, 7], fill=BLACK)

    # 9 mail-fresh: same envelope + a filled dot (new arrival)
    d.rectangle([ox(9) + 1, 4, ox(9) + 9, 10], outline=BLACK, fill=GRAY)
    d.line([ox(9) + 1, 4, ox(9) + 5, 7], fill=BLACK)
    d.line([ox(9) + 9, 4, ox(9) + 5, 7], fill=BLACK)
    d.ellipse([ox(9) + 8, 0, ox(9) + 12, 4], fill=BLACK)

    img.save("assets/statusicons.bmp")
    print(f"wrote assets/statusicons.bmp ({img.width}x{img.height}, {n} frames)")


def main():
    sheet = Image.new("P", (FRAME * len(POSES), FRAME), WHITE)
    # 4-level grayscale palette (indices map to E-Ink grays)
    sheet.putpalette([0, 0, 0, 90, 90, 90, 170, 170, 170, 255, 255, 255] + [0] * (256 * 3 - 12))
    d = ImageDraw.Draw(sheet)
    for i, pose in enumerate(POSES):
        draw_pose(d, i * FRAME, pose)
    sheet.save("assets/slime.bmp")
    print(f"wrote assets/slime.bmp ({sheet.width}x{sheet.height}, {len(POSES)} frames)")

    accents = Image.new("P", (28 * 5, 28), WHITE)
    accents.putpalette([0, 0, 0, 90, 90, 90, 170, 170, 170, 255, 255, 255] + [0] * (256 * 3 - 12))
    ad = ImageDraw.Draw(accents)
    # 0 spring bud, 1 summer sun, 2 autumn leaf, 3 winter snowflake
    ad.ellipse([4, 6, 16, 18], fill=GRAY, outline=BLACK)
    ad.rectangle([9, 16, 11, 24], fill=BLACK)
    ad.ellipse([28 + 6, 6, 28 + 18, 18], fill=GRAY, outline=BLACK)
    for ang in range(0, 360, 45):
        cx, cy = 28 + 12, 12
        ad.line(
            [
                cx,
                cy,
                int(cx + 11 * math.cos(math.radians(ang))),
                int(cy + 11 * math.sin(math.radians(ang))),
            ],
            fill=BLACK,
        )
    ad.polygon([(56 + 12, 4), (56 + 5, 18), (56 + 19, 18)], fill=GRAY, outline=BLACK)
    cx, cy = 84 + 12, 12
    for ang in range(0, 180, 45):
        dx, dy = int(11 * math.cos(math.radians(ang))), int(11 * math.sin(math.radians(ang)))
        ad.line([cx - dx, cy - dy, cx + dx, cy + dy], fill=BLACK)
    # frame 4: moon (a crescent: a disc with an offset white disc cut out)
    ad.ellipse([112 + 6, 4, 112 + 22, 20], fill=GRAY, outline=BLACK)
    ad.ellipse([112 + 11, 2, 112 + 27, 18], fill=WHITE)
    accents.save("assets/accents.bmp")
    print(f"wrote assets/accents.bmp ({accents.width}x{accents.height}, 5 frames)")

    _status_icons()


if __name__ == "__main__":
    main()
