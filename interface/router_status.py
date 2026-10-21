from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def status() -> Any:
    """Какой источник сейчас управляет лентой и в каком состоянии ТВ-источник."""
    from interface import interface

    provider = interface.status_provider
    return {"status": "ok", **(provider() if provider else {})}
