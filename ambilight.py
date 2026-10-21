import math

import numpy as np

from constants import COLORS_COUNT
from settings import settings


class AmbilightProcessor:
    def __init__(self):
        self.img_width = settings.TARGET_FRAME_WIDTH
        self.img_height = settings.TARGET_FRAME_HEIGHT

        # Конфигурация светодиодов для вычисления
        self.leds_left = settings.LEDS_LEFT or 1
        self.leds_top = settings.LEDS_TOP  or 1
        self.leds_right = settings.LEDS_RIGHT  or 1
        self.leds_bottom = settings.LEDS_BOTTOM  or 1

        self.segment_width_top = self.img_width // self.leds_top
        self.segment_width_bottom = self.img_width // self.leds_bottom
        self.segment_height_left = self.img_height // self.leds_left
        self.segment_height_right = self.img_height // self.leds_right

        self.top_check = {}

        self.thickness = settings.LEDS_THICKNESS
        self.total_leds = settings.LED_COUNT

        # Параметры сглаживания (экспоненциальное сглаживание)
        self.smoothing_factor = settings.AMBILIGHT_SMOOTHING_FACTOR  # Чем меньше, тем плавнее
        self.smoothed_colors = np.zeros((self.total_leds, COLORS_COUNT), dtype=np.float32)

    def segment_colors(self, frame):
        """Средние цвета сегментов кадра (BGR, без сглаживания): по одному цвету на светодиод."""
        if frame is None or frame.shape[:2] != (self.img_height, self.img_width):
            pass

        colors = []

        # Левые светодиоды (слева направо, сверху вниз)
        for i in range(self.leds_left, 0, (self.thickness * -1)):
            y_start = i * self.segment_height_left
            y_end = (i + self.thickness) * self.segment_height_left
            segment = frame[y_start:y_end, :settings.AMBILIGHT_ANALYZE_DEEP]
            avg_color = np.mean(segment, axis=(0, 1))
            for _ in range(0, self.thickness):
                colors.append(avg_color)

        # Верхние светодиоды (слева направо)
        for i in range(0, self.leds_top, self.thickness):
            x_start = i * self.segment_width_top
            x_end = (i + self.thickness) * self.segment_width_top
            segment = frame[:settings.AMBILIGHT_ANALYZE_DEEP, x_start:x_end]
            avg_color = np.mean(segment, axis=(0, 1))
            for _ in range(0, self.thickness):
                colors.append(avg_color)

        # Правые светодиоды (сверху вниз)
        for i in range(0, self.leds_right, self.thickness):
            y_start = i * self.segment_height_right
            y_end = (i + self.thickness) * self.segment_height_right
            segment = frame[y_start:y_end, - settings.AMBILIGHT_ANALYZE_DEEP:]
            avg_color = np.mean(segment, axis=(0, 1))
            for _ in range(0, self.thickness):
                colors.append(avg_color)

        # 4. Нижние светодиоды (слева направо)
        for i in range(0, self.leds_bottom, self.thickness):
            x_start = int(i * self.segment_width_bottom)
            x_end = int((i + self.thickness) * self.segment_width_bottom)
            segment = frame[x_start:x_end, self.img_height - settings.AMBILIGHT_ANALYZE_DEEP:self.img_height]
            avg_color = np.mean(segment, axis=(0, 1))
            for _ in range(0, self.thickness):
                colors.append(avg_color)

        if len(colors) > self.total_leds:
            colors = colors[:self.total_leds]

        # пустой сегмент (выходит за кадр, если число светодиодов делит высоту нацело) даёт NaN: считаем его чёрным
        return np.nan_to_num(np.array(colors, dtype=np.float32))

    def process_frame(self, frame):
        """Обрабатывает кадр и возвращает цвета для светодиодов (сглаживание - коэффициент на кадр)."""
        colors = self.segment_colors(frame)

        # Применяем сглаживание (экспоненциальное)
        self.smoothed_colors = (
            self.smoothing_factor * colors +
            (1 - self.smoothing_factor) * self.smoothed_colors
        )

        return self.smoothed_colors.astype(np.uint8)

    def segment_counts(self):
        """Сколько сегментов у каждой стороны: слева (снизу вверх), сверху, справа (сверху вниз)."""
        return (
            len(range(self.leds_left, 0, -self.thickness)),
            len(range(0, self.leds_top, self.thickness)),
            len(range(0, self.leds_right, self.thickness)),
        )

    def from_segments(self, segments):
        """Готовые цвета сегментов (слева, сверху, справа), посчитанные на стороне ТВ, ->
        цвета светодиодов в том же порядке и количестве, что и у segment_colors()."""
        left, top, right = self.segment_counts()
        parts = [segments[:left], segments[left:left + top], segments[left + top:left + top + right]]
        colors = np.concatenate([np.repeat(p, self.thickness, axis=0) for p in parts]).astype(np.float32)
        return self._fit(colors)

    def _fit(self, colors):
        """Обрезает или дополняет чёрным до числа светодиодов."""
        if len(colors) > self.total_leds:
            return colors[:self.total_leds]
        if len(colors) < self.total_leds:
            pad = np.zeros((self.total_leds - len(colors), COLORS_COUNT), np.float32)
            return np.concatenate([colors, pad])
        return colors

    def smooth(self, target, dt, tau):
        """Сглаживание по времени: постоянная tau не зависит от частоты кадров источника."""
        alpha = 1.0 - math.exp(-max(dt, 1e-3) / max(tau, 1e-3))
        self.smoothed_colors += alpha * (self._fit(target) - self.smoothed_colors)
        return np.clip(self.smoothed_colors, 0, 255).astype(np.uint8)

    def grade(self, colors):
        """Цветокоррекция выхода: общая яркость, насыщенность, приглушённый белый (uint8 (N, 3) -> uint8 (N, 3)).

        Оттенок не меняется. Насыщенность s (0..1) умножается на LED_SATURATION; яркость бледных цветов (белого и
        близких к нему) уменьшается на LED_WHITE_REDUCTION * (1 - s)^LED_WHITE_POWER; затем всё умножается на LED_BRIGHTNESS."""
        bright = settings.LED_BRIGHTNESS
        gain = settings.LED_SATURATION
        reduction = settings.LED_WHITE_REDUCTION
        if bright == 1.0 and gain == 1.0 and reduction == 0.0:
            return colors

        c = colors.astype(np.float32)
        peak = c.max(axis=1, keepdims=True)
        low = c.min(axis=1, keepdims=True)
        span = peak - low
        sat = np.divide(span, peak, out=np.zeros_like(span), where=peak > 0)
        hue = np.divide(c - low, span, out=np.ones_like(c), where=span > 0)   # оттенок: максимум 1, минимум 0

        sat = np.minimum(1.0, sat * gain)
        value = peak * (1.0 - reduction * np.power(1.0 - sat, settings.LED_WHITE_POWER)) * bright
        out = value * ((1.0 - sat) + sat * hue)
        # при яркости выше 1 самый яркий канал может упереться в 255: подгоняем остальные, чтобы оттенок не уехал
        top = out.max(axis=1, keepdims=True)
        out = out * np.minimum(1.0, 255.0 / np.maximum(top, 1e-6))
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)
