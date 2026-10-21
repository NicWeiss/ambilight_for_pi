import bisect
from collections import deque

# насколько быстро оценка задержки сети подстраивается вверх (против дрейфа часов), доля на кадр
OFFSET_LEAK = 0.0005
# скачок разницы часов больше этого значения (перезапуск ТВ, новый поток) - начинаем заново
OFFSET_JUMP_S = 2.0
KEEP_S = 1.5


class Playout:
    """Воспроизводит кадры по времени съёмки, а не по времени прихода.

    Сеть (Wi-Fi + ADB) доставляет кадры пачками: несколько штук подряд, потом пауза. Если выводить «последний
    пришедший» кадр, лента стоит и прыгает. Здесь каждый кадр ставится на временную шкалу по своей метке времени
    съёмки, а вывод идёт с постоянной задержкой `delay` и линейной интерполяцией между соседними кадрами."""

    def __init__(self, delay):
        self.delay = delay
        self._times = deque()
        self._data = deque()
        self._offset = None
        self._last_ms = None
        self._wraps = 0
        self._starved = 0.0

    def reset(self):
        self._times.clear()
        self._data.clear()
        self._offset = None
        self._last_ms = None
        self._wraps = 0

    @property
    def starvation(self):
        """Доля последних выводов, когда нужный кадр ещё не пришёл (задержки `delay` не хватило)."""
        return self._starved

    def push(self, cap_ms, data, arrival):
        """cap_ms - метка съёмки (миллисекунды часов ТВ, u32 с переполнением), arrival - время прихода на Pi, секунды."""
        if self._last_ms is not None and cap_ms < self._last_ms - 2 ** 31:
            self._wraps += 1
        self._last_ms = cap_ms
        cap = (cap_ms + self._wraps * 2 ** 32) / 1000.0
        diff = arrival - cap

        if self._offset is None or abs(diff - self._offset) > OFFSET_JUMP_S:
            self._offset = diff
            self._times.clear()
            self._data.clear()
        elif diff < self._offset:
            self._offset = diff                      # самая быстрая доставка = настоящая задержка сети
        else:
            self._offset += (diff - self._offset) * OFFSET_LEAK

        # храним время съёмки; сдвиг на часы Pi применяется при выводе, поэтому уточнение оценки сдвигает и старые кадры
        if self._times and cap <= self._times[-1]:
            cap = self._times[-1] + 0.001
        self._times.append(cap)
        self._data.append(data)

        while len(self._times) > 2 and self._times[1] + self._offset < arrival - self.delay - KEEP_S:
            self._times.popleft()
            self._data.popleft()

    def sample(self, now):
        """Цвета на момент now - delay: интерполяция между соседними кадрами. None, если кадров ещё нет."""
        if not self._times:
            return None
        tp = now - self.delay - self._offset         # то же время на шкале часов ТВ
        starved = tp > self._times[-1]
        self._starved += ((1.0 if starved else 0.0) - self._starved) * 0.01
        if tp <= self._times[0]:
            return self._data[0]
        if starved:
            return self._data[-1]
        times = list(self._times)
        i = bisect.bisect_right(times, tp)          # times[i-1] <= tp < times[i]
        t0, t1 = times[i - 1], times[i]
        alpha = (tp - t0) / (t1 - t0)
        return self._data[i - 1] + (self._data[i] - self._data[i - 1]) * alpha
