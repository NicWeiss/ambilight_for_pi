from typing import Any

from fastapi import APIRouter
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
