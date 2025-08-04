import spidev
import numpy as np
import multiprocessing as mp

from constants import COLORS_COUNT, BIT_PER_LED, COLOR_ORDER, SKIP_FIRST_LED
from settings import settings


class WS2812B_Controller:
    def __init__(self, led_count, buffer):
        self.buffer = buffer
        self.led_process = None
        self.byte_buffer_len  = None
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

        self.bit_buffer[pos+0*24:pos+(1)*24] = self._encode_byte(colors[0])
        self.bit_buffer[pos+1*24:pos+(2)*24] = self._encode_byte(colors[1])
        self.bit_buffer[pos+2*24:pos+(3)*24] = self._encode_byte(colors[2])

    def fill(self, r, g, b):
        start = 1 if SKIP_FIRST_LED else 0
        for i in range(start, self.led_count):
            self.set_pixel(i, r, g, b)
        self.show()

    def show(self):
        """Оптимизированная отправка данных"""
        byte_buffer = np.packbits(self.bit_buffer.reshape(-1, 3))
        byte_buffer_len = self.byte_buffer_len if self.byte_buffer_len else len(byte_buffer)

        # Автоматическая разбивка на пакеты
        chunk_size = 4096
        for i in range(0, byte_buffer_len, chunk_size):
            self.spi.xfer2(byte_buffer[i:i+chunk_size].tolist())

        # Гарантированный сброс
        self.spi.xfer2(self.reset_bits.tolist())

    def set_cv_array(self, colors):
        used_color = 0
        for i in range(self.led_count):
            if not (SKIP_FIRST_LED and i == 1):
                b = colors[used_color] + settings.COLOR_SHIFT_BLUE
                g = colors[used_color+1] + settings.COLOR_SHIFT_GREEN
                r = colors[used_color+2] + settings.COLOR_SHIFT_RED

                b = 255 if b > 255 else b
                g = 255 if g > 255 else g
                r = 255 if r > 255 else r

                b = 0 if b < 0 else b
                g = 0 if g < 0 else g
                r = 0 if r < 0 else r

                self.set_pixel(i, *[r, g, b])
                used_color += COLORS_COUNT

        self.show()

    @staticmethod
    def ambilight_cycle(target_arr, service):
        try:
            while True:
                if target_arr:
                    service.set_cv_array(target_arr)
        except KeyboardInterrupt:
            service.stop()

    def stop(self):
        settings.IS_LED_ENABLED = False
        if not self.led_process:
            return

        try:
            self.led_process.terminate()
            self.led_process.join()
            self.led_process.close()
        except Exception as exc:
            print(f"Can't stop {exc}")

        self.led_process = None
        self.fill(0, 0, 0)
        self.spi.close()

    def start(self):
        settings.IS_LED_ENABLED = True

        if self.led_process:
            return

        self.open_spi()
        self.led_process = mp.Process(target=self.ambilight_cycle, args=(self.buffer, self,))
        self.led_process.start()
