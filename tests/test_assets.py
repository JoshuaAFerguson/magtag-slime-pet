import os
import subprocess
import sys


def test_make_assets_writes_visitors_sheet(tmp_path):
    # Run the generator from the repo root; it writes into assets/.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, "assets/make_assets.py"], cwd=root, check=True)
    path = os.path.join(root, "assets", "visitors.bmp")
    assert os.path.exists(path)
    from PIL import Image

    img = Image.open(path)
    assert img.height == 12
    assert img.width == 12 * 8  # 8 visitor tiles, 12px each
