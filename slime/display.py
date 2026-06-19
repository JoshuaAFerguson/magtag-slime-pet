"""Hardware adapter: render the slime pose + optional quip on E-Ink. Device-only."""

import time

import board
import displayio
import terminalio
from adafruit_display_text import label

from slime.statusbar import wrap_quip
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

        # --- Status bar (top 16px strip) ---
        _BAR_H = 16
        self._bar_h = _BAR_H

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
        self._group.y = self._bar_h  # tuck the creature under the status bar
        self._root.append(self._group)

        # Quip lives in the empty area to the right of the slime, vertically centered.
        self._quip = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._quip.anchor_point = (0.5, 0.5)
        self._quip.anchored_position = (
            (8 + sprite_px + self._display.width) // 2,
            self._display.height // 2,
        )
        self._root.append(self._quip)

        # Left group: a single label holding "time   date".
        self._bar_left = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._bar_left.anchor_point = (0.0, 0.0)
        self._bar_left.anchored_position = (3, 3)
        self._root.append(self._bar_left)

        # Right group: temp label, weather tile, battery label, wifi tile (laid out
        # right-to-left). Tiles come from a shared 12x12 icon sheet.
        self._icons_bmp = displayio.OnDiskBitmap("/assets/statusicons.bmp")
        w = self._display.width

        self._wifi = displayio.TileGrid(
            self._icons_bmp,
            pixel_shader=self._icons_bmp.pixel_shader,
            width=1,
            height=1,
            tile_width=12,
            tile_height=12,
        )
        self._wifi.x = w - 14
        self._wifi.y = 2
        self._wifi_hidden = True

        self._bar_batt = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._bar_batt.anchor_point = (1.0, 0.0)
        self._bar_batt.anchored_position = (w - 18, 3)
        self._root.append(self._bar_batt)

        self._weather = displayio.TileGrid(
            self._icons_bmp,
            pixel_shader=self._icons_bmp.pixel_shader,
            width=1,
            height=1,
            tile_width=12,
            tile_height=12,
        )
        self._weather.x = w - 70
        self._weather.y = 2
        self._weather_hidden = True

        self._bar_temp = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._bar_temp.anchor_point = (1.0, 0.0)
        self._bar_temp.anchored_position = (w - 72, 3)
        self._root.append(self._bar_temp)

        self._mail = displayio.TileGrid(
            self._icons_bmp,
            pixel_shader=self._icons_bmp.pixel_shader,
            width=1,
            height=1,
            tile_width=12,
            tile_height=12,
        )
        self._mail.x = w - 110  # left of the temp text; first-guess, tuned on-device
        self._mail.y = 2
        self._mail_hidden = True

        # Hairline divider beneath the bar.
        div = displayio.Bitmap(w, 1, 1)
        div_pal = displayio.Palette(1)
        div_pal[0] = 0x000000
        div_tg = displayio.TileGrid(div, pixel_shader=div_pal, x=0, y=_BAR_H + 1)
        self._root.append(div_tg)

    def _set_tile(self, tg, hidden_attr, index):
        """Show a bar tile at `index`, or remove it from the scene when index is None."""
        hidden = getattr(self, hidden_attr)
        if index is None:
            if not hidden and tg in self._root:
                self._root.remove(tg)
                setattr(self, hidden_attr, True)
        else:
            tg[0] = index
            if hidden:
                self._root.append(tg)
                setattr(self, hidden_attr, False)

    def render_frame(
        self,
        frame_index,
        quip_text="",
        *,
        time_str=None,
        date_str=None,
        temp_str=None,
        battery_str=None,
        weather_icon=None,
        wifi_state=None,
        mail_icon=None,
    ):
        """Set the sprite frame + quip + status bar fields and refresh.

        Any status field left None renders blank/hidden (offline-first).
        """
        self._tile[0] = frame_index
        self._quip.text = wrap_quip(quip_text or "")

        # Left group: "<part-of-day>  <date>" — show whichever pieces are known.
        left = time_str or ""
        if date_str:
            left = (left + "  " + date_str) if left else date_str
        self._bar_left.text = left
        self._bar_temp.text = temp_str or ""
        self._bar_batt.text = battery_str or ""
        self._set_tile(self._weather, "_weather_hidden", weather_icon)
        self._set_tile(self._wifi, "_wifi_hidden", wifi_state)
        self._set_tile(self._mail, "_mail_hidden", mail_icon)

        self._display.root_group = self._root
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()

    def render_sleep(
        self,
        frame_index,
        *,
        time_str=None,
        date_str=None,
        weather_icon=None,
        wifi_state=None,
        mail_icon=None,
    ):
        """Paint the sleeping creature once with a frozen bar (no quip). Caller then stops
        repainting until light returns."""
        self.render_frame(
            frame_index,
            "",
            time_str=time_str,
            date_str=date_str,
            temp_str=None,
            battery_str=None,
            weather_icon=weather_icon,
            wifi_state=wifi_state,
            mail_icon=mail_icon,
        )

    def render(self, expression, quip_text=""):
        """Render by expression name (maps to a frame). Kept for callers using expressions."""
        self.render_frame(expression_to_pose(expression), quip_text)

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
