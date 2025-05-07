import numpy as np

from constants import COLORS_COUNT
from settings import settings


class AmbilightProcessor:
    def __init__(self):
        self.img_width = settings.TARGET_FRAME_WIDTH
        self.img_height = settings.TARGET_FRAME_HEIGHT

        # Конфигурация светодиодов для вычисления
        self.leds_left = settings.LEDS_LEFT
        self.leds_top = settings.LEDS_TOP
        self.leds_right = settings.LEDS_RIGHT
        self.leds_bottom = settings.LEDS_BOTTOM

        self.thickness = settings.LEDS_THICKNESS
        self.total_leds = settings.LED_COUNT

        # Параметры сглаживания (экспоненциальное сглаживание)
        self.smoothing_factor = settings.AMBILIGHT_SMOOTHING_FACTOR  # Чем меньше, тем плавнее
        self.smoothed_colors = np.zeros((self.total_leds, COLORS_COUNT), dtype=np.float32)

    def process_frame(self, frame):
        """Обрабатывает кадр и возвращает цвета для светодиодов."""
        colors = []

        # Левые светодиоды (слева направо, сверху вниз)
        for i in range(0, self.leds_left, self.thickness):
            segment_height = self.img_height // self.leds_left
            y_start = i * segment_height
            y_end = (i + 1) * segment_height
            segment = frame[y_start:y_end, :30]
            avg_color = np.mean(segment, axis=(0, 1))
            for i in range(0, self.thickness):
                colors.append(avg_color)

        # Верхние светодиоды (слева направо)
        for i in range(0, self.leds_top, self.thickness):
            segment_width = self.img_width // self.leds_top
            x_start = i * segment_width
            x_end = (i + 1) * segment_width
            segment = frame[:30, x_start:x_end]
            avg_color = np.mean(segment, axis=(0, 1))
            for i in range(0, self.thickness):
                colors.append(avg_color)

        # Правые светодиоды (сверху вниз)
        for i in range(0, self.leds_right, self.thickness):
            segment_height = self.img_height // self.leds_right
            y_start = i * segment_height
            y_end = (i + 1) * segment_height
            segment = frame[y_start:y_end, -30:]
            avg_color = np.mean(segment, axis=(0, 1))
            for i in range(0, self.thickness):
                colors.append(avg_color)

        # 4. Нижние светодиоды (слева направо)
        for i in range(0, self.leds_bottom, self.thickness):
            segment_width = self.img_width // self.leds_bottom
            x_start = int(i * segment_width)
            x_end = int((i + 1) * segment_width)
            segment = frame[x_start:x_end, self.img_height - 30:self.img_height]
            avg_color = np.mean(segment, axis=(0, 1))

            for i in range(0, self.thickness):
                colors.append(avg_color)

        if len(colors) > self.self.total_leds:
            colors = colors[:self.total_leds]

        colors = np.array(colors, dtype=np.float32)

        # Применяем сглаживание (экспоненциальное)
        self.smoothed_colors = (
            self.smoothing_factor * colors +
            (1 - self.smoothing_factor) * self.smoothed_colors
        )

        return self.smoothed_colors.astype(np.uint8)
