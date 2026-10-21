import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("spidev", types.SimpleNamespace(SpiDev=object))   # SPI на тестах не нужен

from fastapi import HTTPException

import run
from interface import interface, router_capture
from settings import settings


class SourceTogglesTest(unittest.TestCase):
    def setUp(self):
        self.saved = (settings.TV_ENABLED, settings.TV_MAC, interface.capture)

    def tearDown(self):
        settings.TV_ENABLED, settings.TV_MAC, interface.capture = self.saved

    def test_sources_are_enabled_by_default(self):
        self.assertTrue(settings.HDMI_ENABLED)
        self.assertTrue(settings.TV_ENABLED)

    def test_tv_source_is_not_created_when_disabled(self):
        settings.TV_ENABLED = False
        settings.TV_MAC = "6c:22:1a:9e:a0:04"
        self.assertIsNone(run.make_tv_source(None))

    def test_tv_source_is_not_created_without_mac(self):
        settings.TV_ENABLED = True
        settings.TV_MAC = "  "
        self.assertIsNone(run.make_tv_source(None))

    def test_capture_api_reports_disabled_hdmi(self):
        interface.capture = None
        with self.assertRaises(HTTPException) as ctx:
            router_capture.capture()
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
