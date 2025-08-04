import threading

import uvicorn
from fastapi import APIRouter, FastAPI
from settings import settings
from interface import router_capture, router_led


class Interface:
    def __init__(self):
        self.capture = None
        self.led = None

    def start_interface(self):
        interface_router = APIRouter()
        interface_router.include_router(router_capture.router, tags=["Capture"])
        interface_router.include_router(router_led.router, tags=["Led"])

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

    def start(self, capture=None, led=None):
        self.capture = capture
        self.led = led

        trd = threading.Thread(name='Interface thread', target=self.start_interface)
        trd.setDaemon(True)
        trd.start()


interface = Interface()
