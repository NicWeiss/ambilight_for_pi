from threading import Thread
import cv2

from settings import settings


class VideoStream:
    def __init__(self):
        self.cap = cv2.VideoCapture(settings.CAPTURE_SOURCE)
        self.set_saturation(settings.CAPTURE_SATURATION)
        self.set_brightness(settings.CAPTURE_BRIGHTNESS)
        self.set_contrast(settings.CAPTURE_CONTRAST)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.CAPTURE_FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.CAPTURE_FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, settings.CAPTURE_FPS)

        self.grabbed, frame = self.cap.read()
        self.frame = cv2.resize(frame, (settings.TARGET_FRAME_WIDTH, settings.TARGET_FRAME_HEIGHT))
        self.stopped = False

    def start(self):
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        while not self.stopped:
            try:
                self.grabbed, frame = self.cap.read()
                self.frame = cv2.resize(frame, (settings.TARGET_FRAME_WIDTH, settings.TARGET_FRAME_HEIGHT))
            except Exception as _:
                pass

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True

    def release(self):
        self.cap.release()

    def set_saturation(self, value: int):
        self.cap.set(cv2.CAP_PROP_SATURATION, value)

    def set_contrast(self, value: int):
        self.cap.set(cv2.CAP_PROP_CONTRAST, value)

    def set_brightness(self, value: int):
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, value)
