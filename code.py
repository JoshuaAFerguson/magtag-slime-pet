"""Slime Pet — Local Soul entry point. Runs on the MagTag under CircuitPython."""

import gc
import time

from slime import (
    dreams,
    friendship,
    journal,
    milestones,
    netdream,
    netmemory,
    netoracle,
    nettime,
    persistence,
    power,
    seasons,
    statusbar,
    timekeeping,
    visitors,
)
from slime import oracle as oracle_mod
from slime.forms import choose_render
from slime.interactions import detect, new_detector
from slime.mood import Inputs, step
from slime.motifs import pick_motif
from slime.quips import pick
from slime.state import evolve
from slime.visuals import CONTINUOUS, choose_run_mode, should_refresh

# Refresh / timing constants.
_MIN_REFRESH = 180.0
_SCHEDULED = 21600.0
_REFRESH = 300.0  # USB awake: one calm 5-min repaint (weather + approximate time-of-day)
_NAP_SECONDS = 900.0  # battery awake: 15-minute refresh nap
_DARK_NAP_SECONDS = 3600.0  # battery dark: hourly light-check nap
_NTP_RESYNC = 3600.0  # re-sync NTP at most hourly to correct drift
_NTP_TRIES = 3  # NTP's first attempt after boot often fails; retry a few times
_TICK = 0.05
_SLEEPY_FRAME = 85.0  # sleepiness at/above which the slime counts as "sleeping" (loaf)
_MOOD_BYTE = {"content": 0, "sleepy": 1, "happy": 2, "curious": 3, "contemplative": 4}


def _new_adapter(factory):
    """Construct a hardware adapter, returning None on failure (never kill the creature)."""
    try:
        return factory()
    except Exception:
        return None


def _gather(sensors, detector, last_event_time, now):
    """Read senses into Inputs; return (inputs, events, detector, last_event_time, gap)."""
    if sensors is None:
        return (
            Inputs(
                light=0.5,
                battery=1.0,
                on_usb=True,
                seconds_since_interaction=now - last_event_time,
                events=(),
            ),
            (),
            detector,
            last_event_time,
            now - last_event_time,
        )
    reading = sensors.reading()
    events, detector = detect(detector, reading)
    gap = now - last_event_time
    if events:
        last_event_time = now
    inputs = Inputs(
        light=sensors.light(),
        battery=sensors.battery(),
        on_usb=sensors.on_usb(),
        seconds_since_interaction=gap,
        events=events,
    )
    return inputs, events, detector, last_event_time, gap


def _sync_time(tries=_NTP_TRIES):
    """Try NTP up to `tries` times. Returns (synced_epoch, mono_at_sync, tz).

    The first NTP attempt right after boot/WiFi-connect frequently fails, so we retry
    a few times before giving up. epoch is None if every attempt fails.
    """
    tz = nettime.tz_offset_hours()
    for _ in range(tries):
        epoch = nettime.sync()
        if epoch is not None:
            return epoch, time.monotonic(), tz
    return None, None, tz


def _current_season(synced_epoch, mono_at_sync, tz):
    """Season string if time is known this power-cycle, else None (offline-first)."""
    if synced_epoch is None:
        return None
    epoch = timekeeping.now_epoch(synced_epoch, mono_at_sync, time.monotonic())
    _, month, _ = timekeeping.civil_from_epoch(epoch, tz)
    return seasons.season_of(month)


def _load_oracle(on_usb):
    """Fetch the oracle on USB (and cache it); otherwise use the cached one. Returns Oracle|None."""
    if on_usb:
        payload = netoracle.fetch()
        parsed = oracle_mod.parse(payload)
        if parsed is not None:
            oracle_mod.save_cache(parsed)
            return parsed
    return oracle_mod.load_cache()


def _status_fields(synced_epoch, mono_at_sync, tz, oracle, battery, wifi_state):
    """Build the keyword status-bar fields for display.render_frame (offline-first)."""
    if synced_epoch is None:
        time_str = date_str = None
    else:
        epoch = timekeeping.now_epoch(synced_epoch, mono_at_sync, time.monotonic())
        time_str = statusbar.part_of_day(epoch, tz)  # approximate, calm — no live clock
        date_str = statusbar.short_date(epoch, tz)
    return {
        "time_str": time_str,
        "date_str": date_str,
        "temp_str": statusbar.temp_str(oracle),
        "battery_str": statusbar.battery_str(battery),
        "weather_icon": statusbar.weather_icon(oracle),
        "mail_icon": statusbar.mail_icon(oracle),
        "wifi_state": wifi_state,
    }


def _render_frame(
    display, state, season=None, weather=None, oracle=None, fields=None, visitor=None
):
    """Render the current form + a quip + the status bar. Returns updated state."""
    if not display:
        return state
    sleeping = state.mood.sleepiness >= _SLEEPY_FRAME
    ftier = friendship.tier(state.familiarity)
    frame = choose_render(state.mood, ftier, sleeping, season=season, weather=weather)
    if visitor is not None:  # a guest takes the voice + a corner glyph this frame
        quip = visitors.quip(visitor)
        vicon = visitors.glyph(visitor)
    else:
        mem = None
        if _choice((False, False, False, False, True)):  # ~1 in 5, voice a remembered milestone
            mem = milestones.memory_quip(state.milestones, _choice)
        otag = oracle_mod.quip_tag(oracle) if oracle is not None else None
        tag = otag or ("bonded" if ftier >= 3 else state.expression)
        quip = mem or pick(tag) or pick(state.expression)
        vicon = None
    try:
        display.render_frame(frame, quip or "", visitor_icon=vicon, **(fields or {}))
        state = evolve(state, last_seen=time.monotonic())
    except Exception:
        pass
    return state


def _render_sleep(display, state, season, weather, fields):
    """Freeze on the sleeping creature with a status bar; guarded like _render_frame."""
    if not display:
        return state
    frame = choose_render(
        state.mood, friendship.tier(state.familiarity), True, season=season, weather=weather
    )
    try:
        display.render_sleep(
            frame,
            time_str=fields["time_str"],
            date_str=fields["date_str"],
            weather_icon=fields["weather_icon"],
            wifi_state=fields["wifi_state"],
        )
        state = evolve(state, last_seen=time.monotonic())
    except Exception:
        pass
    return state


def _choice(seq):
    """Pick a random element (CircuitPython has random.choice)."""
    import random

    return random.choice(seq)


def _roll_visitor(oracle, season, tier):
    """Rarely (~1 in 6) summon an eligible visitor key; None otherwise."""
    if not _choice((False, False, False, False, False, True)):
        return None
    return visitors.pick_visitor(visitors.eligible_visitors(oracle, season, tier), _choice)


def _dream_on_wake(display, sound, state, oracle=None, ring=None, season=None):
    """Generate and show a dream + maybe an artifact. Returns updated state.

    The dream line comes from the home-server LLM when reachable, else the on-device
    template. The artifact roll + NVM bookkeeping always run on-device (unchanged).
    """
    fam_tier = friendship.tier(state.familiarity)
    refs = oracle_mod.dream_refs(oracle) if oracle is not None else ()
    template_line, artifact_id = dreams.generate(
        fam_tier, state.artifacts, _choice, extra_refs=refs
    )
    records = journal.entries(ring) if ring is not None else []
    ctx = dreams.dream_context(fam_tier, state.artifacts, records, season, oracle)
    line = netdream.fetch(ctx) or template_line

    artifact_name = ""
    artifacts = state.artifacts
    if artifact_id is not None and not dreams.has_artifact(artifacts, artifact_id):
        artifacts = dreams.add_artifact(artifacts, artifact_id)
        artifact_name = dreams.artifact_name(artifact_id)
    if sound:
        sound.play(pick_motif("dream"))
    if display:
        try:
            display.render_dream(line, artifact_name)
        except Exception:
            pass
    return evolve(state, artifacts=artifacts, last_seen=time.monotonic())


def _maybe_journal(
    display, state, season, synced_epoch, mono_at_sync, tz, ring, events, oracle, visited_by=None
):
    """On a new wall-clock day, append a journal record and show it. Returns (state, ring)."""
    if not season:  # no trustworthy date this power-cycle -> never fabricate one
        return state, ring
    ordinal = timekeeping.day_ordinal(
        timekeeping.now_epoch(synced_epoch, mono_at_sync, time.monotonic()), tz
    )
    if not timekeeping.is_new_day(state.last_journal_day_ordinal, ordinal):
        return state, ring
    record = journal.pack_record(
        ordinal,
        _MOOD_BYTE.get(state.expression, 0),
        seasons.accent_frame(season),
        (
            (0b1 if "double_tap" in events else 0)
            | (0b10 if oracle_mod.is_busy(oracle) else 0)
            | (0b100 if oracle_mod.is_inbox_heavy(oracle) else 0)
            | (0b1000 if visited_by else 0)
        ),
        friendship.tier(state.familiarity),
    )
    ring = journal.append(ring, record)
    journal.save_ring(ring)
    recs = journal.entries(ring)
    line = journal.generate_entry(recs[-1], len(recs), _choice)
    ctx = dreams.dream_context(
        friendship.tier(state.familiarity), state.artifacts, recs, season, oracle
    )
    ctx["journal"] = line  # local dict, safe to augment; reaches /remember -> episode_from
    netmemory.post(ctx)
    state = evolve(state, last_journal_day_ordinal=ordinal)
    if display:
        try:
            display.render_journal([line])
        except Exception:
            pass
    return state, ring


def main():
    from slime.display import Display
    from slime.pixels import Pixels
    from slime.sensors import Sensors
    from slime.sound import Sound

    now = time.monotonic()
    state = persistence.load(now)
    sensors = _new_adapter(Sensors)
    pixels = _new_adapter(Pixels)
    display = _new_adapter(Display)
    sound = _new_adapter(Sound)
    detector = new_detector()
    last_event_time = time.monotonic()

    # Time + season (offline-first): only spend WiFi/power on USB or in daylight; never fake a date.
    on_usb_boot = sensors.on_usb() if sensors else True
    light_boot = sensors.light() if sensors else 0.5
    dark_boot = statusbar.is_sleep_mode(light_boot, False)
    synced_epoch, mono_at_sync, tz = (None, None, -7.0)
    if on_usb_boot or not dark_boot:
        synced_epoch, mono_at_sync, tz = _sync_time()
    ring = journal.load_ring()
    season = _current_season(synced_epoch, mono_at_sync, tz)
    if season:
        state = evolve(state, mood=seasons.apply_bias(state.mood, season))

    # Oracle (weather + moon): fetch+cache on USB or daylight, else use cache. None -> no effect.
    oracle = _load_oracle(on_usb_boot or not dark_boot)
    if oracle is not None:
        state = evolve(state, mood=oracle_mod.mood_bias(state.mood, oracle))
    weather_form = oracle_mod.form_override(oracle)
    state = evolve(
        state,
        milestones=milestones.evaluate(
            state.milestones, oracle, state, friendship.tier(state.familiarity)
        ),
    )

    visitor = _roll_visitor(oracle, season, friendship.tier(state.familiarity))
    if visitor is not None:
        state = evolve(state, visitors=visitors.collect(state.visitors, visitors.bit(visitor)))

    # WiFi "live" if either the clock or the oracle came through this cycle.
    wifi_state = (
        statusbar.WIFI_LIVE
        if (synced_epoch is not None or oracle is not None)
        else statusbar.WIFI_STALE
    )

    woke_deep = power.woke_from_deep_sleep()
    # If we woke from a long deep-sleep nap, that was a "night" — dream first.
    if woke_deep and dreams.should_dream(True, _NAP_SECONDS):
        state = _dream_on_wake(display, sound, state, oracle, ring=ring, season=season)

    inputs, events, detector, last_event_time, gap = _gather(
        sensors, detector, last_event_time, now
    )
    state = step(state, inputs, 1.0)
    if "double_tap" in events:
        state = evolve(state, total_boops=state.total_boops + 1)
    fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
    state = evolve(state, familiarity=fam, visit_count=visits)

    state, ring = _maybe_journal(
        display,
        state,
        season,
        synced_epoch,
        mono_at_sync,
        tz,
        ring,
        events,
        oracle,
        visited_by=visitor,
    )

    batt0 = inputs.battery
    fields = _status_fields(synced_epoch, mono_at_sync, tz, oracle, batt0, wifi_state)
    state = _render_frame(display, state, season, weather_form, oracle, fields, visitor=visitor)
    persistence.save(state)
    if visitor is not None and not oracle_mod.is_in_meeting(oracle):
        if sound:
            sound.play(pick_motif("greeting", friendship.tier(state.familiarity)))
        if pixels:
            pixels.flash((0, 80, 60))

    if choose_run_mode(inputs.on_usb, inputs.battery) == CONTINUOUS:
        t0 = time.monotonic()
        sleeping = statusbar.is_sleep_mode(inputs.light, False)
        last_refresh = time.monotonic()  # last calm periodic bar repaint
        last_ntp = time.monotonic() if synced_epoch is not None else 0.0
        if sleeping:
            state = _render_sleep(display, state, season, weather_form, fields)
        while True:
            now = time.monotonic()
            inputs, events, detector, last_event_time, gap = _gather(
                sensors, detector, last_event_time, now
            )
            was_sleeping = sleeping
            sleeping = statusbar.is_sleep_mode(inputs.light, sleeping)
            in_meeting = oracle_mod.is_in_meeting(oracle)

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
                if sound and state.behavior == "greeting" and not in_meeting:
                    sound.play(pick_motif("greeting", ftier))
                if state.behavior == "dizzy" and pixels:
                    pixels.flash((120, 0, 0))
                    time.sleep(0.4)
                if should_refresh(
                    time.monotonic(),
                    state.last_seen,
                    pose_changed=(state.expression != prev),
                    significant_event=("double_tap" in events),
                    min_interval=_MIN_REFRESH,
                    scheduled_interval=_SCHEDULED,
                ):
                    batt = inputs.battery
                    fields = _status_fields(
                        synced_epoch, mono_at_sync, tz, oracle, batt, wifi_state
                    )
                    state = _render_frame(display, state, season, weather_form, oracle, fields)
                persistence.save(state)

            if was_sleeping and not sleeping:
                batt = inputs.battery
                fields = _status_fields(synced_epoch, mono_at_sync, tz, oracle, batt, wifi_state)
                state = _render_frame(display, state, season, weather_form, oracle, fields)
                last_refresh = time.monotonic()
            elif sleeping and not was_sleeping:
                state = _render_sleep(display, state, season, weather_form, fields)

            # One calm periodic repaint (no live clock). Re-acquire NTP whenever we have no
            # time yet (its first try often fails) or hourly for drift, re-fetch the oracle,
            # and repaint the bar with the approximate time-of-day + weather. The whole block
            # is guarded so a transient hiccup can never crash the creature; gc.collect() keeps
            # the heap tidy across the periodic repaints.
            if not sleeping and time.monotonic() - last_refresh >= _REFRESH:
                try:
                    gc.collect()
                    if synced_epoch is None or time.monotonic() - last_ntp >= _NTP_RESYNC:
                        e2, m2, tz = _sync_time()
                        if e2 is not None:
                            synced_epoch, mono_at_sync = e2, m2
                            last_ntp = time.monotonic()
                    new_oracle = _load_oracle(True)
                    if new_oracle is not None:  # keep the last good oracle on a failed fetch
                        oracle = new_oracle
                        weather_form = oracle_mod.form_override(oracle)
                    state = evolve(
                        state,
                        milestones=milestones.evaluate(
                            state.milestones, oracle, state, friendship.tier(state.familiarity)
                        ),
                    )
                    # A visit during a same-day refresh collects the keepsake + shows the quip/
                    # glyph/cue, but is not journaled: the journal is a once-per-day entry written
                    # at the new-day boot. The keepsake bitmask is the permanent record of visits.
                    rv = _roll_visitor(oracle, season, friendship.tier(state.familiarity))
                    if rv is not None:
                        state = evolve(
                            state, visitors=visitors.collect(state.visitors, visitors.bit(rv))
                        )
                    wifi_state = (
                        statusbar.WIFI_LIVE
                        if (synced_epoch is not None or oracle is not None)
                        else statusbar.WIFI_STALE
                    )
                    batt = inputs.battery
                    fields = _status_fields(
                        synced_epoch, mono_at_sync, tz, oracle, batt, wifi_state
                    )
                    state = _render_frame(
                        display, state, season, weather_form, oracle, fields, visitor=rv
                    )
                    persistence.save(state)
                    if rv is not None and not in_meeting:
                        if sound:
                            sound.play(pick_motif("greeting", friendship.tier(state.familiarity)))
                        if pixels:
                            pixels.flash((0, 80, 60))
                except Exception as exc:  # never let a periodic refresh crash the creature
                    print("periodic refresh skipped:", exc)
                last_refresh = time.monotonic()

            if pixels:
                if sleeping or in_meeting:
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=0.05)
                else:
                    rate = 0.12 + (state.mood.energy / 100.0) * 0.35
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
            time.sleep(_TICK)
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
            power.nap(_DARK_NAP_SECONDS)
        else:
            if sound:
                sound.play(pick_motif("sleepy"))
            power.nap(_NAP_SECONDS)


# CircuitPython runs code.py as __main__; the guard keeps host imports from running main().
if __name__ == "__main__":
    main()
