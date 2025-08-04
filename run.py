
from led import WS2812B_Controller
from capture import VideoStream
from ambilight import AmbilightProcessor
from interface import interface
import multiprocessing as mp

from constants import COLORS_COUNT
from settings import settings

LED_DATA_BUFFER = mp.Array("i", settings.LED_COUNT * COLORS_COUNT)

# Поток управления лентой
led = WS2812B_Controller(settings.LED_COUNT, LED_DATA_BUFFER)
led.start()

# Поток видеозахвата
vs = VideoStream()
vs.start()

# Процессор подсветки
ambilight = AmbilightProcessor()


# Интерфейс управления
interface.start(vs, led)

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
