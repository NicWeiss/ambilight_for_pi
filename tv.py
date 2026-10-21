import ipaddress
import os
import re
import select
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from settings import settings

BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR / "tv"
STATE_FILE = BASE_DIR / settings.TV_STATE_FILE

# Основной способ: vcap читает V4L2-устройство видео прямо на ТВ и считает цвета сегментов ленты
VCAP_BIN = "/data/local/tmp/vcap"
VCAP_MAX_AGE_S = 3.0
# Запасной способ: штатный screencatch (~1 кадр/с), если vcap не запускается
LEGACY_BIN = "/data/local/tests/vendor/screencatch_p"
LEGACY_SCRIPT = "/data/local/tmp/cap.sh"
LEGACY_W, LEGACY_H = 160, 90
LEGACY_FIFO_COUNT = 5000
LEGACY_MAX_AGE_S = 12.0
LEGACY_RETRY_VCAP_S = 120.0
MAX_BACKOFF = 30.0


def log(msg):
    print("[tv] " + msg, flush=True)


def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except subprocess.TimeoutExpired:
        return 124, ""


def parse_neighbours(text):
    """{ip: (mac, dev)} из вывода `ip -4 neigh show` (без FAILED/INCOMPLETE)."""
    table = {}
    for line in text.splitlines():
        if line.rstrip().endswith(("FAILED", "INCOMPLETE")):
            continue
        m = re.match(r"(\d+\.\d+\.\d+\.\d+)\s+dev\s+(\S+)\s.*lladdr\s+([0-9a-f:]{17})", line, re.IGNORECASE)
        if m:
            table[m.group(1)] = (m.group(3).lower(), m.group(2))
    return table


def neighbours():
    _, out = run_cmd(["ip", "-4", "neigh", "show"], timeout=5)
    return parse_neighbours(out)


def local_hosts():
    _, out = run_cmd(["ip", "-4", "-o", "addr", "show", "scope", "global"], timeout=5)
    hosts = []
    for line in out.splitlines():
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", line)
        if not m:
            continue
        iface = ipaddress.ip_interface(m.group(1))
        net = iface.network
        if net.prefixlen < 24:
            net = ipaddress.ip_network("%s/24" % iface.ip, strict=False)
        hosts += [str(h) for h in net.hosts() if h != iface.ip]
    return hosts


def probe(host):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        s.connect_ex((host, settings.TV_ADB_PORT))
    except OSError:
        pass
    finally:
        s.close()


def tv_candidates(mac, preferred=None):
    """[(ip, dev)] адресов с MAC телевизора; preferred (последний известный) идёт первым."""
    found = [(ip, dev) for ip, (m, dev) in neighbours().items() if m == mac]
    found.sort(key=lambda c: 0 if c[0] == preferred else 1)
    return found


def find_tv_candidates(mac, preferred=None):
    cands = tv_candidates(mac, preferred)
    if cands:
        return cands
    try:
        hint = STATE_FILE.read_text().strip()
    except OSError:
        hint = ""
    if hint:
        probe(hint)
        cands = tv_candidates(mac, hint)
        if cands:
            return cands
    # сканируем подсеть: ответившие хосты (даже закрытым портом) попадают в таблицу соседей
    hosts = local_hosts()
    if hosts:
        with ThreadPoolExecutor(max_workers=64) as pool:
            list(pool.map(probe, hosts))
    return tv_candidates(mac, hint or preferred)


class TvSource(threading.Thread):
    """Картинка с экрана ТВ (видео + интерфейс) по ADB, ~30 кадр/с.

    На ТВ работает vcap: читает V4L2-устройство видео и сам считает средние цвета сегментов ленты,
    по сети идёт ~170 байт на кадр. Работает только пока включён (enable), сам находит ТВ в сети
    по MAC и переподключается. Если vcap не запускается - переходит на штатный screencatch (~1 кадр/с).

    latest() возвращает: ndarray (N, 3) - цвета сегментов (vcap), либо ndarray (H, W, 3) - целый кадр
    (запасной режим)."""

    def __init__(self, segments, edge_x, edge_y):
        super().__init__(daemon=True)
        self.segments = tuple(segments)   # (слева, сверху, справа)
        self.edge_x = edge_x
        self.edge_y = edge_y
        self.mac = settings.TV_MAC.strip().lower()
        self._enabled = threading.Event()
        self._lock = threading.Lock()
        self._frame = None
        self._ts = 0.0
        self._seq = 0
        self._proc = None
        self._serial = None
        self._legacy_until = 0.0
        self._vcap_failures = 0
        self._mode = "vcap"

    @property
    def mode(self):
        return self._mode

    @property
    def seq(self):
        return self._seq

    @property
    def address(self):
        return self._serial.split(":")[0] if self._serial else None

    def max_age(self):
        return LEGACY_MAX_AGE_S if self._mode == "legacy" else VCAP_MAX_AGE_S

    def enable(self, on):
        if on:
            self._enabled.set()
        else:
            self._enabled.clear()

    def latest(self, max_age):
        with self._lock:
            if self._frame is None or time.time() - self._ts > max_age:
                return None
            return self._frame

    def age(self):
        with self._lock:
            return None if self._frame is None else time.time() - self._ts

    def shutdown(self):
        self._enabled.clear()
        self._kill_stream()
        self._cleanup_remote()

    def _store(self, frame):
        with self._lock:
            self._frame = frame
            self._ts = time.time()
            self._seq += 1

    def _adb(self, *args, timeout=10):
        return run_cmd(["adb", "-s", self._serial] + list(args), timeout=timeout)

    def _alive(self):
        if not self._serial:
            return False
        rc, out = self._adb("get-state", timeout=6)
        return rc == 0 and out == "device"

    def _locate(self):
        """Находит ТВ по MAC, подключает по ADB. Перебирает все адреса с его MAC."""
        previous = self.address
        for ip, dev in find_tv_candidates(self.mac, previous):
            serial = "%s:%d" % (ip, settings.TV_ADB_PORT)
            run_cmd(["adb", "connect", serial], timeout=6)
            self._serial = serial
            if self._alive():
                if ip != previous:
                    log("TV found at %s" % ip)
                try:
                    STATE_FILE.write_text(ip)
                except OSError:
                    pass
                return True
            run_cmd(["adb", "disconnect", serial], timeout=5)
            # запись в таблице соседей могла устареть (адрес сменился) - выкидываем и ищем заново
            run_cmd(["ip", "neigh", "del", ip, "dev", dev], timeout=5)
        self._serial = None
        return False

    def _tools_missing(self, mode):
        if mode == "vcap":
            check = "[ -x %s ]" % VCAP_BIN
        else:
            check = "[ -x %s ] && [ -x %s ]" % (LEGACY_BIN, LEGACY_SCRIPT)
        rc, out = self._adb("shell", "%s && echo ok || echo missing" % check)
        return rc == 0 and out.endswith("missing")

    def _push_tools(self, mode):
        log("installing %s capture tools on the TV" % mode)
        if mode == "vcap":
            rc, _ = self._adb("push", str(TOOLS_DIR / "vcap"), VCAP_BIN, timeout=30)
            self._adb("shell", "chmod 755 %s" % VCAP_BIN)
            return rc == 0
        self._adb("shell", "mkdir -p /data/local/tests/vendor")
        rc1, _ = self._adb("push", str(TOOLS_DIR / "screencatch_p"), LEGACY_BIN, timeout=30)
        rc2, _ = self._adb("push", str(TOOLS_DIR / "cap.sh"), LEGACY_SCRIPT, timeout=30)
        self._adb("shell", "chmod 755 %s %s" % (LEGACY_BIN, LEGACY_SCRIPT))
        return rc1 == 0 and rc2 == 0

    def _cleanup_remote(self):
        if self._serial:
            self._adb("shell", "for p in $(ps -A | grep -E '[v]cap|[c]ap\\.sh|[s]creencatch_p' | awk '{print $2}'); "
                               "do kill $p; done", timeout=8)

    def _kill_stream(self):
        p, self._proc = self._proc, None
        if p is not None:
            try:
                p.kill()
                p.wait(timeout=3)
            except Exception:
                pass
            self._cleanup_remote()

    def _read_frames(self, cmd, frame_bytes, decode, first_timeout, frame_timeout):
        """Читает кадры фиксированного размера из stdout команды -> (получены ли кадры, причина конца)."""
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        fd = self._proc.stdout.fileno()
        buf = b""
        got_any = False
        last = time.time()
        while self._enabled.is_set():
            wait = frame_timeout if got_any else first_timeout
            ready, _, _ = select.select([fd], [], [], 1.0)
            if not ready:
                if time.time() - last > wait:
                    log("no frames for %.0fs, restarting stream" % wait)
                    return got_any, "timeout"
                continue
            chunk = os.read(fd, frame_bytes - len(buf))
            if not chunk:
                return got_any, "eof"
            buf += chunk
            if len(buf) == frame_bytes:
                self._store(decode(buf))
                buf = b""
                got_any = True
                last = time.time()
        return got_any, "disabled"

    def _stream(self, mode):
        if mode == "vcap":
            cmd = ["adb", "-s", self._serial, "exec-out", VCAP_BIN,
                   str(settings.TV_CAPTURE_WIDTH), str(settings.TV_CAPTURE_HEIGHT),
                   str(settings.TV_CAPTURE_FPS), "1" if settings.TV_CAPTURE_OSD else "0"] + \
                  [str(n) for n in self.segments] + [str(self.edge_x), str(self.edge_y)]

            def decode(b):
                return np.frombuffer(b, dtype=np.uint8).reshape(-1, 3).astype(np.float32)

            return self._read_frames(cmd, sum(self.segments) * 3, decode, 10.0, 4.0)

        cmd = ["adb", "-s", self._serial, "exec-out", "sh", LEGACY_SCRIPT,
               str(LEGACY_W), str(LEGACY_H), "1", str(LEGACY_FIFO_COUNT)]

        def decode_legacy(b):
            rgba = np.frombuffer(b, dtype=np.uint8).reshape(LEGACY_H, LEGACY_W, 4)
            bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
            return cv2.resize(bgr, (settings.TARGET_FRAME_WIDTH, settings.TARGET_FRAME_HEIGHT))

        return self._read_frames(cmd, LEGACY_W * LEGACY_H * 4, decode_legacy, 40.0, 10.0)

    def run(self):
        backoff = 2.0
        failures = 0
        while True:
            if not self._enabled.is_set():
                self._kill_stream()
                time.sleep(0.5)
                continue
            mode = "legacy" if time.time() < self._legacy_until else "vcap"
            if mode != self._mode:
                log("capture mode: %s" % mode)
                self._mode = mode
            try:
                # связь пропала или стрим несколько раз подряд не дал кадров - ищем ТВ заново
                if failures >= 3 or not self._alive():
                    if not self._locate():
                        time.sleep(backoff)
                        backoff = min(backoff * 2, MAX_BACKOFF)
                        continue
                    failures = 0
                if self._tools_missing(mode) and not self._push_tools(mode):
                    time.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
                backoff = 2.0
                self._cleanup_remote()
                got_any, reason = self._stream(mode)
                if got_any:
                    failures = 0
                    self._vcap_failures = 0
                else:
                    failures += 1
                    if mode == "legacy":
                        # запасной режим тоже не дал кадров - толку от него нет, возвращаемся к vcap
                        self._legacy_until = 0.0
                    # vcap сразу завершился при живой связи - значит, он сам не может работать
                    # (пауза в кадрах, например ТВ в режиме ожидания, vcap переживает сам и не завершается)
                    if mode == "vcap" and reason == "eof" and self._alive():
                        self._vcap_failures += 1
                        if self._vcap_failures >= 3:
                            log("vcap does not start, using the legacy 1 fps capture for a while")
                            self._legacy_until = time.time() + LEGACY_RETRY_VCAP_S
                            self._vcap_failures = 0
            except Exception as e:
                log("error: %r" % (e,))
                failures += 1
            finally:
                self._kill_stream()
            time.sleep(1.0)
