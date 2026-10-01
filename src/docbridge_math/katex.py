"""Offline KaTeX PNG rendering in an owned, persistent headless browser."""
from __future__ import annotations

import atexit
import base64
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, ProxyHandler, build_opener

from .shared import FormulaError, FormulaImage, MAX_SOURCE

_lock = threading.RLock()
_session = None


def vendor_dir():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return root / 'tools' / 'vendor' / 'katex'


def browser_paths():
    configured = os.environ.get('DOCBRIDGE_BROWSER') or os.environ.get('MD2DOCX_CHROME')
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file():
            raise FormulaError('指定的公式渲染浏览器不存在：' + str(path))
        return [str(path)]
    candidates = [
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe'),
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    ]
    found = [candidate for candidate in candidates if Path(candidate).is_file()]
    for name in ('msedge', 'google-chrome', 'chromium', 'chromium-browser'):
        if path := shutil.which(name):
            found.append(path)
    if found:
        return list(dict.fromkeys(found))
    raise FormulaError('KaTeX 图片渲染需要本机 Edge 或 Chrome，可用 DOCBRIDGE_BROWSER 指定路径。')


def browser_path():
    return browser_paths()[0]


class _AssetHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header('Content-Security-Policy',
            "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; connect-src 'none'; img-src 'none'")
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


class _BrowserSession:
    def __init__(self, executable=None):
        self.process = self.socket = self.server = self.thread = self.profile = None
        self.serial = 0
        try:
            executable = executable or browser_path()
            assets = vendor_dir()
            for name in ('katex.min.js', 'katex.min.css', 'render.html', 'render.js',
                         'fonts/KaTeX_Main-Regular.woff2'):
                if not (assets / name).is_file():
                    raise FormulaError('缺少打包的 KaTeX 资源：' + name)
            self.server = ThreadingHTTPServer(('127.0.0.1', 0),
                lambda *a, **kw: _AssetHandler(*a, directory=str(assets), **kw))
            self.server.daemon_threads = True
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.profile = Path(tempfile.mkdtemp(prefix='docbridge-katex-'))
            command = [executable, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                '--no-first-run', '--no-default-browser-check', '--disable-extensions',
                '--disable-background-networking', '--disable-component-update',
                '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
                '--disable-sync', '--metrics-recording-only', '--remote-debugging-address=127.0.0.1',
                '--remote-debugging-port=0', '--no-proxy-server',
                '--user-data-dir=' + str(self.profile), 'about:blank']
            self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            deadline = time.monotonic() + 20
            active_port = self.profile / 'DevToolsActivePort'
            port = None
            while port is None:
                if self.process.poll() is not None or time.monotonic() > deadline:
                    raise FormulaError('公式渲染浏览器启动失败。')
                try:
                    port = int(active_port.read_text().splitlines()[0])
                except (OSError, IndexError, ValueError):
                    time.sleep(.03)
            local = build_opener(ProxyHandler({}))
            with local.open(Request(f'http://127.0.0.1:{port}/json/new?about:blank', method='PUT'), timeout=5) as response:
                target = json.load(response)
            import websocket
            self.socket = websocket.create_connection(target['webSocketDebuggerUrl'],
                timeout=20, suppress_origin=True, http_proxy_host=None,
                http_no_proxy=['127.0.0.1', 'localhost'])
            self.request('Emulation.setDeviceMetricsOverride',
                {'width': 1200, 'height': 1000, 'deviceScaleFactor': 3, 'mobile': False})
            self.request('Page.navigate', {'url': f'http://127.0.0.1:{self.server.server_port}/render.html'})
            while not self.evaluate('Boolean(window.docbridgeKaTeXReady)'):
                if time.monotonic() > deadline:
                    raise FormulaError('KaTeX 离线资源加载超时。')
                time.sleep(.03)
        except Exception:
            self.close()
            raise

    def request(self, method, params=None):
        self.serial += 1
        serial = self.serial
        self.socket.send(json.dumps({'id': serial, 'method': method, 'params': params or {}}))
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            message = json.loads(self.socket.recv())
            if message.get('id') == serial:
                if 'error' in message:
                    raise FormulaError('浏览器渲染失败：' + str(message['error'].get('message', '')))
                return message.get('result', {})
        raise FormulaError('公式渲染超时。')

    def evaluate(self, expression):
        result = self.request('Runtime.evaluate',
            {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
        if 'exceptionDetails' in result:
            details = result['exceptionDetails']
            text = details.get('exception', {}).get('description') or details.get('text', '')
            raise FormulaError('KaTeX 渲染失败：' + text.split('\n')[0])
        return result.get('result', {}).get('value')

    def render(self, source, display, size_pt):
        args = json.dumps([source, bool(display), float(size_pt) * 96 / 72], ensure_ascii=True)
        bounds = self.evaluate('window.renderFormula(...' + args + ')')
        width, height = bounds['width'], bounds['height']
        if (not all(math.isfinite(v) and v > 0 for v in (width, height))
                or width > 8000 or height > 4000 or width * height > 2_000_000):
            raise FormulaError('公式图片尺寸过大。')
        result = self.request('Page.captureScreenshot', {'format': 'png', 'fromSurface': True,
            'captureBeyondViewport': True, 'clip': {key: bounds[key] for key in ('x', 'y', 'width', 'height')} | {'scale': 1}})
        return FormulaImage(base64.b64decode(result['data']), width * 72 / 96,
            height * 72 / 96, max(0., bounds['y'] + height - bounds['baseline']) * 72 / 96)

    def close(self):
        if self.socket:
            try:
                self.socket.send(json.dumps({'id': -1, 'method': 'Browser.close'}))
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
        if self.process:
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            self.process = None
        if self.server:
            if self.thread and self.thread.is_alive():
                self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        if self.profile:
            path = self.profile.resolve()
            if path.parent == Path(tempfile.gettempdir()).resolve() and path.name.startswith('docbridge-katex-'):
                for attempt in range(5):
                    try:
                        shutil.rmtree(path)
                        break
                    except FileNotFoundError:
                        break
                    except OSError:
                        time.sleep(.1 * (attempt + 1))
            self.profile = None


def close_renderer():
    global _session
    with _lock:
        if _session:
            _session.close()
            _session = None


def start_renderer():
    """Try installed browsers in order; an explicit browser remains authoritative."""
    errors = []
    for executable in browser_paths():
        try:
            return _BrowserSession(executable)
        except Exception as exc:
            errors.append(f'{Path(executable).name}: {exc}')
    raise FormulaError('KaTeX 渲染浏览器启动失败：' + '；'.join(errors))


@lru_cache(maxsize=128)
def render_png(source: str, display=False, size_pt=12) -> FormulaImage:
    global _session
    if not source.strip() or len(source) > MAX_SOURCE:
        raise FormulaError('公式为空或超过 16000 字符。')
    if not math.isfinite(float(size_pt)) or not 1 <= float(size_pt) <= 200:
        raise FormulaError('公式字号必须在 1–200 pt 之间。')
    try:
        with _lock:
            if _session is None or _session.process.poll() is not None:
                close_renderer()
                _session = start_renderer()
            return _session.render(source, display, size_pt)
    except FormulaError:
        raise
    except Exception as exc:
        close_renderer()
        raise FormulaError(f'KaTeX 图片渲染失败：{exc}') from exc


atexit.register(close_renderer)
