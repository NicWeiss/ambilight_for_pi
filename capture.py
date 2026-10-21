from threading import Thread
from time import sleep, time
import cv2
import threading

from settings import settings


class VideoStream:
    """Карта захвата (HDMI). Сама переоткрывает устройство, если оно пропало."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cap = None
        self.saturation = settings.CAPTURE_SATURATION
        self.brightness = settings.CAPTURE_BRIGHTNESS
        self.contrast = settings.CAPTURE_CONTRAST

        self.frame = None
        self.frame_time = 0.0
        self.peak = 0
        self.stopped = False
        self._open()

    def _open(self):
        cap = cv2.VideoCapture(settings.CAPTURE_SOURCE)
        if not cap.isOpened():
            cap.release()
            return False

        cap.set(cv2.CAP_PROP_SATURATION, self.saturation)
        cap.set(cv2.CAP_PROP_BRIGHTNESS, self.brightness)
        cap.set(cv2.CAP_PROP_CONTRAST, self.contrast)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAPTURE_FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAPTURE_FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, settings.CAPTURE_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap = cap
        return True

    def start(self):
        Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        failures = 0
        while not self.stopped:
            if self.cap is None:
                if not self._open():
                    print("[capture] device is not available, retrying", flush=True)
                    sleep(2)
                    continue

            grabbed, frame = self.cap.read()
            if not grabbed or frame is None:
                failures += 1
                if failures >= 30:
                    print("[capture] reading failed, reopening", flush=True)
                    self.cap.release()
                    self.cap = None
                    failures = 0
                    sleep(1)
                else:
                    sleep(0.05)
                continue

            failures = 0
            small = cv2.resize(frame, (settings.TARGET_FRAME_WIDTH, settings.TARGET_FRAME_HEIGHT))
            with self.lock:
                self.frame = small
                self.frame_time = time()
                self.peak = int(small.max())

    def read(self):
        if self.frame is not None:
            with self.lock:
                return self.frame.copy()

    def snapshot(self):
        """(кадр, время кадра, максимум яркости по каналам). Кадр не копируется - его никто не меняет."""
        with self.lock:
            return self.frame, self.frame_time, self.peak

    def stop(self):
        self.stopped = True

    def release(self):
        if self.cap is not None:
            self.cap.release()

    def set_saturation(self, value: int):
        self.saturation = value
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_SATURATION, value)

    def set_contrast(self, value: int):
        self.contrast = value
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_CONTRAST, value)

    def set_brightness(self, value: int):
        self.brightness = value
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, value)
