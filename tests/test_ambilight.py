import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ambilight import AmbilightProcessor
from settings import settings


class AmbilightTest(unittest.TestCase):
    def setUp(self):
        self.thickness = settings.LEDS_THICKNESS
        self.bottom = settings.LEDS_BOTTOM

    def tearDown(self):
        settings.LEDS_THICKNESS = self.thickness
        settings.LEDS_BOTTOM = self.bottom

    def test_segment_counts_follow_leds(self):
        left, top, right = AmbilightProcessor().segment_counts()
        self.assertEqual((left, top, right), (settings.LEDS_LEFT, settings.LEDS_TOP, settings.LEDS_RIGHT))

    def test_from_segments_keeps_order_and_led_count(self):
        proc = AmbilightProcessor()
        left, top, right = proc.segment_counts()
        seg = np.zeros((left + top + right, 3), np.float32)
        seg[:left, 0] = 1       # слева
        seg[left:left + top, 0] = 2   # сверху
        seg[left + top:, 0] = 3       # справа
        colors = proc.from_segments(seg)
        self.assertEqual(colors.shape, (settings.LED_COUNT, 3))
        self.assertTrue((colors[:left, 0] == 1).all())
        self.assertTrue((colors[left:left + top, 0] == 2).all())
        self.assertTrue((colors[left + top:, 0] == 3).all())

    def test_thickness_repeats_each_segment(self):
        settings.LEDS_THICKNESS = 2
        proc = AmbilightProcessor()
        left, top, right = proc.segment_counts()
        seg = np.arange((left + top + right) * 3, dtype=np.float32).reshape(-1, 3)
        colors = proc.from_segments(seg)
        self.assertEqual(len(colors), settings.LED_COUNT)
        self.assertTrue((colors[0] == colors[1]).all())
        self.assertTrue((colors[2] == seg[1]).all())

    def test_from_segments_pads_with_black_when_short(self):
        proc = AmbilightProcessor()
        colors = proc.from_segments(np.full((3, 3), 50, np.float32))
        self.assertEqual(len(colors), settings.LED_COUNT)

    def test_smoothing_does_not_depend_on_call_rate(self):
        target = np.full((settings.LED_COUNT, 3), 200, np.float32)
        a, b = AmbilightProcessor(), AmbilightProcessor()
        a.smooth(target, 0.2, 0.1)
        b.smooth(target, 0.1, 0.1)
        b.smooth(target, 0.1, 0.1)
        self.assertTrue(np.allclose(a.smoothed_colors, b.smoothed_colors, atol=1e-3))

    def test_smoothing_converges_to_target(self):
        proc = AmbilightProcessor()
        target = np.full((settings.LED_COUNT, 3), 120, np.float32)
        out = proc.smooth(target, 10.0, 0.1)
        self.assertTrue((out == 120).all())


if __name__ == "__main__":
    unittest.main()


class GradeTest(unittest.TestCase):
    def setUp(self):
        from ambilight import AmbilightProcessor
        self.proc = AmbilightProcessor()

    def grade(self, rows, **kw):
        import numpy as np
        from settings import settings
        old = {k: getattr(settings, k) for k in kw}
        for k, v in kw.items():
            setattr(settings, k, v)
        try:
            return self.proc.grade(np.array(rows, dtype=np.uint8))
        finally:
            for k, v in old.items():
                setattr(settings, k, v)

    def test_neutral_settings_change_nothing(self):
        rows = [[10, 200, 90], [255, 255, 255], [0, 0, 0]]
        out = self.grade(rows, LED_BRIGHTNESS=1.0, LED_SATURATION=1.0, LED_WHITE_REDUCTION=0.0)
        self.assertEqual(out.tolist(), rows)

    def test_brightness_scales_everything(self):
        out = self.grade([[200, 100, 0]], LED_BRIGHTNESS=0.5, LED_SATURATION=1.0, LED_WHITE_REDUCTION=0.0)
        self.assertEqual(out[0].tolist(), [100, 50, 0])

    def test_white_is_dimmed_more_than_saturated_color(self):
        out = self.grade([[255, 255, 255], [0, 0, 255]], LED_BRIGHTNESS=1.0, LED_SATURATION=1.0, LED_WHITE_REDUCTION=0.5)
        self.assertEqual(out[0].tolist(), [128, 128, 128])     # белый вдвое темнее
        self.assertEqual(out[1].tolist(), [0, 0, 255])         # чисто красный не тронут (BGR)

    def test_gray_stays_gray(self):
        out = self.grade([[120, 120, 120]], LED_SATURATION=3.0)
        self.assertEqual(len(set(out[0].tolist())), 1)

    def test_saturation_increases_and_hue_is_kept(self):
        base = [[150, 120, 100]]                               # BGR: слегка оранжевый
        out = self.grade(base, LED_BRIGHTNESS=1.0, LED_SATURATION=2.0, LED_WHITE_REDUCTION=0.0)[0].astype(int)
        spread_before = max(base[0]) - min(base[0])
        self.assertGreater(out.max() - out.min(), spread_before)
        self.assertEqual(out.argmax(), 0)                      # самый яркий канал прежний (синий в BGR)
        self.assertEqual(out.argmin(), 2)

    def test_values_never_overflow(self):
        out = self.grade([[255, 0, 0], [255, 255, 0], [255, 250, 255]], LED_BRIGHTNESS=1.0, LED_SATURATION=4.0, LED_WHITE_REDUCTION=0.0)
        self.assertTrue(((out >= 0) & (out <= 255)).all())

    def test_brightness_above_one_keeps_hue_when_clipping(self):
        out = self.grade([[200, 100, 0]], LED_BRIGHTNESS=2.0, LED_SATURATION=1.0, LED_WHITE_REDUCTION=0.0)[0]
        self.assertEqual(out[0], 255)                           # самый яркий канал упёрся в потолок
        self.assertAlmostEqual(out[1] / out[0], 0.5, delta=0.01)  # пропорции каналов прежние
        self.assertEqual(out[2], 0)
