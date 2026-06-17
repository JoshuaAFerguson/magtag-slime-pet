"""Hardware adapter: play a tone motif on the MagTag piezo. Device-only."""

import time

import board
import digitalio
import pwmio


class Sound:
    def __init__(self):
        self._enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
        self._enable.direction = digitalio.Direction.OUTPUT
        self._enable.value = True

    def play(self, motif):
        """Play a sequence of (freq_hz, duration_ms) tones. No-op on None/empty."""
        if not motif:
            return
        for freq, ms in motif:
            pwm = pwmio.PWMOut(board.SPEAKER, variable_frequency=True)
            pwm.frequency = int(freq)
            pwm.duty_cycle = 2**14  # ~25% duty: gentle, not loud
            time.sleep(ms / 1000.0)
            pwm.deinit()

    def silence(self):
        self._enable.value = False
