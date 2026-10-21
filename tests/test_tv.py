import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tv

SAMPLE = """\
192.168.100.1 dev wlan0 lladdr cc:d8:43:b9:e4:ae REACHABLE
192.168.100.4 dev wlan0 lladdr 6c:22:1a:9e:a0:04 STALE
192.168.100.77 dev wlan0  FAILED
192.168.100.88 dev wlan0  INCOMPLETE
192.168.100.200 dev wlan0 lladdr 6C:22:1A:9E:A0:04 PERMANENT
"""


class NeighboursTest(unittest.TestCase):
    def test_parse_skips_failed_and_incomplete(self):
        table = tv.parse_neighbours(SAMPLE)
        self.assertEqual(set(table), {"192.168.100.1", "192.168.100.4", "192.168.100.200"})
        self.assertEqual(table["192.168.100.4"], ("6c:22:1a:9e:a0:04", "wlan0"))

    def test_mac_is_compared_case_insensitively(self):
        self.assertEqual(tv.parse_neighbours(SAMPLE)["192.168.100.200"][0], "6c:22:1a:9e:a0:04")

    def test_candidates_put_last_known_address_first(self):
        with mock.patch.object(tv, "neighbours", return_value=tv.parse_neighbours(SAMPLE)):
            cands = tv.tv_candidates("6c:22:1a:9e:a0:04", preferred="192.168.100.200")
            self.assertEqual([ip for ip, _ in cands], ["192.168.100.200", "192.168.100.4"])
            cands = tv.tv_candidates("6c:22:1a:9e:a0:04", preferred="192.168.100.4")
            self.assertEqual(cands[0][0], "192.168.100.4")

    def test_unknown_mac_gives_no_candidates(self):
        with mock.patch.object(tv, "neighbours", return_value=tv.parse_neighbours(SAMPLE)):
            self.assertEqual(tv.tv_candidates("aa:bb:cc:dd:ee:ff"), [])



class FlatGrayTest(unittest.TestCase):
    def seg(self, rgb, n=109):
        import numpy as np
        return np.tile(np.array(rgb, dtype=np.float32), (n, 1))

    def test_uniform_mid_gray_is_flat(self):
        self.assertTrue(tv.is_flat_gray(self.seg((130, 130, 130))))

    def test_real_picture_is_not_flat(self):
        import numpy as np
        frame = self.seg((130, 130, 130))
        frame[10] = (20, 60, 200)
        self.assertFalse(tv.is_flat_gray(frame))
        rng = np.random.default_rng(1)
        self.assertFalse(tv.is_flat_gray(rng.integers(0, 255, (109, 3)).astype(np.float32)))

    def test_black_and_white_screens_are_not_flat(self):
        # чёрный погаснет сам, белый экран должен светить белым
        self.assertFalse(tv.is_flat_gray(self.seg((5, 5, 5))))
        self.assertFalse(tv.is_flat_gray(self.seg((250, 250, 250))))

    def test_uniform_color_is_not_flat(self):
        self.assertFalse(tv.is_flat_gray(self.seg((40, 90, 200))))

    def test_full_image_in_legacy_mode(self):
        import numpy as np
        self.assertTrue(tv.is_flat_gray(np.full((120, 160, 3), 130, dtype=np.uint8)))

    def test_can_be_disabled(self):
        with mock.patch.object(tv.settings, "TV_FLAT_GRAY_AS_BLANK", False):
            self.assertFalse(tv.is_flat_gray(self.seg((130, 130, 130))))


class BlankStateTest(unittest.TestCase):
    def source(self):
        return tv.TvSource((29, 51, 29), 20, 10)

    def frame(self, rgb):
        import numpy as np
        return np.tile(np.array(rgb, dtype=np.float32), (109, 1))

    def test_flat_frames_hide_picture_after_three_in_a_row(self):
        s = self.source()
        s._store(self.frame((20, 60, 200)))
        self.assertIsNotNone(s.latest(5))
        for _ in range(2):
            s._store(self.frame((130, 130, 130)))
        self.assertFalse(s.blank)                    # две плоских подряд - ещё не считаем
        self.assertIsNotNone(s.latest(5))
        s._store(self.frame((130, 130, 130)))
        self.assertTrue(s.blank)
        self.assertIsNone(s.latest(5))               # в ленту ничего не отдаём
        self.assertIsNotNone(s.age())                # но поток живой

    def test_picture_returns_immediately(self):
        s = self.source()
        for _ in range(5):
            s._store(self.frame((130, 130, 130)))
        self.assertTrue(s.blank)
        s._store(self.frame((200, 30, 30)))
        self.assertFalse(s.blank)
        self.assertIsNotNone(s.latest(5))


if __name__ == "__main__":
    unittest.main()


class SampleTest(unittest.TestCase):
    def frame(self, v):
        import numpy as np
        return np.tile(np.array([v, v + 1, v + 2], dtype=np.float32), (109, 1))

    def test_sample_follows_capture_time(self):
        s = tv.TvSource((29, 51, 29), 20, 10)
        s._playout.delay = 0.1
        import time
        t0 = time.time()
        s._store(self.frame(10), 1000)
        s._store(self.frame(110), 1100)
        out = s.sample(s._ts + 0.05)                  # между кадрами: половина пути
        self.assertIsNotNone(out)
        self.assertAlmostEqual(float(out[0][0]), 60, delta=3)

    def test_sample_is_none_for_blank_or_legacy_or_stale(self):
        import time
        s = tv.TvSource((29, 51, 29), 20, 10)
        self.assertIsNone(s.sample(time.time()))                      # кадров нет
        for i in range(3):
            s._store(self.frame(10) * 0 + 130, 1000 + i * 33)         # плоский серый
        self.assertTrue(s.blank)
        self.assertIsNone(s.sample(time.time()))
        s2 = tv.TvSource((29, 51, 29), 20, 10)
        s2._store(self.frame(10), 1000)
        self.assertIsNone(s2.sample(s2._ts + 60))                     # кадры устарели
        s2._mode = "legacy"
        self.assertIsNone(s2.sample(s2._ts))                          # запасной режим: другой путь


class DatagramTest(unittest.TestCase):
    """Приём кадров UDP-датаграммами (без ADB и реального ТВ)."""

    SEGMENTS = (29, 51, 29)

    def make_source(self):
        s = tv.TvSource(self.SEGMENTS, 20, 10)
        s._enabled.set()
        return s

    def frame_bytes(self, cap_ms, value):
        return cap_ms.to_bytes(4, "little") + bytes([value, value + 1, value + 2]) * sum(self.SEGMENTS)

    def run_receiver(self, source, datagrams, first_timeout=3.0, frame_timeout=1.0):
        import socket
        import threading
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.bind(("127.0.0.1", 0))
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        out = {}

        def work():
            out["r"] = source._read_datagrams(rx, 4 + sum(self.SEGMENTS) * 3, source._decode_segments, first_timeout, frame_timeout)

        t = threading.Thread(target=work)
        t.start()
        import time
        time.sleep(0.2)
        for d in datagrams:
            tx.sendto(d, rx.getsockname())
            time.sleep(0.01)
        time.sleep(0.3)
        source._enabled.clear()
        t.join(5)
        rx.close()
        tx.close()
        return out["r"]

    def test_several_frames_in_one_datagram_are_all_stored(self):
        s = self.make_source()
        d1 = self.frame_bytes(1000, 10) + self.frame_bytes(1016, 20) + self.frame_bytes(1033, 30)
        got, reason = self.run_receiver(s, [d1, self.frame_bytes(1050, 40)])
        self.assertTrue(got)
        self.assertEqual(s.seq, 4)

    def test_broken_trailing_bytes_are_ignored(self):
        s = self.make_source()
        d = self.frame_bytes(1000, 10) + b"\x01\x02\x03"           # лишние байты после целого кадра
        self.run_receiver(s, [d])
        self.assertEqual(s.seq, 1)

    def test_short_garbage_datagram_is_ignored(self):
        s = self.make_source()
        self.run_receiver(s, [b"hello"])
        self.assertEqual(s.seq, 0)

    def test_silence_ends_with_timeout(self):
        s = self.make_source()
        got, reason = self.run_receiver(s, [], first_timeout=1.0)
        self.assertEqual((got, reason), (False, "timeout"))

    def test_received_frames_reach_the_playout(self):
        s = self.make_source()
        self.run_receiver(s, [self.frame_bytes(1000, 10) + self.frame_bytes(1016, 110)])
        self.assertEqual(len(s._playout._times), 2)


class TransportTest(unittest.TestCase):
    def test_udp_failure_switches_to_adb_for_a_while(self):
        s = tv.TvSource((29, 51, 29), 20, 10)
        s._serial = "192.168.100.4:5555"
        with mock.patch.object(s, "_stream_vcap_udp", return_value=(False, "timeout")), \
                mock.patch.object(s, "_alive", return_value=True), \
                mock.patch.object(s, "_read_frames", return_value=(True, "disabled")) as adb:
            got, _ = s._stream("vcap")                                   # UDP не прошёл
            self.assertFalse(got)
            self.assertGreater(s._adb_until, __import__("time").time())
            got, _ = s._stream("vcap")                                   # следующая попытка идёт через ADB
            self.assertTrue(got)
            adb.assert_called_once()
            self.assertEqual(s.transport, "adb")

    def test_adb_transport_can_be_forced(self):
        s = tv.TvSource((29, 51, 29), 20, 10)
        s._serial = "192.168.100.4:5555"
        with mock.patch.object(tv.settings, "TV_TRANSPORT", "adb"), \
                mock.patch.object(s, "_stream_vcap_udp") as udp, \
                mock.patch.object(s, "_read_frames", return_value=(True, "disabled")):
            s._stream("vcap")
            udp.assert_not_called()
            self.assertEqual(s._playout.delay, tv.settings.TV_PLAYOUT_DELAY_ADB)
