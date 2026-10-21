from typing import Any

from fastapi import APIRouter, HTTPException
from interface import schemas
from settings import settings

router = APIRouter()


def capture():
    from interface import interface
    if interface.capture is None:
        raise HTTPException(status_code=409, detail="HDMI source is disabled (HDMI_ENABLED=false)")
    return interface.capture


@router.post("/capture/set/saturation")
def set_saturation(
    params_in: schemas.SetScheme
) -> Any:
    capture().set_saturation(params_in.value)

    return {"status": "ok"}

@router.post("/capture/set/contrast")
def set_contrast(
    params_in: schemas.SetScheme
) -> Any:
    capture().set_contrast(params_in.value)

    return {"status": "ok"}


@router.post("/capture/set/brightness")
def set_brightness(
    params_in: schemas.SetScheme
) -> Any:
    capture().set_brightness(params_in.value)

    return {"status": "ok"}
