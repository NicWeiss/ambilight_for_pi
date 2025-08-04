
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
    CAPTURE_BRIGHTNESS: int = 60
    CAPTURE_CONTRAST: float = 1

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

    AMBILIGHT_SMOOTHING_FACTOR: float = 0.3
    AMBILIGHT_ANALYZE_DEEP: int = 20

    COLOR_SHIFT_BLUE: int = 0
    COLOR_SHIFT_GREEN: int = 0
    COLOR_SHIFT_RED: int = 0

    SPI_BUS: int = 1
    SPI_CHANNEL: int = 0
    SPI_SPEED: int = 3_400_000
    SPI_MODE: int = 0b00

    @validator("LED_COUNT", pre=True)
    def assemble_led_count(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        return values.get("LEDS_LEFT") + values.get("LEDS_TOP") + values.get("LEDS_RIGHT")+ values.get("LEDS_BOTTOM")


settings = Settings()
