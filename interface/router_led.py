from typing import Any

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from settings import settings

router = APIRouter()


@router.post("/led/disable")
def turn_off() -> Any:
    from interface import interface
    interface.led.stop()

    return {"status": "ok"}


@router.post("/led/enable")
def turn_on() -> Any:
    from interface import interface
    interface.led.start()

    return {"status": "ok"}


@router.get("/led/status")
def status() -> Any:
    from interface import interface
    status = interface.led.status()

    return {"status": "ok", "is_enabled": status}


class GradeScheme(BaseModel):
    brightness: Optional[float] = None
    saturation: Optional[float] = None
    white_reduction: Optional[float] = None
    white_power: Optional[float] = None


def _grade():
    return {
        "brightness": settings.LED_BRIGHTNESS,
        "saturation": settings.LED_SATURATION,
        "white_reduction": settings.LED_WHITE_REDUCTION,
        "white_power": settings.LED_WHITE_POWER,
    }


@router.get("/led/grade")
def get_grade() -> Any:
    """Текущая цветокоррекция ленты."""
    return {"status": "ok", **_grade()}


@router.post("/led/grade")
def set_grade(params_in: GradeScheme) -> Any:
    """Подбор цветокоррекции на лету (действует сразу, до перезапуска). Постоянные значения - в .env (LED_*)."""
    limits = {"brightness": (0.0, 3.0), "saturation": (0.0, 4.0), "white_reduction": (0.0, 1.0), "white_power": (0.2, 8.0)}
    names = {"brightness": "LED_BRIGHTNESS", "saturation": "LED_SATURATION",
             "white_reduction": "LED_WHITE_REDUCTION", "white_power": "LED_WHITE_POWER"}
    for key, (lo, hi) in limits.items():
        value = getattr(params_in, key)
        if value is None:
            continue
        if not lo <= value <= hi:
            raise HTTPException(status_code=422, detail="%s must be between %s and %s" % (key, lo, hi))
        setattr(settings, names[key], value)
    return {"status": "ok", **_grade()}
