import os
import sys
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("spidev", types.SimpleNamespace(SpiDev=object))   # на ноутбуке SPI нет

import led
from constants import COLOR_ORDER, SKIP_FIRST_LED
from settings import settings


class ReferenceEncoder:
    """Прежняя (медленная) реализация: эталон, с которым сверяется новая."""

    def __init__(self, count):
        self.count = count
        self.bit_buffer = np.zeros(count * 24 * 3, dtype=np.uint8)

    @staticmethod
    def encode_byte(byte):
        bits = []
        for i in range(7, -1, -1):
            bits.extend([1, 1, 0] if byte & (1 << i) else [1, 0, 0])
        return bits

    def set_pixel(self, index, r, g, b):
        if SKIP_FIRST_LED and index == 0:
            return
        pos = index * 72
        colors = [g, r, b] if COLOR_ORDER == "GRB" else [r, g, b]
        for k in range(3):
            self.bit_buffer[pos + k * 24:pos + (k + 1) * 24] = self.encode_byte(colors[k])

    def fill(self, r, g, b):
        for i in range(1 if SKIP_FIRST_LED else 0, self.count):
            self.set_pixel(i, r, g, b)
        return np.packbits(self.bit_buffer.reshape(-1, 3)).tobytes()

    def set_cv_array(self, colors):
        used = 0
        for i in range(self.count):
            if not (SKIP_FIRST_LED and i == 1):
                b, g, r = colors[used], colors[used + 1], colors[used + 2]
                b = b + settings.COLOR_SHIFT_BLUE if b > 10 else b
                g = g + settings.COLOR_SHIFT_GREEN if g > 10 else g
                r = r + settings.COLOR_SHIFT_RED if r > 10 else r
                b, g, r = (max(0, min(255, v)) for v in (b, g, r))
                self.set_pixel(i, r, g, b)
                used += 3
        return np.packbits(self.bit_buffer.reshape(-1, 3)).tobytes()


class LedEncodingTest(unittest.TestCase):
    N = 109

    def new(self, colors):
        pix, written = led.cv_to_pixels(colors, self.N)
        return led.encode_pixels(pix, written)

    def test_matches_reference_for_random_frames(self):
        rng = np.random.default_rng(7)
        for _ in range(20):
            colors = rng.integers(0, 256, self.N * 3).tolist()
            self.assertEqual(self.new(colors), ReferenceEncoder(self.N).set_cv_array(colors))

    def test_matches_reference_with_colour_shifts(self):
        rng = np.random.default_rng(11)
        with mock.patch.object(settings, "COLOR_SHIFT_RED", 20), mock.patch.object(settings, "COLOR_SHIFT_GREEN", -15), \
                mock.patch.object(settings, "COLOR_SHIFT_BLUE", 300):
            for _ in range(10):
                colors = rng.integers(0, 256, self.N * 3).tolist()
                self.assertEqual(self.new(colors), ReferenceEncoder(self.N).set_cv_array(colors))

    def test_dark_values_are_not_shifted(self):
        colors = [5, 10, 11] * self.N
        with mock.patch.object(settings, "COLOR_SHIFT_RED", 7):
            self.assertEqual(self.new(colors), ReferenceEncoder(self.N).set_cv_array(colors))

    def test_black_and_white_frames(self):
        for v in (0, 255):
            colors = [v] * (self.N * 3)
            self.assertEqual(self.new(colors), ReferenceEncoder(self.N).set_cv_array(colors))

    def test_fill_matches_reference(self):
        ctrl = led.WS2812B_Controller(self.N, [0] * (self.N * 3))
        sent = []
        ctrl.spi = types.SimpleNamespace(writebytes2=lambda data: sent.append(bytes(data)))
        for rgb in ((0, 0, 0), (10, 200, 30)):
            ctrl.fill(*rgb)
            self.assertEqual(sent[-1][:-led.RESET_BYTES], ReferenceEncoder(self.N).fill(*rgb))

    def test_frame_is_followed_by_reset_in_one_write(self):
        ctrl = led.WS2812B_Controller(self.N, [0] * (self.N * 3))
        sent = []
        ctrl.spi = types.SimpleNamespace(writebytes2=lambda data: sent.append(bytes(data)))
        ctrl.show(b"\x01" * 981)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][-led.RESET_BYTES:], bytes(led.RESET_BYTES))

    def test_fallback_to_xfer2_in_chunks(self):
        ctrl = led.WS2812B_Controller(self.N, [0] * (self.N * 3))
        chunks = []
        ctrl.spi = types.SimpleNamespace(xfer2=lambda data: chunks.append(len(data)))
        ctrl.show(b"\x01" * 5000)
        self.assertEqual(sum(chunks), 5000 + led.RESET_BYTES)
        self.assertTrue(all(c <= 4096 for c in chunks))


if __name__ == "__main__":
    unittest.main()
