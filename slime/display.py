"""Hardware adapter: render the slime pose + optional quip on E-Ink. Device-only."""
import time
import board
import displayio
import terminalio
from adafruit_display_text import label
from slime.visuals import expression_to_pose

_FRAME = 64
_SCALE = 2  # 64px sprite -> 128px tall, fills the panel height


class Display:
    def __init__(self, sheet_path="/assets/slime.bmp"):
        self._display = board.DISPLAY
        self._bitmap = displayio.OnDiskBitmap(sheet_path)
        self._tile = displayio.TileGrid(
            self._bitmap,
            pixel_shader=self._bitmap.pixel_shader,
            width=1, height=1,
            tile_width=_FRAME, tile_height=_FRAME,
        )
        self._group = displayio.Group(scale=_SCALE)
        self._group.append(self._tile)
        # Sprite sits on the left; it fills the panel height (64px * scale 2 = 128px).
        sprite_px = _FRAME * _SCALE
        self._group.x = 8
        self._group.y = 0
        self._root = displayio.Group()
        self._root.append(self._group)
        # Quip lives in the empty area to the right of the slime, vertically centered.
        self._quip = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._quip.anchor_point = (0.5, 0.5)
        self._quip.anchored_position = (
            (8 + sprite_px + self._display.width) // 2,
            self._display.height // 2,
        )
        self._root.append(self._quip)

    def render(self, expression, quip_text=""):
        """Set the pose frame + quip and refresh the panel (blocking, slow)."""
        self._tile[0] = expression_to_pose(expression)
        self._quip.text = quip_text or ""
        self._display.root_group = self._root
        # Respect the panel's mandated minimum refresh interval, yielding while we wait.
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()
