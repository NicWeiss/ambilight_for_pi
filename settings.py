
from typing import Any, Dict,  Optional

from pydantic import  validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        case_sensitive = True

    CAPTURE_SOURCE: int = 0
    CAPTURE_SATURATION: int = 100
    CAPTURE_BRIGHTNESS: int = 60
    CAPTURE_CONTRAST: float = 0.6

    CAPTURE_FRAME_WIDTH: int = 640
    CAPTURE_FRAME_HEIGHT: int = 480
    CAPTURE_FPS: int = 30

    TARGET_FRAME_WIDTH: int = 320
    TARGET_FRAME_HEIGHT: int = 240

    LEDS_LEFT: int = 20
    LEDS_TOP: int = 38
    LEDS_RIGHT: int = 20
    LEDS_BOTTOM: int = 0

    LED_COUNT: int = 0

    LEDS_THICKNESS: int = 1

    AMBILIGHT_SMOOTHING_FACTOR: float = 0.3

    SPI_BUS: int = 1
    SPI_CHANNEL: int = 0
    SPI_SPEED: int = 3_200_000
    SPI_MODE: bytes = 0b00

    @validator("LED_COUNT", pre=True)
    def assemble_led_count(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        return values.get("LEDS_LEFT") + values.get("LEDS_TOP") + values.get("LEDS_RIGHT")+ values.get("LEDS_BOTTOM")


settings = Settings()
