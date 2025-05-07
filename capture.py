from threading import Thread
import cv2

from settings import settings


class VideoStream:
    def __init__(self):
        self.cap = cv2.VideoCapture(settings.CAPTURE_SOURCE)
        self.cap.set(cv2.CAP_PROP_SATURATION, settings.CAPTURE_SATURATION)
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, settings.CAPTURE_BRIGHTNESS)
        self.cap.set(cv2.CAP_PROP_CONTRAST, settings.CAPTURE_CONTRAST)

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
            self.grabbed, frame = self.cap.read()
            self.frame = cv2.resize(frame, (settings.TARGET_FRAME_WIDTH, settings.TARGET_FRAME_HEIGHT))

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True

    def release(self):
        self.cap.release()
