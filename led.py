import os
import signal
import spidev
import numpy as np
import multiprocessing as mp
from time import sleep

from constants import COLORS_COUNT, COLOR_ORDER, SKIP_FIRST_LED
from settings import settings

# Один бит WS2812B кодируется тремя битами SPI: 1 -> 110, 0 -> 100. Таблица: байт -> 24 бита SPI.
_BIT_LUT = np.zeros((256, 24), dtype=np.uint8)
for _value in range(256):
    for _n in range(8):
        _BIT_LUT[_value, _n * 3:_n * 3 + 3] = (1, 1, 0) if _value & (0x80 >> _n) else (1, 0, 0)

RESET_BYTES = 64


def encode_pixels(pix, written):
    """pix: (N, 3) значения r, g, b (0..255); written: (N,) bool - какие светодиоды записываются.
    Незаписанные остаются нулевыми битами (линия прижата к нулю). Возвращает байты для SPI."""
    order = [1, 0, 2] if COLOR_ORDER == "GRB" else [0, 1, 2]
    channels = pix[:, order]
    bits = _BIT_LUT[channels].reshape(len(pix), 72)
    bits[~written] = 0
    return np.packbits(bits.reshape(-1)).tobytes()


def cv_to_pixels(colors, led_count):
    """Плоский буфер b, g, r, b, g, r... -> ((N, 3) r, g, b с поправкой цвета, (N,) маска записи).
    Повторяет прежнюю логику: при SKIP_FIRST_LED светодиоды 0 и 1 не пишутся, остальные получают цвета со сдвигом на один."""
    cv = np.asarray(colors, dtype=np.int32).reshape(-1, COLORS_COUNT)
    pix = np.zeros((led_count, 3), dtype=np.int32)
    written = np.ones(led_count, dtype=bool)
    if SKIP_FIRST_LED:
        written[:2] = False
        src = cv[1:led_count - 1]
        pix[2:2 + len(src)] = src[:, ::-1]           # b, g, r -> r, g, b
    else:
        src = cv[:led_count]
        pix[:len(src)] = src[:, ::-1]
    shifts = np.array([settings.COLOR_SHIFT_RED, settings.COLOR_SHIFT_GREEN, settings.COLOR_SHIFT_BLUE], dtype=np.int32)
    pix = np.where(pix > 10, pix + shifts, pix)
    return np.clip(pix, 0, 255), written


class WS2812B_Controller:
    def __init__(self, led_count, buffer):
        self.buffer = buffer
        self.led_process = None
        self.byte_buffer_len  = None
        self.spi = None
        self.led_count = led_count
        self.new_frame = mp.Event()          # главный цикл сообщает, что в буфере новые цвета
        self.sent = mp.Value("l", 0)         # сколько раз лента перерисована (для статистики)

    def open_spi(self):
        # Настройки SPI
        self.spi = spidev.SpiDev()
        self.spi.open(settings.SPI_BUS, settings.SPI_CHANNEL)  # SPI0 на OrangePi
        self.spi.max_speed_hz = settings.SPI_SPEED
        self.spi.mode = settings.SPI_MODE
        self.spi.lsbfirst = False  # MSB first

    def notify(self):
        """Сообщить процессу ленты, что в буфере новые цвета."""
        self.new_frame.set()

    def show(self, data):
        """Отправка кадра и сброса одной передачей: без паузы внутри кадра."""
        payload = data + bytes(RESET_BYTES)
        if hasattr(self.spi, "writebytes2"):
            self.spi.writebytes2(payload)
        else:
            for i in range(0, len(payload), 4096):
                self.spi.xfer2(list(payload[i:i + 4096]))

    def fill(self, r, g, b):
        pix = np.tile(np.array([r, g, b], dtype=np.int32), (self.led_count, 1))
        written = np.ones(self.led_count, dtype=bool)
        if SKIP_FIRST_LED:
            written[0] = False
        self.show(encode_pixels(pix, written))

    def set_cv_array(self, colors):
        pix, written = cv_to_pixels(colors, self.led_count)
        self.show(encode_pixels(pix, written))
        with self.sent.get_lock():
            self.sent.value += 1

    @staticmethod
    def ambilight_cycle(target_arr, service):
        def blank(*_):
            # при остановке сервиса гасим ленту, а не оставляем последние цвета
            service.fill(0, 0, 0)
            service.spi.close()
            os._exit(0)

        signal.signal(signal.SIGTERM, blank)
        keepalive = 1.0 / max(settings.LED_REFRESH_HZ, 1)
        view = np.frombuffer(target_arr.get_obj(), dtype=np.int32)
        try:
            while True:
                # перерисовываем сразу, как только главный цикл положил новые цвета; без них - не реже keepalive
                service.new_frame.wait(keepalive)
                service.new_frame.clear()
                with target_arr.get_lock():
                    colors = view.copy()                 # целый кадр сразу: без «разрывов» между старым и новым
                service.set_cv_array(colors)
        except KeyboardInterrupt:
            service.stop()

    def stop(self):
        settings.IS_LED_ENABLED = False
        if not self.led_process:
            return

        try:
            self.led_process.terminate()
            self.led_process.join()
            sleep(1)
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

    def status(self):
        return settings.IS_LED_ENABLED
