from typing import Any

from fastapi import APIRouter
from interface import schemas

router = APIRouter()


@router.post("/capture/set/saturation")
def set_saturation(
    params_in: schemas.SetScheme
) -> Any:
    from interface import interface
    interface.capture.set_saturation(params_in.value)

    return {"status": "ok"}

@router.post("/capture/set/contrast")
def set_contrast(
    params_in: schemas.SetScheme
) -> Any:
    from interface import interface
    interface.capture.set_contrast(params_in.value)

    return {"status": "ok"}


@router.post("/capture/set/brightness")
def set_brightness(
    params_in: schemas.SetScheme
) -> Any:
    from interface import interface
    interface.capture.set_brightness(params_in.value)

    return {"status": "ok"}
