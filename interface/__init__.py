import threading

import uvicorn
from fastapi import APIRouter, FastAPI
from settings import settings
from interface import router


class Interface:
    def __init__(self):
        self.capture = None

    def start_interface(self):
        interface_router = APIRouter()
        interface_router.include_router(router.router, tags=["Capture"])

        app = FastAPI()
        app.include_router(interface_router, prefix="")

        uvicorn.run(
            app,
            host=settings.INTERFACE_HOST,
            port=settings.INTERFACE_PORT,
            log_config=None,
            proxy_headers=True,
            forwarded_allow_ips="*"
        )

    def start(self, capture=None):
        self.capture = capture
        trd = threading.Thread(name='Interface thread', target=self.start_interface)
        trd.setDaemon(True)
        trd.start()


interface = Interface()
