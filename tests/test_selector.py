import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from selector import Selector


class SelectorTest(unittest.TestCase):
    def setUp(self):
        self.sel = Selector(threshold=12, hold=8.0)
        self.t = 1000.0

    def pick(self, dt, peak, fresh=True):
        return self.sel.pick(self.t + dt, peak, fresh)

    def test_tv_when_hdmi_never_had_picture(self):
        self.assertEqual(self.pick(0, 0), Selector.TV)

    def test_hdmi_picture_takes_priority_at_once(self):
        self.assertEqual(self.pick(0, 0), Selector.TV)
        self.assertEqual(self.pick(1, 200), Selector.HDMI)

    def test_dark_scene_keeps_hdmi_until_hold_expires(self):
        self.pick(0, 200)
        self.assertEqual(self.pick(5, 0), Selector.HDMI)
        self.assertEqual(self.pick(7.9, 0), Selector.HDMI)
        self.assertEqual(self.pick(8.1, 0), Selector.TV)

    def test_picture_returning_switches_back_immediately(self):
        self.pick(0, 200)
        self.assertEqual(self.pick(20, 0), Selector.TV)
        self.assertEqual(self.pick(21, 150), Selector.HDMI)

    def test_picture_below_threshold_is_not_a_picture(self):
        self.assertEqual(self.pick(0, 12), Selector.TV)
        self.assertEqual(self.pick(1, 13), Selector.HDMI)

    def test_stale_capture_does_not_count_as_picture(self):
        self.assertEqual(self.pick(0, 255, fresh=False), Selector.TV)


if __name__ == "__main__":
    unittest.main()
