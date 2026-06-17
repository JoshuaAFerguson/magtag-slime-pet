"""Generate assets/slime.bmp: a 7-frame 64x64 indexed sprite sheet. Run: python3 assets/make_assets.py"""
from PIL import Image, ImageDraw

FRAME = 64
POSES = ["content", "sleepy", "curious", "happy", "contemplative", "dizzy", "resting"]
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
    else:  # content
        _eyes(d, ox, 34)
        d.rectangle([ox + 28, 47, ox + 40, 50], fill=BLACK)


def main():
    sheet = Image.new("P", (FRAME * len(POSES), FRAME), WHITE)
    # 4-level grayscale palette (indices map to E-Ink grays)
    sheet.putpalette([0, 0, 0, 90, 90, 90, 170, 170, 170, 255, 255, 255] + [0] * (256 * 3 - 12))
    d = ImageDraw.Draw(sheet)
    for i, pose in enumerate(POSES):
        draw_pose(d, i * FRAME, pose)
    sheet.save("assets/slime.bmp")
    print(f"wrote assets/slime.bmp ({sheet.width}x{sheet.height}, {len(POSES)} frames)")


if __name__ == "__main__":
    main()
