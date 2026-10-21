class Selector:
    """Выбор источника: HDMI в приоритете, пока на нём есть картинка.

    Тёмная сцена и отсутствие сигнала на карте захвата выглядят одинаково (кадр абсолютно чёрный),
    поэтому на ТВ переключаемся только после hold секунд сплошной черноты. Обратно на HDMI - сразу.
    """

    HDMI = "HDMI"
    TV = "TV"

    def __init__(self, threshold, hold):
        self.threshold = threshold
        self.hold = hold
        self.last_picture = float("-inf")

    def pick(self, now, hdmi_peak, hdmi_fresh):
        if hdmi_fresh and hdmi_peak > self.threshold:
            self.last_picture = now
        return self.HDMI if now - self.last_picture < self.hold else self.TV
