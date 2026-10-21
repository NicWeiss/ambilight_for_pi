
import os
import signal
import threading
from time import sleep, time
import math
import multiprocessing as mp

import numpy as np

from led import WS2812B_Controller
from capture import VideoStream
from ambilight import AmbilightProcessor
from interface import interface
from selector import Selector
from tv import TvSource

from constants import COLORS_COUNT
from settings import settings

# процесс ленты получает объект с открытым SPI - он наследуется через fork и не передаётся через pickle
# (в Python 3.14 по умолчанию forkserver)
mp.set_start_method("fork", force=True)

LED_DATA_BUFFER = mp.Array("i", settings.LED_COUNT * COLORS_COUNT)

NONE = "NONE"


def hdmi_tau():
    if settings.SMOOTHING_TAU_HDMI > 0:
        return settings.SMOOTHING_TAU_HDMI
    # коэффициент на кадр при 30 кадр/с -> постоянная времени
    factor = min(max(settings.AMBILIGHT_SMOOTHING_FACTOR, 0.01), 0.99)
    return -(1 / 30) / math.log(1 - factor)


def make_tv_source(ambilight):
    if not settings.TV_ENABLED:
        print("[main] TV source is disabled (TV_ENABLED=false)", flush=True)
        return None
    if not settings.TV_MAC.strip():
        print("[main] TV source is disabled: TV_MAC is not set", flush=True)
        return None

    left, top, right = ambilight.segment_counts()
    # толщина полосы анализа задана для TARGET-кадра, пересчитываем на размер кадра ТВ
    edge_x = max(1, round(settings.AMBILIGHT_ANALYZE_DEEP * settings.TV_CAPTURE_WIDTH / settings.TARGET_FRAME_WIDTH))
    edge_y = max(1, round(settings.AMBILIGHT_ANALYZE_DEEP * settings.TV_CAPTURE_HEIGHT / settings.TARGET_FRAME_HEIGHT))
    tv = TvSource((left, top, right), edge_x, edge_y)
    tv.start()
    return tv


def main():
    # Поток управления лентой
    led = WS2812B_Controller(settings.LED_COUNT, LED_DATA_BUFFER)
    led.start()

    # Поток видеозахвата (HDMI)
    vs = None
    if settings.HDMI_ENABLED:
        vs = VideoStream()
        vs.start()
    else:
        print("[main] HDMI source is disabled (HDMI_ENABLED=false)", flush=True)

    # Процессор подсветки
    ambilight = AmbilightProcessor()

    # Источник ТВ
    tv = make_tv_source(ambilight)

    if not vs and not tv:
        print("[main] both sources are disabled, the strip will stay dark", flush=True)

    selector = Selector(settings.HDMI_PICTURE_THRESHOLD, settings.HDMI_HOLD_SECONDS)
    state = {"source": None, "hdmi_enabled": vs is not None, "tv_enabled": tv is not None,
             "hdmi_peak": 0, "tv_mode": None, "tv_age": None, "tv_address": None}

    # Интерфейс управления
    interface.start(vs, led, lambda: dict(state))

    stop = threading.Event()
    heartbeat = [time()]

    def watchdog():
        while not stop.wait(5.0):
            if time() - heartbeat[0] > settings.WATCHDOG_SECONDS:
                print("[main] main loop stalled, exiting for restart", flush=True)
                os._exit(3)

    threading.Thread(target=watchdog, daemon=True).start()

    def on_term(*_):
        stop.set()
        try:
            if tv:
                tv.shutdown()
            led.stop()
        finally:
            os._exit(0)

    signal.signal(signal.SIGTERM, on_term)

    tau_hdmi = hdmi_tau()
    period = 1.0 / max(settings.MAIN_LOOP_HZ, 1)
    target = np.zeros((settings.LED_COUNT, COLORS_COUNT), dtype=np.float32)
    seen_hdmi_time = 0.0
    seen_tv_seq = -1
    source = None
    last_t = time()
    last_status = 0.0

    # Цикл вычисления подсветки
    try:
        while True:
            now = time()
            heartbeat[0] = now

            if settings.IS_LED_ENABLED and led.led_process and not led.led_process.is_alive():
                print("[main] led process died, exiting for restart", flush=True)
                os._exit(4)

            frame, frame_time, peak = vs.snapshot() if vs else (None, 0.0, 0)
            wanted = selector.pick(now, peak, frame is not None and now - frame_time < settings.HDMI_STALE_SECONDS)
            if tv:
                tv.enable(wanted == Selector.TV)

            if wanted == Selector.HDMI:
                active = Selector.HDMI
                tau = tau_hdmi
                if frame is not None and frame_time != seen_hdmi_time:
                    seen_hdmi_time = frame_time
                    target = ambilight.segment_colors(frame)
            else:
                tv_data = tv.latest(tv.max_age()) if tv else None
                if tv_data is not None:
                    active = Selector.TV
                    tau = settings.SMOOTHING_TAU_TV_SLOW if tv.mode == "legacy" else settings.SMOOTHING_TAU_TV
                    if tv.seq != seen_tv_seq:
                        seen_tv_seq = tv.seq
                        # vcap отдаёт готовые цвета сегментов (2D), запасной режим - целый кадр (3D)
                        target = (ambilight.from_segments(tv_data) if tv_data.ndim == 2
                                  else ambilight.segment_colors(tv_data))
                else:
                    active = NONE
                    tau = settings.SMOOTHING_TAU_IDLE
                    target = np.zeros_like(target)

            if active != source:
                print("[main] source: %s -> %s" % (source, active), flush=True)
                source = active

            led_colors = ambilight.smooth(target, now - last_t, tau)
            last_t = now

            # Порядок байт в буфере - BGR, как его читает led.set_cv_array
            with LED_DATA_BUFFER.get_lock():
                LED_DATA_BUFFER[:] = led_colors.reshape(-1).tolist()

            state.update(
                source=source, hdmi_peak=peak,
                tv_mode=tv.mode if tv else None,
                tv_age=None if not tv or tv.age() is None else round(tv.age(), 2),
                tv_address=tv.address if tv else None,
            )
            if now - last_status > 60:
                last_status = now
                print("[main] status: %s" % state, flush=True)

            spare = period - (time() - now)
            if spare > 0:
                sleep(spare)

    except KeyboardInterrupt:
        if vs:
            vs.release()
        if tv:
            tv.shutdown()
        print("\nПрограмма завершена")


if __name__ == "__main__":
    main()
