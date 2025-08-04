import spidev
import numpy as np

from constants import COLORS_COUNT, BIT_PER_LED, COLOR_ORDER, SKIP_FIRST_LED
from settings import settings


class WS2812B_Controller:
    def __init__(self, led_count):
        self.spi = None
        self.led_count = led_count
        self.bit_buffer = np.zeros(led_count * BIT_PER_LED * COLORS_COUNT, dtype=np.uint8)
        self.reset_bits = np.zeros(64, dtype=np.uint8)

    def open_spi(self):
        # Настройки SPI
        self.spi = spidev.SpiDev()
        self.spi.open(settings.SPI_BUS, settings.SPI_CHANNEL)  # SPI0 на OrangePi
        self.spi.max_speed_hz = settings.SPI_SPEED
        self.spi.mode = settings.SPI_MODE
        self.spi.lsbfirst = False  # MSB first

    def _encode_byte(self, byte):
        """Оптимизированное кодирование байта"""
        bits = []
        for i in range(7, -1, -1):
            bits.extend([1, 1, 0] if byte & (1 << i) else [1, 0, 0])
        return bits

    def set_pixel(self, index, r, g, b):
        if SKIP_FIRST_LED and index == 0:
            return

        pos = index * 72
        colors = [g, r, b] if COLOR_ORDER == 'GRB' else [r, g, b]

        for i, color in enumerate(colors):
            self.bit_buffer[pos+i*24:pos+(i+1)*24] = self._encode_byte(color)

    def fill(self, r, g, b):
        start = 1 if SKIP_FIRST_LED else 0
        for i in range(start, self.led_count):
            self.set_pixel(i, r, g, b)
        self.show()

    def show(self):
        """Оптимизированная отправка данных"""
        byte_buffer = np.packbits(self.bit_buffer.reshape(-1, 3))

        # Автоматическая разбивка на пакеты
        chunk_size = 4096
        for i in range(0, len(byte_buffer), chunk_size):
            self.spi.xfer2(byte_buffer[i:i+chunk_size].tolist())

        # Гарантированный сброс
        self.spi.xfer2(self.reset_bits.tolist())

    def set_cv_array(self, colors):
        used_color = 0
        for i in range(self.led_count):
            if not (SKIP_FIRST_LED and i == 1):
                b = colors[used_color]
                g = colors[used_color+1]
                r = colors[used_color+2]

                self.set_pixel(i, *[r, g, b])
                used_color += COLORS_COUNT

        self.show()
