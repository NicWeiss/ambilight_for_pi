import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playout import Playout


def frame(value):
    return np.array([[value, value, value]], dtype=np.float32)


class PlayoutTest(unittest.TestCase):
    def test_interpolates_between_frames(self):
        p = Playout(0.1)
        p.push(1000, frame(0), 10.00)
        p.push(1100, frame(100), 10.10)
        # offset = 9.0; кадры лежат на 10.0 и 10.1; воспроизведение отстаёт на 0.1 с
        self.assertAlmostEqual(float(p.sample(10.15)[0][0]), 50, delta=0.01)
        self.assertAlmostEqual(float(p.sample(10.175)[0][0]), 75, delta=0.01)

    def test_bursty_arrival_gives_even_motion(self):
        """Кадры сняты равномерно (каждые 33.3 мс), а пришли пачками по 4: на выходе движение должно быть равномерным."""
        p = Playout(0.15)
        cap = [i * 33.3333 for i in range(90)]
        events = []                                                  # (время, порядок, что)
        for i in range(0, 90, 4):
            group = list(range(i, min(i + 4, 90)))
            arrival = 5.0 + cap[group[-1]] / 1000 + 0.01             # пачка приходит, когда снят её последний кадр
            events.append((arrival, 0, group))
        t = 5.6
        while t < 7.4:
            events.append((t, 1, None))                              # вывод на ленту 60 раз в секунду
            t += 1 / 60
        events.sort(key=lambda e: (e[0], e[1]))

        values = []
        for when, kind, payload in events:
            if kind == 0:
                for k in payload:
                    p.push(int(cap[k]), frame(cap[k] / 1000), when)
            else:
                values.append(float(p.sample(when)[0][0]))
        steps = np.diff(values)
        self.assertTrue((steps > 0).all())                           # всегда вперёд
        self.assertLess(steps.max() - steps.min(), 0.002)            # шаг ровный (без стоячих и скачков)
        self.assertEqual(p.starvation, 0.0)                          # задержки хватало

    def test_without_playout_the_same_bursts_would_be_jerky(self):
        """Для сравнения: вывод «последнего пришедшего кадра» при тех же пачках даёт неровные шаги."""
        latest, values = None, []
        cap = [i * 33.3333 for i in range(90)]
        events = []
        for i in range(0, 90, 4):
            group = list(range(i, min(i + 4, 90)))
            events.append((5.0 + cap[group[-1]] / 1000 + 0.01, 0, group))
        t = 5.6
        while t < 7.4:
            events.append((t, 1, None))
            t += 1 / 60
        events.sort(key=lambda e: (e[0], e[1]))
        for when, kind, payload in events:
            if kind == 0:
                latest = cap[payload[-1]] / 1000
            else:
                values.append(latest)
        steps = np.diff(values)
        self.assertGreater((steps == 0).sum(), 20)                   # много «стоячих» тактов подряд

    def test_holds_last_frame_and_counts_starvation(self):
        p = Playout(0.05)
        p.push(0, frame(1), 1.0)
        p.push(100, frame(2), 1.1)
        for _ in range(200):
            self.assertEqual(float(p.sample(5.0)[0][0]), 2.0)        # новых кадров нет - держим последний
        self.assertGreater(p.starvation, 0.8)

    def test_before_first_frame_returns_first(self):
        p = Playout(0.1)
        p.push(500, frame(7), 3.0)
        self.assertEqual(float(p.sample(3.0)[0][0]), 7.0)

    def test_empty_returns_none(self):
        self.assertIsNone(Playout(0.1).sample(1.0))

    def test_timestamp_wraparound(self):
        p = Playout(0.1)
        p.push(2 ** 32 - 100, frame(0), 10.0)
        p.push(0, frame(100), 10.1)                                  # счётчик ТВ переполнился
        p.push(100, frame(200), 10.2)
        self.assertAlmostEqual(float(p.sample(10.25)[0][0]), 150, delta=1)   # между кадрами 100 и 200
        self.assertAlmostEqual(float(p.sample(10.3)[0][0]), 200, delta=1)

    def test_clock_jump_starts_over(self):
        p = Playout(0.1)
        p.push(1000, frame(1), 10.0)
        p.push(1033, frame(2), 10.033)
        p.push(50, frame(9), 20.0)                                   # ТВ перезагрузился: часы пошли с нуля
        self.assertEqual(float(p.sample(20.2)[0][0]), 9.0)

    def test_reset(self):
        p = Playout(0.1)
        p.push(0, frame(1), 1.0)
        p.reset()
        self.assertIsNone(p.sample(1.0))

    def test_old_frames_are_dropped(self):
        p = Playout(0.1)
        for i in range(600):
            p.push(i * 33, frame(i), 1.0 + i * 0.033)
        self.assertLess(len(p._times), 120)


if __name__ == "__main__":
    unittest.main()
