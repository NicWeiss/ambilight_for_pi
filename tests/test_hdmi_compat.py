"""Источник «карта захвата» (HDMI) должен продолжать работать: настоящий главный цикл с поддельной картой."""
import os
import sys
import threading
import time
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("spidev", types.SimpleNamespace(SpiDev=object))

import run
from ambilight import AmbilightProcessor
from settings import settings


class FakeCard:
    """Карта захвата: слева красная половина, справа синяя (BGR), кадры идут ~30 в секунду."""

    def __init__(self):
        frame = np.zeros((settings.TARGET_FRAME_HEIGHT, settings.TARGET_FRAME_WIDTH, 3), dtype=np.uint8)
        half = settings.TARGET_FRAME_WIDTH // 2
        frame[:, :half] = (0, 0, 220)        # красный
        frame[:, half:] = (220, 0, 0)        # синий
        self.frame = frame

    def start(self):
        pass

    def snapshot(self):
        return self.frame, time.time(), int(self.frame.max())

    def release(self):
        pass


class FakeLed:
    led_process = None

    def __init__(self, *_):
        self.sent = types.SimpleNamespace(value=0)

    def start(self):
        pass

    def stop(self):
        pass

    def notify(self):
        pass


class HdmiSourceTest(unittest.TestCase):
    def test_hdmi_has_priority_and_reaches_the_strip(self):
        captured = {}
        with mock.patch.object(settings, "HDMI_ENABLED", True), mock.patch.object(settings, "TV_ENABLED", False), \
                mock.patch.object(run, "VideoStream", FakeCard), mock.patch.object(run, "WS2812B_Controller", FakeLed), \
                mock.patch.object(run.signal, "signal"), \
                mock.patch.object(run.interface, "start", lambda vs, led, provider: captured.update(provider=provider)):
            t = threading.Thread(target=run.main, daemon=True)
            t.start()
            time.sleep(2.0)

        state = captured["provider"]()
        self.assertEqual(state["source"], "HDMI")
        self.assertTrue(state["hdmi_enabled"])
        self.assertFalse(state["tv_enabled"])

        leds = np.array(run.LED_DATA_BUFFER[:], dtype=np.int32).reshape(-1, 3)      # BGR
        n_left = settings.LEDS_LEFT
        left, right = leds[:n_left], leds[-settings.LEDS_RIGHT:]
        self.assertGreater(left[:, 2].mean(), 40)           # слева красный
        self.assertLess(left[:, 0].mean(), 10)
        self.assertGreater(right[:, 0].mean(), 40)          # справа синий
        self.assertLess(right[:, 2].mean(), 10)


class SegmentsTest(unittest.TestCase):
    def frame(self):
        f = np.zeros((settings.TARGET_FRAME_HEIGHT, settings.TARGET_FRAME_WIDTH, 3), dtype=np.uint8)
        f[:, :settings.TARGET_FRAME_WIDTH // 2] = (0, 0, 200)
        return f

    def test_any_thickness_gives_one_colour_per_led(self):
        for thickness in (1, 2, 3):
            with mock.patch.object(settings, "LEDS_THICKNESS", thickness):
                proc = AmbilightProcessor()
                colors = proc.segment_colors(self.frame())
                self.assertEqual(colors.shape, (settings.LED_COUNT, 3), "thickness=%d" % thickness)
                self.assertFalse(np.isnan(colors).any())


if __name__ == "__main__":
    unittest.main()
