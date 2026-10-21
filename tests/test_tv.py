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


if __name__ == "__main__":
    unittest.main()
