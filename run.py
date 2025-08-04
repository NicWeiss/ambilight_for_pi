
from led import WS2812B_Controller
from capture import VideoStream
from ambilight import AmbilightProcessor
from interface import interface
import multiprocessing as mp

from constants import COLORS_COUNT
from settings import settings

LED_DATA_BUFFER = mp.Array("i", settings.LED_COUNT * COLORS_COUNT)


def start_led_process(target_arr):
    leds = WS2812B_Controller(settings.LED_COUNT)
    leds.open_spi()
    try:
        while True:
            if target_arr:
                leds.set_cv_array(target_arr)
    except KeyboardInterrupt:
        leds.fill(0, 0, 0)
        leds.spi.close()


# Поток управления лентой
led_process = mp.Process(target=start_led_process, args=(LED_DATA_BUFFER,))
led_process.start()

# Поток видеозахвата
vs = VideoStream()
vs.start()

ambilight = AmbilightProcessor()

interface.start(vs)

# Цикл вычисления подсветки
try:
    while True:
        frame = vs.read()
        led_colors = ambilight.process_frame(frame)

        index = 0
        for val in led_colors:
            r, g, b = val
            if index > len(LED_DATA_BUFFER):
                continue

            LED_DATA_BUFFER[index] = r
            LED_DATA_BUFFER[index+1] = g
            LED_DATA_BUFFER[index+2] = b
            index += COLORS_COUNT

except KeyboardInterrupt:
    vs.release()
    print("\nПрограмма завершена")
