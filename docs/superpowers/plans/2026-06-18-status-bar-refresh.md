# Status Bar + Adaptive Refresh Cadence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a top status bar (time · date · weather · battery · WiFi) and a power-aware refresh cadence (5 min USB / 15 min battery / disabled in darkness) to the MagTag Slime Pet.

**Architecture:** All formatting and the cadence/sleep decisions live in pure, host-tested modules (`slime/statusbar.py`, extensions to `slime/timekeeping.py`). The device-only display adapter (`slime/display.py`) renders the bar from those strings/indices, and `code.py` drives the cadence. A new generated tile sheet (`assets/statusicons.bmp`) supplies the weather + WiFi glyphs the ASCII-only `terminalio.FONT` cannot.

**Tech Stack:** CircuitPython 10.2.1 (device), Python 3 + pytest (host tests), Pillow (asset generation), `black`/`ruff` line-length 100.

**Spec:** `docs/superpowers/specs/2026-06-18-status-bar-refresh-design.md`

**Conventions to respect:**
- Pure modules MUST NOT import hardware (`board`, `displayio`, `microcontroller`, `alarm`, `analogio`, `adafruit_*`). Host tests import them directly.
- Run host tests with the repo's pytest config (`-p no:debugging` is already set in `pyproject.toml`).
- CircuitPython namedtuples have no `_replace`; not relevant here (no new namedtuples), but do not add one.
- Commit after each task with a `feat:`/`test:`/`chore:` conventional message.

---

## File Structure

| File | Responsibility | Tested |
|------|----------------|--------|
| `slime/timekeeping.py` (modify) | Add `hms_from_epoch` + `MONTH_ABBR` (pure time math) | host (`tests/test_timekeeping.py`) |
| `slime/statusbar.py` (create) | Pure: format bar fields, decide cadence + sleep mode | host (`tests/test_statusbar.py`) |
| `assets/make_assets.py` (modify) | Also emit `assets/statusicons.bmp` (weather + WiFi tiles) | run-and-verify |
| `slime/display.py` (modify) | Render the bar + `render_sleep`; reposition sprite | on-device visual |
| `code.py` (modify) | Periodic refresh, sleep-mode freeze, battery cadence, WiFi state | on-device visual |

---

## Task 1: Time-of-day + month names in `timekeeping`

**Files:**
- Modify: `slime/timekeeping.py`
- Test: `tests/test_timekeeping.py` (create if absent; otherwise append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_timekeeping.py` (create the file with this content if it does not exist):

```python
from slime import timekeeping


def test_hms_from_epoch_at_unix_zero():
    assert timekeeping.hms_from_epoch(0, 0.0) == (0, 0, 0)


def test_hms_from_epoch_counts_into_day():
    # 1:01:01 after midnight UTC
    assert timekeeping.hms_from_epoch(3661, 0.0) == (1, 1, 1)
    # 12:30:00 after midnight UTC
    assert timekeeping.hms_from_epoch(45000, 0.0) == (12, 30, 0)


def test_hms_from_epoch_applies_tz_offset():
    # 45000s UTC, shifted -7h -> 19800s -> 05:30:00 local
    assert timekeeping.hms_from_epoch(45000, -7.0) == (5, 30, 0)


def test_month_abbr_has_twelve_entries():
    assert len(timekeeping.MONTH_ABBR) == 12
    assert timekeeping.MONTH_ABBR[0] == "Jan"
    assert timekeeping.MONTH_ABBR[5] == "Jun"
    assert timekeeping.MONTH_ABBR[11] == "Dec"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_timekeeping.py -v`
Expected: FAIL with `AttributeError: module 'slime.timekeeping' has no attribute 'hms_from_epoch'` (and `MONTH_ABBR`).

- [ ] **Step 3: Implement**

In `slime/timekeeping.py`, add the month table near the top (after `_SECONDS_PER_DAY`):

```python
MONTH_ABBR: tuple[str, ...] = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
```

And add this function (anywhere after `_local_seconds`):

```python
def hms_from_epoch(epoch: int, tz_offset_hours: float) -> tuple[int, int, int]:
    """Return (hours, minutes, seconds) of the local time-of-day."""
    secs_into_day = _local_seconds(epoch, tz_offset_hours) % _SECONDS_PER_DAY
    return (secs_into_day // 3600, (secs_into_day % 3600) // 60, secs_into_day % 60)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_timekeeping.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint + commit**

```bash
black slime/timekeeping.py tests/test_timekeeping.py
ruff check slime/timekeeping.py tests/test_timekeeping.py
git add slime/timekeeping.py tests/test_timekeeping.py
git commit -m "feat: add hms_from_epoch and MONTH_ABBR to timekeeping"
```

---

## Task 2: `statusbar` text formatters

**Files:**
- Create: `slime/statusbar.py`
- Test: `tests/test_statusbar.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_statusbar.py`:

```python
from collections import namedtuple

from slime import statusbar

# Minimal oracle stand-in matching slime.oracle.Oracle's used fields.
Ora = namedtuple("Ora", ("weather_tag", "temp_c", "moon_phase"))


def test_clock_12h_midnight_and_noon():
    assert statusbar.clock_12h(0, 0.0) == "12:00 AM"      # 00:00
    assert statusbar.clock_12h(45000, 0.0) == "12:30 PM"  # 12:30


def test_clock_12h_morning_and_evening():
    assert statusbar.clock_12h(3660, 0.0) == "1:01 AM"     # 01:01
    assert statusbar.clock_12h(45000 + 3600, 0.0) == "1:30 PM"  # 13:30


def test_short_date_formats_month_abbrev_and_day():
    # 2026-06-18 is 20622 days after epoch; use an epoch inside that local day.
    # 1781827200 = 2026-06-18 12:00:00 UTC
    assert statusbar.short_date(1781827200, 0.0) == "Jun 18"


def test_temp_str_converts_celsius_to_whole_fahrenheit():
    assert statusbar.temp_str(Ora("clear", 0.0, 1)) == "32°"
    assert statusbar.temp_str(Ora("extreme_heat", 38.9, 1)) == "102°"
    assert statusbar.temp_str(Ora("cold", -10.0, 1)) == "14°"


def test_temp_str_blank_when_missing():
    assert statusbar.temp_str(None) == ""
    assert statusbar.temp_str(Ora("clear", None, 1)) == ""


def test_battery_str_rounds_and_clamps():
    assert statusbar.battery_str(0.84) == "84%"
    assert statusbar.battery_str(1.0) == "100%"
    assert statusbar.battery_str(0.0) == "0%"
    assert statusbar.battery_str(1.5) == "100%"
    assert statusbar.battery_str(-0.2) == "0%"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_statusbar.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'slime.statusbar'`.

- [ ] **Step 3: Implement**

Create `slime/statusbar.py`:

```python
"""Pure status-bar formatting + refresh/sleep decisions. No hardware imports."""

from slime import timekeeping


def clock_12h(epoch: int, tz_offset_hours: float) -> str:
    """Local time as a 12-hour string, e.g. '3:45 PM'."""
    hh, mm, _ = timekeeping.hms_from_epoch(epoch, tz_offset_hours)
    suffix = "AM" if hh < 12 else "PM"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d} {suffix}"


def short_date(epoch: int, tz_offset_hours: float) -> str:
    """Local date as 'Mon D', e.g. 'Jun 18'."""
    _, month, day = timekeeping.civil_from_epoch(epoch, tz_offset_hours)
    return f"{timekeeping.MONTH_ABBR[month - 1]} {day}"


def temp_str(oracle) -> str:
    """Whole-degree Fahrenheit from the oracle's Celsius temp, '' if unknown."""
    if oracle is None or oracle.temp_c is None:
        return ""
    return f"{round(oracle.temp_c * 9 / 5 + 32)}°"


def battery_str(frac: float) -> str:
    """Battery percentage from a 0..1 fraction, clamped, e.g. '84%'."""
    pct = round(max(0.0, min(1.0, frac)) * 100)
    return f"{pct}%"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_statusbar.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint + commit**

```bash
black slime/statusbar.py tests/test_statusbar.py
ruff check slime/statusbar.py tests/test_statusbar.py
git add slime/statusbar.py tests/test_statusbar.py
git commit -m "feat: add statusbar text formatters (time/date/temp/battery)"
```

---

## Task 3: `statusbar` icon mapping, WiFi constants, cadence + sleep decisions

**Files:**
- Modify: `slime/statusbar.py`
- Test: `tests/test_statusbar.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_statusbar.py`:

```python
def test_weather_icon_maps_known_tags():
    assert statusbar.weather_icon(Ora("clear", 30.0, 1)) == statusbar.ICON_CLEAR
    assert statusbar.weather_icon(Ora("cold", 5.0, 1)) == statusbar.ICON_CLOUD
    assert statusbar.weather_icon(Ora("rain", 18.0, 1)) == statusbar.ICON_RAIN
    assert statusbar.weather_icon(Ora("storm_incoming", 25.0, 1)) == statusbar.ICON_STORM
    assert statusbar.weather_icon(Ora("monsoon", 25.0, 1)) == statusbar.ICON_STORM
    assert statusbar.weather_icon(Ora("extreme_heat", 44.0, 1)) == statusbar.ICON_HEAT


def test_weather_icon_shows_moon_on_clear_notable_phase():
    # Clear sky + new (0) or full (4) moon -> moon glyph instead of sun.
    assert statusbar.weather_icon(Ora("clear", 20.0, 4)) == statusbar.ICON_MOON
    assert statusbar.weather_icon(Ora("clear", 20.0, 0)) == statusbar.ICON_MOON


def test_weather_icon_none_when_no_oracle():
    assert statusbar.weather_icon(None) is None


def test_wifi_constants_distinct():
    assert statusbar.WIFI_LIVE != statusbar.WIFI_STALE


def test_refresh_interval_by_state():
    assert statusbar.refresh_interval(on_usb=True, sleeping=False) == 300.0
    assert statusbar.refresh_interval(on_usb=False, sleeping=False) == 900.0
    assert statusbar.refresh_interval(on_usb=True, sleeping=True) is None
    assert statusbar.refresh_interval(on_usb=False, sleeping=True) is None


def test_is_sleep_mode_hysteresis_entering():
    # Not currently sleeping: only very dark (< 0.08) enters sleep.
    assert statusbar.is_sleep_mode(0.05, currently_sleeping=False) is True
    assert statusbar.is_sleep_mode(0.10, currently_sleeping=False) is False
    assert statusbar.is_sleep_mode(0.20, currently_sleeping=False) is False


def test_is_sleep_mode_hysteresis_holding_and_waking():
    # Already sleeping: stays asleep through the dead band, wakes only above 0.15.
    assert statusbar.is_sleep_mode(0.10, currently_sleeping=True) is True
    assert statusbar.is_sleep_mode(0.14, currently_sleeping=True) is True
    assert statusbar.is_sleep_mode(0.20, currently_sleeping=True) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_statusbar.py -v`
Expected: FAIL with `AttributeError: module 'slime.statusbar' has no attribute 'ICON_CLEAR'` (and the rest).

- [ ] **Step 3: Implement**

Append to `slime/statusbar.py`:

```python
# --- Tile indices into assets/statusicons.bmp (12x12 tiles, left to right) ---
ICON_CLEAR = 0   # sun
ICON_CLOUD = 1   # cloud (cold / overcast)
ICON_RAIN = 2
ICON_STORM = 3
ICON_HEAT = 4
ICON_MOON = 5
WIFI_LIVE = 6    # connected
WIFI_STALE = 7   # disconnected / cached

_WEATHER_ICON = {
    "clear": ICON_CLEAR,
    "cold": ICON_CLOUD,
    "rain": ICON_RAIN,
    "storm_incoming": ICON_STORM,
    "monsoon": ICON_STORM,
    "extreme_heat": ICON_HEAT,
}

_SLEEP_ENTER = 0.08   # below this (while awake) -> enter sleep
_SLEEP_EXIT = 0.15    # at/above this (while asleep) -> wake
_USB_REFRESH = 300.0
_BATTERY_REFRESH = 900.0


def weather_icon(oracle):
    """Tile index for the oracle's weather (or notable moon on a clear sky); None if no oracle."""
    if oracle is None:
        return None
    if oracle.weather_tag == "clear" and oracle.moon_phase in (0, 4):
        return ICON_MOON
    return _WEATHER_ICON.get(oracle.weather_tag, ICON_CLEAR)


def refresh_interval(on_usb: bool, sleeping: bool):
    """Seconds between scheduled repaints; None disables refresh (sleep mode)."""
    if sleeping:
        return None
    return _USB_REFRESH if on_usb else _BATTERY_REFRESH


def is_sleep_mode(light: float, currently_sleeping: bool) -> bool:
    """Whether the pet should be in dark 'sleep mode', with hysteresis to avoid flicker."""
    if currently_sleeping:
        return light < _SLEEP_EXIT
    return light < _SLEEP_ENTER
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_statusbar.py -v`
Expected: PASS (all 13 tests in the file).

- [ ] **Step 5: Full host suite + lint + commit**

```bash
pytest -q
black slime/statusbar.py tests/test_statusbar.py
ruff check slime/statusbar.py tests/test_statusbar.py
git add slime/statusbar.py tests/test_statusbar.py
git commit -m "feat: add statusbar weather icons, wifi state, cadence and sleep decisions"
```
Expected: full suite PASS (existing tests unaffected).

---

## Task 4: Generate `assets/statusicons.bmp`

**Files:**
- Modify: `assets/make_assets.py`
- Asset (generated): `assets/statusicons.bmp`

This is a generator script, not unit-tested; verify by running it and checking the output dimensions. Tiles are 12×12 so they fit inside the 16 px bar. Order MUST match the indices in Task 3: `0 sun, 1 cloud, 2 rain, 3 storm, 4 heat, 5 moon, 6 wifi-live, 7 wifi-stale` → 8 tiles → 96×12 px.

- [ ] **Step 1: Add the generator function**

In `assets/make_assets.py`, add this function above `def main():`:

```python
def _status_icons():
    """8 grayscale 12x12 tiles: sun, cloud, rain, storm, heat, moon, wifi-live, wifi-stale."""
    n, sz = 8, 12
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

    img.save("assets/statusicons.bmp")
    print(f"wrote assets/statusicons.bmp ({img.width}x{img.height}, {n} frames)")
```

- [ ] **Step 2: Call it from `main()`**

In `assets/make_assets.py`, inside `def main():`, add before the final implicit end (after the `accents.save(...)`/print lines):

```python
    _status_icons()
```

- [ ] **Step 3: Generate and verify**

Run:
```bash
python3 assets/make_assets.py
python3 -c "from PIL import Image; im=Image.open('assets/statusicons.bmp'); print(im.size, im.mode)"
```
Expected: prints `wrote assets/statusicons.bmp (96x12, 8 frames)` then `(96, 12) P`.

- [ ] **Step 4: Commit**

```bash
git add assets/make_assets.py assets/statusicons.bmp
git commit -m "feat: generate statusicons.bmp (weather + wifi glyphs)"
```

---

## Task 5: Render the status bar in `display.py`

**Files:**
- Modify: `slime/display.py`

Device-only adapter (imports `board`/`displayio`), so it is not host-tested — verified on-device in Task 6's visual check. Keep the existing `render`, `render_journal`, `render_dream` working. Replace the old top-right seasonal-accent mechanism with bar-based weather/WiFi/battery glyphs; `render_frame`'s signature changes (its only caller, `code.py:_render_frame`, is updated in Task 6).

- [ ] **Step 1: Add bar elements in `__init__`**

In `slime/display.py`, after the quip label is appended (around line 52) and BEFORE the seasonal-accent block, add the status-bar elements. Then DELETE the old seasonal-accent block (the `self._accent_bmp` / `self._accent` / `self._accent_hidden` lines, current lines ~54-66) since weather now lives in the bar.

Add:

```python
        # --- Status bar (top 16px strip) ---
        _BAR_H = 16
        self._bar_h = _BAR_H

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
            self._icons_bmp, pixel_shader=self._icons_bmp.pixel_shader,
            width=1, height=1, tile_width=12, tile_height=12,
        )
        self._wifi.x = w - 14
        self._wifi.y = 2
        self._wifi_hidden = True

        self._bar_batt = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._bar_batt.anchor_point = (1.0, 0.0)
        self._bar_batt.anchored_position = (w - 18, 3)
        self._root.append(self._bar_batt)

        self._weather = displayio.TileGrid(
            self._icons_bmp, pixel_shader=self._icons_bmp.pixel_shader,
            width=1, height=1, tile_width=12, tile_height=12,
        )
        self._weather.x = w - 70
        self._weather.y = 2
        self._weather_hidden = True

        self._bar_temp = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._bar_temp.anchor_point = (1.0, 0.0)
        self._bar_temp.anchored_position = (w - 72, 3)
        self._root.append(self._bar_temp)

        # Hairline divider beneath the bar.
        div = displayio.Bitmap(w, 1, 1)
        div_pal = displayio.Palette(1)
        div_pal[0] = 0x000000
        div_tg = displayio.TileGrid(div, pixel_shader=div_pal, x=0, y=_BAR_H + 1)
        self._root.append(div_tg)
```

Then move the sprite down so it sits below the bar. Change the sprite position lines (current `self._group.x = 8` / `self._group.y = 0`) to:

```python
        self._group.x = 8
        self._group.y = self._bar_h  # tuck the creature under the status bar
```

- [ ] **Step 2: Add a tile show/hide helper**

Add this private method to the `Display` class (e.g. after `__init__`):

```python
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
```

- [ ] **Step 3: Replace `render_frame` with the bar-aware version**

Replace the entire existing `render_frame` method with:

```python
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
    ):
        """Set the sprite frame + quip + status bar fields and refresh.

        Any status field left None renders blank/hidden (offline-first).
        """
        self._tile[0] = frame_index
        self._quip.text = quip_text or ""

        left = time_str if time_str else "--:--"
        if date_str:
            left = left + "   " + date_str
        self._bar_left.text = left
        self._bar_temp.text = temp_str or ""
        self._bar_batt.text = battery_str or ""
        self._set_tile(self._weather, "_weather_hidden", weather_icon)
        self._set_tile(self._wifi, "_wifi_hidden", wifi_state)

        self._display.root_group = self._root
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()
```

- [ ] **Step 4: Add `render_sleep`**

Add this method to the `Display` class (after `render_frame`):

```python
    def render_sleep(
        self,
        frame_index,
        *,
        time_str=None,
        date_str=None,
        weather_icon=None,
        wifi_state=None,
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
        )
```

- [ ] **Step 5: Update `render` (expression passthrough)**

The existing `render(self, expression, quip_text="")` calls `self.render_frame(expression_to_pose(expression), quip_text)` — that still works (status fields default to None). Leave it unchanged. Verify the file has no remaining references to `self._accent` (the deleted accent block):

Run: `grep -n "_accent" slime/display.py`
Expected: no output.

- [ ] **Step 6: Syntax check + commit**

Run: `python3 -c "import ast; ast.parse(open('slime/display.py').read()); print('ok')"`
Expected: `ok` (host can't import the hardware libs, so an AST parse is the offline gate).

```bash
black slime/display.py
ruff check slime/display.py
git add slime/display.py
git commit -m "feat: render status bar (time/date/temp/battery/weather/wifi) and sleep frame"
```

---

## Task 6: Drive the cadence in `code.py`

**Files:**
- Modify: `code.py`

Device-only entry point. Wire: (a) status fields into every render, (b) USB periodic refresh + sleep-mode freeze, (c) battery 15-min cadence with the dark 1-hour light-check, (d) WiFi live/stale state. Verified on-device.

- [ ] **Step 1: Imports + constants**

In `code.py`, add `statusbar` to the `from slime import (...)` block (keep alphabetical: it goes after `seasons`). Then update the timing constants near the top:

```python
_MIN_REFRESH = 180.0
_SCHEDULED = 21600.0
_NAP_SECONDS = 900.0          # battery awake: 15-minute refresh nap
_DARK_NAP_SECONDS = 3600.0    # battery dark: hourly light-check nap
_NTP_RESYNC = 3600.0          # re-sync NTP at most hourly to correct drift
_TICK = 0.05
_SLEEPY_FRAME = 85.0
_MOOD_BYTE = {"content": 0, "sleepy": 1, "happy": 2, "curious": 3, "contemplative": 4}
```

- [ ] **Step 2: Add a status-fields helper**

Add this helper near `_render_frame` in `code.py`:

```python
def _status_fields(synced_epoch, mono_at_sync, tz, oracle, battery, wifi_state):
    """Build the keyword status-bar fields for display.render_frame (offline-first)."""
    if synced_epoch is None:
        time_str = date_str = None
    else:
        epoch = timekeeping.now_epoch(synced_epoch, mono_at_sync, time.monotonic())
        time_str = statusbar.clock_12h(epoch, tz)
        date_str = statusbar.short_date(epoch, tz)
    return {
        "time_str": time_str,
        "date_str": date_str,
        "temp_str": statusbar.temp_str(oracle),
        "battery_str": statusbar.battery_str(battery),
        "weather_icon": statusbar.weather_icon(oracle),
        "wifi_state": wifi_state,
    }
```

- [ ] **Step 3: Thread status fields through `_render_frame`**

Replace the `_render_frame` function with a version that accepts and forwards the status fields (it keeps choosing the pose/quip exactly as before, just passes the bar fields and drops the old accent logic):

```python
def _render_frame(display, state, season=None, weather=None, oracle=None, fields=None):
    """Render the current form + a quip + the status bar. Returns updated state."""
    if not display:
        return state
    sleeping = state.mood.sleepiness >= _SLEEPY_FRAME
    ftier = friendship.tier(state.familiarity)
    frame = choose_render(state.mood, ftier, sleeping, season=season, weather=weather)
    otag = oracle_mod.quip_tag(oracle) if oracle is not None else None
    tag = otag or ("bonded" if ftier >= 3 else state.expression)
    quip = pick(tag) or pick(state.expression)
    try:
        display.render_frame(frame, quip or "", **(fields or {}))
        state = evolve(state, last_seen=time.monotonic())
    except Exception:
        pass
    return state
```

Note: `ACCENT_MOON` import and the accent branch are no longer used here. Remove `ACCENT_MOON` from the `from slime.visuals import ...` line (leaving `CONTINUOUS, choose_run_mode, should_refresh`).

- [ ] **Step 4: Update the boot render call + battery path**

In `main()`, find the first render (`state = _render_frame(display, state, season, weather_form, oracle)` near line 231). Replace the surrounding boot logic so a WiFi state and battery reading are known, then pass fields. Replace from the oracle-load line through the end of `main()`'s boot section and both loop branches.

First, after `oracle = _load_oracle(on_usb_boot)` and the `mood_bias` line, compute WiFi state:

```python
    # WiFi "live" if either the clock or the oracle came through this cycle.
    wifi_state = statusbar.WIFI_LIVE if (synced_epoch is not None or oracle is not None) else statusbar.WIFI_STALE
```

Then change the boot render (the `state = _render_frame(...)` after `_maybe_journal`) to:

```python
    batt0 = inputs.battery
    fields = _status_fields(synced_epoch, mono_at_sync, tz, oracle, batt0, wifi_state)
    state = _render_frame(display, state, season, weather_form, oracle, fields)
    persistence.save(state)
```

- [ ] **Step 5: USB continuous loop — periodic refresh + sleep freeze**

Replace the `if choose_run_mode(...) == CONTINUOUS:` block's body with the version below. It adds a `sleeping` state, a scheduled-refresh timer, hourly NTP resync, and oracle re-fetch:

```python
    if choose_run_mode(inputs.on_usb, inputs.battery) == CONTINUOUS:
        t0 = time.monotonic()
        sleeping = statusbar.is_sleep_mode(inputs.light, False)
        last_scheduled = time.monotonic()
        last_ntp = time.monotonic() if synced_epoch is not None else 0.0
        if sleeping and display:
            display.render_sleep(choose_render(state.mood, friendship.tier(state.familiarity),
                                 True, season=season, weather=weather_form), **{
                "time_str": fields["time_str"], "date_str": fields["date_str"],
                "weather_icon": fields["weather_icon"], "wifi_state": fields["wifi_state"]})
        while True:
            now = time.monotonic()
            inputs, events, detector, last_event_time, gap = _gather(
                sensors, detector, last_event_time, now
            )
            was_sleeping = sleeping
            sleeping = statusbar.is_sleep_mode(inputs.light, sleeping)

            if events and not sleeping:
                prev = state.expression
                state = step(state, inputs, 1.0)
                if "double_tap" in events:
                    state = evolve(state, total_boops=state.total_boops + 1)
                fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
                state = evolve(state, familiarity=fam, visit_count=visits)
                if season:
                    state = evolve(state, mood=seasons.apply_bias(state.mood, season))
                if oracle is not None:
                    state = evolve(state, mood=oracle_mod.mood_bias(state.mood, oracle))
                ftier = friendship.tier(state.familiarity)
                if sound and state.behavior == "greeting":
                    sound.play(pick_motif("greeting", ftier))
                if state.behavior == "dizzy" and pixels:
                    pixels.flash((120, 0, 0))
                    time.sleep(0.4)
                if should_refresh(
                    time.monotonic(), state.last_seen,
                    pose_changed=(state.expression != prev),
                    significant_event=("double_tap" in events),
                    min_interval=_MIN_REFRESH, scheduled_interval=_SCHEDULED,
                ):
                    batt = inputs.battery
                    fields = _status_fields(synced_epoch, mono_at_sync, tz, oracle, batt, wifi_state)
                    state = _render_frame(display, state, season, weather_form, oracle, fields)
                persistence.save(state)

            # Light returned -> wake and repaint immediately.
            if was_sleeping and not sleeping:
                batt = inputs.battery
                fields = _status_fields(synced_epoch, mono_at_sync, tz, oracle, batt, wifi_state)
                state = _render_frame(display, state, season, weather_form, oracle, fields)
                last_scheduled = time.monotonic()
            # Just entered sleep -> freeze on the sleeping frame once.
            elif sleeping and not was_sleeping and display:
                display.render_sleep(choose_render(state.mood, friendship.tier(state.familiarity),
                                     True, season=season, weather=weather_form), **{
                    "time_str": fields["time_str"], "date_str": fields["date_str"],
                    "weather_icon": fields["weather_icon"], "wifi_state": fields["wifi_state"]})

            # Scheduled periodic refresh while awake (live clock + fresh weather).
            if not sleeping and time.monotonic() - last_scheduled >= statusbar.refresh_interval(True, False):
                if time.monotonic() - last_ntp >= _NTP_RESYNC:
                    e2, m2, tz = _sync_time()
                    if e2 is not None:
                        synced_epoch, mono_at_sync = e2, m2
                        last_ntp = time.monotonic()
                oracle = _load_oracle(True)
                weather_form = oracle_mod.form_override(oracle)
                wifi_state = statusbar.WIFI_LIVE if (synced_epoch is not None or oracle is not None) else statusbar.WIFI_STALE
                batt = inputs.battery
                fields = _status_fields(synced_epoch, mono_at_sync, tz, oracle, batt, wifi_state)
                state = _render_frame(display, state, season, weather_form, oracle, fields)
                persistence.save(state)
                last_scheduled = time.monotonic()

            if pixels:
                if sleeping:
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=0.05)
                else:
                    rate = 0.12 + (state.mood.energy / 100.0) * 0.35
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
            time.sleep(_TICK)
```

- [ ] **Step 6: Battery path — 15-min cadence + dark light-check**

Replace the `else:` (wake-cycle) branch at the end of `main()` with:

```python
    else:
        t0 = time.monotonic()
        sleeping = statusbar.is_sleep_mode(inputs.light, False)
        while time.monotonic() - t0 < 4.0:
            if pixels:
                pixels.breathe(state.mood, time.monotonic() - t0, rate=0.05 if sleeping else 0.2)
            time.sleep(_TICK)
        if pixels:
            pixels.off()
        if sleeping:
            # Dark: don't repaint; nap on motion + an hourly light re-check.
            power.nap(_DARK_NAP_SECONDS)
        else:
            if sound:
                sound.play(pick_motif("sleepy"))
            power.nap(_NAP_SECONDS)
```

Note: on battery, NTP + oracle are already fetched at boot only when `on_usb_boot` is True. To get live time/weather on battery wakes, change the boot guard so battery wakes also sync. Find:

```python
    on_usb_boot = sensors.on_usb() if sensors else True
    synced_epoch, mono_at_sync, tz = (None, None, -7.0)
    if on_usb_boot:
        synced_epoch, mono_at_sync, tz = _sync_time()
```

and replace the condition so a non-dark battery wake also syncs:

```python
    on_usb_boot = sensors.on_usb() if sensors else True
    light_boot = sensors.light() if sensors else 0.5
    dark_boot = statusbar.is_sleep_mode(light_boot, False)
    synced_epoch, mono_at_sync, tz = (None, None, -7.0)
    if on_usb_boot or not dark_boot:
        synced_epoch, mono_at_sync, tz = _sync_time()
```

Likewise change the oracle load so a non-dark battery wake fetches fresh weather. Replace `oracle = _load_oracle(on_usb_boot)` with `oracle = _load_oracle(on_usb_boot or not dark_boot)`.

- [ ] **Step 7: Offline syntax check**

Run: `python3 -c "import ast; ast.parse(open('code.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 8: Full host suite (guards + existing pure tests)**

Run: `pytest -q`
Expected: PASS. (The module-scan guard test imports the pure modules; `code.py`/`display.py` stay device-only and are not imported by host tests.)

- [ ] **Step 9: Lint + commit**

```bash
black code.py
ruff check code.py
git add code.py
git commit -m "feat: adaptive refresh cadence + status bar wiring (5m USB / 15m battery / dark sleep)"
```

- [ ] **Step 10: On-device deploy + visual verification**

Deploy: copy `code.py`, `slime/`, and `assets/` to `CIRCUITPY`. Then confirm on the MagTag:
1. Status bar shows `time · date · temp° · battery% · weather glyph · WiFi glyph`, sprite tucked below the divider.
2. WiFi glyph is the "live" icon when the Mac oracle server is reachable; cover/disconnect → stale icon on the next refresh.
3. On USB, the clock advances on a ~5-minute cadence (no need to wait 6h anymore).
4. Cover the light sensor → within the dead band it freezes on the sleeping creature with a dim slow NeoPixel breath; uncover → it wakes and repaints.
5. Offline (server down + no NTP) → `--:--`, blank temp, stale WiFi, creature still alive.

Record results in the PR/commit notes.

---

## Self-Review

**Spec coverage:**
- Split bar layout (time/date left; temp/weather/battery/WiFi right) → Task 5 `__init__` + `render_frame`. ✓
- Formats: 12h time, "Jun 18", °F, battery %, WiFi bars glyph → Tasks 1–4. ✓
- Cadence 300/900/None → `refresh_interval` (Task 3) used in Task 6. ✓
- Sleep hysteresis 0.08/0.15 → `is_sleep_mode` (Task 3), used USB + battery (Task 6). ✓
- Battery dark = motion + hourly light-check → `_DARK_NAP_SECONDS` path (Task 6 Step 6). ✓
- Dim sleep-breath pixels → Task 6 Steps 5 & 6 (`rate=0.05`). ✓
- WiFi live/stale semantics → `wifi_state` set from fetch success (Task 6). ✓
- Battery wakes sync NTP + oracle when not dark → Task 6 Step 6 boot-guard change. ✓
- `render_sleep` freeze frame → Task 5 Step 4, called in Task 6. ✓
- No new NVM fields / no server changes → nothing in plan touches `persistence.py`/`server/`. ✓
- statusicons.bmp generated, 12px tiles → Task 4. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `weather_icon`/`wifi_state`/`time_str`/`date_str`/`temp_str`/`battery_str` names match between `statusbar` (Tasks 2–3), `display.render_frame` (Task 5), and `_status_fields`/callers (Task 6). `refresh_interval(on_usb, sleeping)` and `is_sleep_mode(light, currently_sleeping)` signatures match call sites. Tile indices (`ICON_*`, `WIFI_*`) defined in Task 3 match the 8-tile order generated in Task 4. ✓
