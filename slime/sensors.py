"""Hardware adapter: battery, USB, light, accelerometer. Device-only (imports board/libs)."""
import board
import analogio
import supervisor
import adafruit_lis3dh
from slime.interactions import AccelReading

_LIGHT_MAX = 65535.0
_BATTERY_MIN_V = 3.3   # ~empty LiPo
_BATTERY_MAX_V = 4.2   # ~full LiPo


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
        """Current AccelReading (m/s^2) with tap flags consumed from the sensor."""
        x, y, z = self._accel.acceleration
        tapped = bool(self._accel.tapped)  # True on any tap since last read
        return AccelReading(x=x, y=y, z=z, tapped=tapped, double_tapped=False)
