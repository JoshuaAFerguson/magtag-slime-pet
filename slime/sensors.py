"""Hardware adapter: battery, USB, light, accelerometer. Device-only (imports board/libs)."""
import board
import analogio
import supervisor
import adafruit_lis3dh
from slime.interactions import AccelReading

_LIGHT_MAX = 65535.0
_BATTERY_MIN_V = 3.3   # ~empty LiPo
_BATTERY_MAX_V = 4.2   # ~full LiPo

# LIS3DH CLICK_SRC register and its single/double click bits.
_CLICK_SRC = 0x39
_SCLICK = 0x10
_DCLICK = 0x20


class Sensors:
    def __init__(self):
        self._light = analogio.AnalogIn(board.LIGHT)
        self._battery = analogio.AnalogIn(board.BATTERY)
        i2c = board.I2C()
        self._accel = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
        self._accel.range = adafruit_lis3dh.RANGE_4_G
        # Enable single + double tap on INT1.
        self._accel.set_tap(2, 60)

    def light(self):
        """Ambient light 0.0 (dark) .. 1.0 (bright)."""
        return self._light.value / _LIGHT_MAX

    def battery(self):
        """Battery charge 0.0 .. 1.0 from the divided cell voltage."""
        volts = (self._battery.value / 65535.0) * 3.3 * 2.0
        frac = (volts - _BATTERY_MIN_V) / (_BATTERY_MAX_V - _BATTERY_MIN_V)
        return min(1.0, max(0.0, frac))

    def on_usb(self):
        """True when powered/communicating over USB."""
        return supervisor.runtime.usb_connected

    def reading(self):
        """Current AccelReading (m/s^2), decoding single vs. double tap from CLICK_SRC.

        With double-tap configured via set_tap(2, ...), the LIS3DH reports clicks in its
        CLICK_SRC register (cleared on read). We decode the single (SCLICK) and double
        (DCLICK) bits so the pure interaction layer can fire TAP vs. DOUBLE_TAP. If the
        register read isn't supported by the installed library, we degrade to treating
        any tap as a single tap rather than crashing.
        """
        x, y, z = self._accel.acceleration
        single = double = False
        try:
            src = self._accel._read_register_byte(_CLICK_SRC)
            double = bool(src & _DCLICK)
            single = bool(src & _SCLICK)
        except Exception:
            single = bool(self._accel.tapped)
        return AccelReading(x=x, y=y, z=z, tapped=single and not double, double_tapped=double)
