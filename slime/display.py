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
        self._root = displayio.Group()

        # White "paper" background behind everything — without it the panel clears
        # to black and the (black) quip text is invisible.
        bg_bitmap = displayio.Bitmap(self._display.width, self._display.height, 1)
        bg_palette = displayio.Palette(1)
        bg_palette[0] = 0xFFFFFF
        self._root.append(displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette))

        self._bitmap = displayio.OnDiskBitmap(sheet_path)
        self._tile = displayio.TileGrid(
            self._bitmap,
            pixel_shader=self._bitmap.pixel_shader,
            width=1,
            height=1,
            tile_width=_FRAME,
            tile_height=_FRAME,
        )
        self._group = displayio.Group(scale=_SCALE)
        self._group.append(self._tile)
        # Sprite sits on the left; it fills the panel height (64px * scale 2 = 128px).
        sprite_px = _FRAME * _SCALE
        self._group.x = 8
        self._group.y = 0
        self._root.append(self._group)

        # Quip lives in the empty area to the right of the slime, vertically centered.
        self._quip = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._quip.anchor_point = (0.5, 0.5)
        self._quip.anchored_position = (
            (8 + sprite_px + self._display.width) // 2,
            self._display.height // 2,
        )
        self._root.append(self._quip)

        # Seasonal corner accent (top-right), hidden until a season is known.
        self._accent_bmp = displayio.OnDiskBitmap("/assets/accents.bmp")
        self._accent = displayio.TileGrid(
            self._accent_bmp,
            pixel_shader=self._accent_bmp.pixel_shader,
            width=1,
            height=1,
            tile_width=28,
            tile_height=28,
        )
        self._accent.x = self._display.width - 32
        self._accent.y = 4
        self._accent_hidden = True

    def render(self, expression, quip_text=""):
        """Render by expression name (maps to a frame). Kept for callers using expressions."""
        self.render_frame(expression_to_pose(expression), quip_text)

    def render_frame(self, frame_index, quip_text="", accent_index=None):
        """Set the sprite frame + quip (+ optional seasonal accent) and refresh."""
        self._tile[0] = frame_index
        self._quip.text = quip_text or ""
        if accent_index is None:
            if not self._accent_hidden and self._accent in self._root:
                self._root.remove(self._accent)
                self._accent_hidden = True
        else:
            self._accent[0] = accent_index
            if self._accent_hidden:
                self._root.append(self._accent)
                self._accent_hidden = False
        self._display.root_group = self._root
        # Respect the panel's mandated minimum refresh interval, yielding while we wait.
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()

    def render_journal(self, lines):
        """Full-screen journal: a list of short lines, centered, then a slow refresh."""
        group = displayio.Group()
        bg = displayio.Bitmap(self._display.width, self._display.height, 1)
        palette = displayio.Palette(1)
        palette[0] = 0xFFFFFF
        group.append(displayio.TileGrid(bg, pixel_shader=palette))
        n = len(lines)
        for i, text in enumerate(lines):
            lbl = label.Label(terminalio.FONT, text=text, color=0x000000, scale=1)
            lbl.anchor_point = (0.5, 0.5)
            lbl.anchored_position = (
                self._display.width // 2,
                int(self._display.height // 2 + (i - (n - 1) / 2) * 18),
            )
            group.append(lbl)
        self._display.root_group = group
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()

    def render_dream(self, dream_text, artifact_name=""):
        """Full-screen dream: the dream line, plus any artifact found, then a slow refresh."""
        group = displayio.Group()
        bg = displayio.Bitmap(self._display.width, self._display.height, 1)
        palette = displayio.Palette(1)
        palette[0] = 0xFFFFFF
        group.append(displayio.TileGrid(bg, pixel_shader=palette))

        dream = label.Label(terminalio.FONT, text=dream_text, color=0x000000, scale=1)
        dream.anchor_point = (0.5, 0.5)
        dream.anchored_position = (self._display.width // 2, self._display.height // 2 - 14)
        group.append(dream)

        if artifact_name:
            found = label.Label(
                terminalio.FONT, text="found: " + artifact_name, color=0x000000, scale=1
            )
            found.anchor_point = (0.5, 0.5)
            found.anchored_position = (self._display.width // 2, self._display.height // 2 + 14)
            group.append(found)

        self._display.root_group = group
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()
