"""Hardware adapter: NeoPixel breathing. Device-only. Uses pure slime.visuals for the math."""
import board
import digitalio
import neopixel
from slime.visuals import mood_to_rgb, breath_brightness

_NUM = 4


class Pixels:
    def __init__(self):
        # MagTag gates NeoPixel power through a dedicated pin.
        self._power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
        self._power.direction = digitalio.Direction.OUTPUT
        self._power.value = True
        # Cap brightness to keep peak current modest — protects against brownout on
        # marginal USB supplies and suits the calm, low-glow aesthetic.
        self._np = neopixel.NeoPixel(board.NEOPIXEL, _NUM, auto_write=False, brightness=0.3)

    def breathe(self, mood, t, rate=0.25):
        """Paint one breath frame for the current mood at time t (seconds)."""
        r, g, b = mood_to_rgb(mood)
        level = breath_brightness(t, rate=rate)
        self._np.fill((int(r * level), int(g * level), int(b * level)))
        self._np.show()

    def flash(self, rgb):
        """A brief reaction color (e.g., dizzy)."""
        self._np.fill(rgb)
        self._np.show()

    def off(self):
        self._np.fill((0, 0, 0))
        self._np.show()
        self._power.value = False
