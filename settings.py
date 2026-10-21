
from typing import Any, Dict,  Optional

from pydantic import  validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        case_sensitive = True

    INTERFACE_HOST: str = "0.0.0.0"
    INTERFACE_PORT: int = 8000

    CAPTURE_SOURCE: int = 0
    CAPTURE_SATURATION: int = 100
    CAPTURE_BRIGHTNESS: int = 40
    CAPTURE_CONTRAST: float = 40

    CAPTURE_FRAME_WIDTH: int = 640
    CAPTURE_FRAME_HEIGHT: int = 480
    CAPTURE_FPS: int = 30

    TARGET_FRAME_WIDTH: int = 160
    TARGET_FRAME_HEIGHT: int = 120

    LEDS_LEFT: int = 20
    LEDS_TOP: int = 38
    LEDS_RIGHT: int = 20
    LEDS_BOTTOM: int = 0

    LED_COUNT: int = 0

    LEDS_THICKNESS: int = 1
    IS_LED_ENABLED: Optional[bool] = True

    AMBILIGHT_SMOOTHING_FACTOR: float = 0.3
    AMBILIGHT_ANALYZE_DEEP: int = 20

    # Обработка цвета перед выводом на ленту (для любого источника)
    LED_BRIGHTNESS: float = 1.2         # общая яркость (1.0 - как есть, выше - ярче; оттенок при упоре в 255 сохраняется)
    LED_SATURATION: float = 1.5         # усиление насыщенности, 1.0 - без изменений
    LED_WHITE_REDUCTION: float = 0.8    # насколько приглушать белый и бледные цвета (0 - не трогать, 1 - гасить полностью)
    LED_WHITE_POWER: float = 2.0        # чем больше, тем ближе к чистому белому ограничено приглушение (1 - плавно на всю бледность)

    COLOR_SHIFT_BLUE: int = 0
    COLOR_SHIFT_GREEN: int = 0
    COLOR_SHIFT_RED: int = 0

    SPI_BUS: int = 1
    SPI_CHANNEL: int = 0
    SPI_SPEED: int = 3_200_000
    SPI_MODE: int = 0b00

    # Включение источников. Выключенный источник не открывается и не опрашивается.
    # HDMI - карта захвата, ТВ - картинка с самого телевизора (для неё ещё нужен TV_MAC).
    HDMI_ENABLED: bool = True
    TV_ENABLED: bool = True

    # Выбор источника: HDMI (карта захвата) всегда в приоритете, пока на нём есть картинка.
    # Если HDMI чёрный дольше HDMI_HOLD_SECONDS - считаем, что сигнала нет, и берём картинку с ТВ.
    # Сигналы никогда не смешиваются.
    HDMI_PICTURE_THRESHOLD: int = 25    # максимум по каналам (0..255), выше которого кадр - "есть картинка"; должен быть заметно выше пика пустого кадра (зависит от CAPTURE_BRIGHTNESS)
    HDMI_HOLD_SECONDS: float = 8.0
    HDMI_STALE_SECONDS: float = 2.0     # если карта захвата не присылает кадры - HDMI считается отсутствующим

    # Картинка с телевизора по ADB (см. tv/README.md). ТВ ищется в сети по MAC, а не по IP.
    TV_MAC: str = ""                    # MAC Wi-Fi телевизора; пусто - источник ТВ выключен
    TV_ADB_PORT: int = 5555
    TV_CAPTURE_WIDTH: int = 320         # меньше 320x180 драйвер отдаёт кадр с чёрными полями
    TV_CAPTURE_HEIGHT: int = 180
    TV_CAPTURE_FPS: int = 60
    TV_CAPTURE_OSD: bool = True         # True - видео + интерфейс ТВ, False - только видео
    # Защищённый вход (HDCP, например Steam Deck через док) ТВ отдаёт в захват как ровный серый кадр.
    # Такой кадр считается "нет изображения": в ленту ничего не отдаётся, и она плавно гаснет.
    TV_FLAT_GRAY_AS_BLANK: bool = True
    TV_FLAT_TOLERANCE: int = 2          # максимальный разброс значений в кадре и между каналами
    TV_FLAT_MIN: int = 40               # серый ниже этого уровня - обычный чёрный экран, ниже сам погаснет
    TV_FLAT_MAX: int = 215              # серый выше этого уровня - настоящий белый экран, светим белым
    TV_FLAT_FRAMES: int = 3             # сколько плоских кадров подряд нужно, чтобы признать "нет изображения"
    # Сеть доставляет кадры с ТВ пачками, поэтому они воспроизводятся по времени съёмки с постоянной задержкой
    # и линейной интерполяцией. Больше задержка - плавнее при плохом Wi-Fi, но запаздывает подсветка.
    TV_PLAYOUT_DELAY: float = 0.07      # для UDP-потока
    TV_PLAYOUT_DELAY_ADB: float = 0.15  # для запасного потока через ADB (он приходит заметно более пачками)
    # Как кадры идут с ТВ: "udp" - программа на ТВ шлёт их на Pi напрямую (ADB только запускает её), быстрее и ровнее;
    # "adb" - вся передача идёт через ADB. Если UDP не проходит, автоматически используется ADB.
    TV_TRANSPORT: str = "udp"
    TV_STATE_FILE: str = ".tv_last_ip"  # последний найденный адрес ТВ (подсказка для быстрого поиска)

    # Сглаживание: постоянная времени экспоненты, секунды (чем больше, тем плавнее).
    # 0 для HDMI - вычислить из AMBILIGHT_SMOOTHING_FACTOR (как коэффициент на кадр при 30 кадр/с).
    SMOOTHING_TAU_HDMI: float = 0.0
    SMOOTHING_TAU_TV: float = 0.03      # небольшое: кадры уже интерполируются (TV_PLAYOUT_DELAY)
    SMOOTHING_TAU_TV_SLOW: float = 0.6  # запасной режим ТВ, ~1 кадр/с
    SMOOTHING_TAU_IDLE: float = 0.8     # когда источников нет - плавно гасим ленту

    MAIN_LOOP_HZ: int = 60
    LED_REFRESH_HZ: int = 20            # минимальная частота: лента перерисовывается при каждом новом кадре главного цикла, а без него - с этой частотой
    WATCHDOG_SECONDS: float = 30.0      # если главный цикл завис - процесс завершается и перезапускается systemd

    @validator("LED_COUNT", pre=True)
    def assemble_led_count(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        return values.get("LEDS_LEFT") + values.get("LEDS_TOP") + values.get("LEDS_RIGHT")+ values.get("LEDS_BOTTOM")


settings = Settings()
