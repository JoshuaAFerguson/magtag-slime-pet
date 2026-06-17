"""Hardware adapter: deep-sleep and wake sources. Device-only."""
import alarm
import time
import board


def woke_from_deep_sleep():
    """True if this run began by waking from deep sleep (vs. a cold boot/reload)."""
    return alarm.wake_alarm is not None


def nap(seconds, motion_pin=board.ACCELEROMETER_INTERRUPT):
    """Enter deep sleep until `seconds` elapse OR the accelerometer signals motion.

    Returns control to a fresh boot on wake (deep sleep restarts code.py); NVM persists.
    """
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + seconds)
    try:
        pin_alarm = alarm.pin.PinAlarm(pin=motion_pin, value=True, pull=True)
        alarm.exit_and_deep_sleep_until_alarms(time_alarm, pin_alarm)
    except (ValueError, AttributeError):
        # If the INT pin isn't wake-capable on this board revision, fall back to time only.
        alarm.exit_and_deep_sleep_until_alarms(time_alarm)
