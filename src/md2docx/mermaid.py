"""Mermaid 代码块 → PNG 图片。

主渲染路径不依赖任何外部服务：用系统里已装的 Chrome/Edge 无头模式，
跑本地 vendor 的 mermaid.js 内核，两趟出图——
第一趟 `--dump-dom` 拿到图形的真实尺寸，第二趟按目标像素截图，
这样插进 Word 的图片既清晰、又不会有白边。

可选后端：mermaid-cli（mmdc，本地已装则优先）与 kroki 在线服务。
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import resources

VENDOR_DIR = resources.vendor_dir()
MERMAID_JS = resources.mermaid_js_path()

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


@dataclass
class RenderResult:
    path: str
    width_px: int          # 图形的自然宽度（CSS px，96dpi 基准）
    height_px: int
    renderer: str
    svg_path: str | None = None

    @property
    def width_inch(self) -> float:
        return self.width_px / 96.0

    @property
    def height_inch(self) -> float:
        return self.height_px / 96.0


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102
        pass


class _LocalServer:
    """给无头浏览器提供一个 http 源，绕开 file:// 的脚本加载限制。"""

    def __init__(self, directory: str):
        self.directory = directory
        self.httpd = None
        self.thread = None
        self.port = None

    def start(self):
        if self.httpd:
            return
        handler = lambda *a, **kw: _QuietHandler(*a, directory=self.directory, **kw)  # noqa: E731
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        for _ in range(50):
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", self.port)) == 0:
                    break
            time.sleep(0.05)

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


PAGE_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>md2docx mermaid</title>
<style>
  html,body {{ margin:0; padding:0; background:{background}; }}
  #c {{ display:inline-block; background:{background}; }}
  #c svg {{ display:block; max-width:none !important; height:auto; }}
  textarea {{ position:absolute; left:-99999px; width:1px; height:1px; }}
</style>
</head><body>
<div id="c"></div>
<div id="__size" hidden></div>
<textarea id="__svg"></textarea>
<script src="mermaid.min.js"></script>
<script id="__src" type="text/plain">{code_b64}</script>
<script>
const CFG = {cfg_json};
(async () => {{
  const sizeEl = document.getElementById('__size');
  try {{
    const raw = document.getElementById('__src').textContent.trim();
    const bytes = Uint8Array.from(atob(raw), c => c.charCodeAt(0));
    const code = new TextDecoder('utf-8').decode(bytes);
    await mermaid.initialize({{
      startOnLoad: false,
      securityLevel: 'loose',
      theme: CFG.theme,
      fontFamily: CFG.font_family,
      themeVariables: Object.assign({{ fontSize: CFG.font_size + 'px' }}, CFG.theme_variables || {{}}),
      flowchart: {{ useMaxWidth: false, htmlLabels: true }},
      sequence: {{ useMaxWidth: false }},
      gantt: {{ useMaxWidth: false }},
      class: {{ useMaxWidth: false }},
      state: {{ useMaxWidth: false }},
      er: {{ useMaxWidth: false }}
    }});
    const {{ svg }} = await mermaid.render('md2docx-graph', code);
    document.getElementById('c').innerHTML = svg;
    document.getElementById('__svg').textContent = svg;
    const el = document.querySelector('#c svg');
    let w = 0, h = 0;
    if (el.viewBox && el.viewBox.baseVal && el.viewBox.baseVal.width) {{
      w = el.viewBox.baseVal.width; h = el.viewBox.baseVal.height;
    }} else {{
      const r = el.getBoundingClientRect(); w = r.width; h = r.height;
    }}
    if (CFG.target_width && CFG.target_height) {{
      el.setAttribute('width', CFG.target_width);
      el.setAttribute('height', CFG.target_height);
      el.style.maxWidth = 'none';
    }}
    sizeEl.setAttribute('data-ok', '1');
    sizeEl.setAttribute('data-w', String(Math.ceil(w)));
    sizeEl.setAttribute('data-h', String(Math.ceil(h)));
    if (!CFG.keep_dom) {{
      document.getElementById('c').innerHTML = '';
    }}
    document.title = 'md2docx-done';
  }} catch (err) {{
    sizeEl.setAttribute('data-err', String((err && err.message) || err));
    document.title = 'md2docx-error';
  }}
}})();
</script>
</body></html>
"""


class MermaidRenderer:
    def __init__(self, cfg: dict, cache_dir: str, log=print):
        self.cfg = cfg
        self.cache_dir = cache_dir          # 只放渲染产物（png / svg）
        self.log = log
        # 页面、内核副本、浏览器 profile 都放系统临时目录：这些东西体积大、
        # 数量多（profile 有上百个小文件），不该污染输出目录
        self.work_dir = os.path.join(tempfile.gettempdir(), "md2docx-mermaid")
        self._server: _LocalServer | None = None
        self._browser: str | None = None
        self._resolved = False

    # ---------------------------------------------------------------- 探测
    def browser_path(self) -> str | None:
        if self._resolved:
            return self._browser
        self._resolved = True
        configured = (self.cfg.get("chrome_path") or "").strip()
        if configured and os.path.exists(configured):
            self._browser = configured
            return self._browser
        env = os.environ.get("MD2DOCX_CHROME")
        if env and os.path.exists(env):
            self._browser = env
            return self._browser
        for candidate in BROWSER_CANDIDATES:
            if candidate and os.path.exists(candidate):
                self._browser = candidate
                return self._browser
        found = shutil.which("google-chrome") or shutil.which("chromium")
        self._browser = found
        return self._browser

    def mmdc_path(self) -> str | None:
        configured = (self.cfg.get("mmdc_path") or "").strip()
        if configured and os.path.exists(configured):
            return configured
        found = shutil.which("mmdc")
        if found:
            return found
        cand = os.path.expandvars(r"%APPDATA%\npm\mmdc.cmd")
        return cand if os.path.exists(cand) else None

    def available_backend(self) -> str | None:
        mode = str(self.cfg.get("renderer", "auto")).lower()
        if mode == "off":
            return None
        if mode == "mmdc":
            return "mmdc" if self.mmdc_path() else None
        if mode == "kroki":
            return "kroki"
        if mode == "chrome":
            return "chrome" if (self.browser_path() and os.path.exists(MERMAID_JS)) else None
        if self.mmdc_path():
            return "mmdc"
        if self.browser_path() and os.path.exists(MERMAID_JS):
            return "chrome"
        return "kroki"

    # ---------------------------------------------------------------- 对外
    def render(self, code: str, out_png: str) -> RenderResult | None:
        backend = self.available_backend()
        if backend is None:
            return None
        os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
        try:
            if backend == "mmdc":
                return self._render_mmdc(code, out_png)
            if backend == "chrome":
                return self._render_chrome(code, out_png)
            return self._render_kroki(code, out_png)
        except Exception as exc:  # noqa: BLE001
            self.log(f"    ! mermaid 渲染失败（{backend}）：{exc}")
            return None

    # ------------------------------------------------------------- chrome
    def _ensure_server(self) -> _LocalServer:
        os.makedirs(self.work_dir, exist_ok=True)
        target_js = os.path.join(self.work_dir, "mermaid.min.js")
        if not os.path.exists(target_js) or os.path.getsize(target_js) != os.path.getsize(MERMAID_JS):
            shutil.copyfile(MERMAID_JS, target_js)
        if self._server is None:
            self._server = _LocalServer(self.work_dir)
            self._server.start()
        return self._server

    def _write_page(self, name: str, code: str, extra: dict) -> str:
        cfg = {
            "theme": self.cfg.get("theme", "default"),
            "font_family": self.cfg.get("font_family"),
            "font_size": self.cfg.get("font_size", 14),
            "theme_variables": self.cfg.get("theme_variables") or {},
            "background": self.cfg.get("background", "#FFFFFF"),
        }
        cfg.update(extra)
        payload = PAGE_TEMPLATE.format(
            background=cfg["background"],
            code_b64=base64.b64encode(code.encode("utf-8")).decode("ascii"),
            cfg_json=json.dumps(cfg),
        )
        path = os.path.join(self.work_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(payload)
        return path

    def _chrome_run(self, url: str, args: list[str], timeout: int = 120):
        headless = ["--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", "--disable-extensions",
                    "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--disable-lcd-text",
                    f"--user-data-dir={os.path.join(self.work_dir, '_chrome_profile')}"]
        cmd = [self.browser_path()] + headless + args + [url]
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0 and "headless=new" in cmd:
            cmd = [c for c in cmd if c != "--headless=new"]
            cmd.insert(1, "--headless")
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                                  encoding="utf-8", errors="replace")
        return proc

    def _render_chrome(self, code: str, out_png: str) -> RenderResult | None:
        server = self._ensure_server()
        scale = max(1, int(self.cfg.get("scale", 3)))

        # 第一趟：拿真实尺寸
        page1 = self._write_page("page_measure.html", code, {"keep_dom": False})
        proc = self._chrome_run(f"{server.url}/{os.path.basename(page1)}",
                               ["--virtual-time-budget=20000", "--dump-dom"])
        dom = proc.stdout or ""
        marker = 'id="__size"'
        if marker not in dom:
            raise RuntimeError("无头浏览器没有回传渲染结果（--dump-dom 为空）")
        import re
        ok = re.search(r'id="__size"[^>]*data-ok="1"[^>]*data-w="(\d+)"[^>]*data-h="(\d+)"', dom)
        if not ok:
            err = re.search(r'id="__size"[^>]*data-err="([^"]*)"', dom)
            raise RuntimeError(f"mermaid 报错：{err.group(1) if err else '未捕获到尺寸'}")
        width_px, height_px = int(ok.group(1)), int(ok.group(2))
        if width_px <= 0 or height_px <= 0:
            raise RuntimeError("mermaid 渲染结果尺寸为 0")

        # 顺手存一份 svg 源文件，方便二次利用
        svg_path = None
        m = re.search(r'<textarea id="__svg">(.*?)</textarea>', dom, re.S)
        if m and m.group(1).strip():
            import html as _html
            svg_path = os.path.splitext(out_png)[0] + ".svg"
            with open(svg_path, "w", encoding="utf-8") as fh:
                fh.write(_html.unescape(m.group(1)))

        # 第二趟：按目标像素截图
        target_w, target_h = width_px * scale, height_px * scale
        page2 = self._write_page("page_shot.html", code,
                                 {"keep_dom": True, "target_width": target_w,
                                  "target_height": target_h})
        if os.path.exists(out_png):
            try:
                os.remove(out_png)   # 目标路径由我们生成，覆盖是预期行为
            except OSError:
                pass
        self._chrome_run(f"{server.url}/{os.path.basename(page2)}",
                         ["--virtual-time-budget=20000", "--window-size="
                          f"{target_w},{target_h}",
                          f"--screenshot={out_png}"])
        if not os.path.exists(out_png):
            raise RuntimeError("截图未生成")
        _png_size(out_png)          # 顺带校验 PNG 头，文件坏了当场报错
        return RenderResult(out_png, width_px, height_px, "chrome", svg_path)

    # --------------------------------------------------------------- mmdc
    def _render_mmdc(self, code: str, out_png: str) -> RenderResult | None:
        mmdc = self.mmdc_path()
        base = os.path.splitext(out_png)[0]
        mmd_file = base + ".mmd"
        with open(mmd_file, "w", encoding="utf-8") as fh:
            fh.write(code)
        puppeteer_cfg = os.path.join(self.work_dir, "puppeteer.json")
        os.makedirs(self.work_dir, exist_ok=True)
        with open(puppeteer_cfg, "w", encoding="utf-8") as fh:
            json.dump({"args": ["--no-sandbox", "--disable-gpu"]}, fh)
        scale = max(1, int(self.cfg.get("scale", 3)))
        cmd = [mmdc, "-i", mmd_file, "-o", out_png, "-s", str(scale),
               "-b", str(self.cfg.get("background", "#FFFFFF")).lstrip("#") or "FFFFFF",
               "-t", str(self.cfg.get("theme", "default")),
               "-p", puppeteer_cfg, "-q"]
        env = dict(os.environ)
        browser = self.browser_path()
        if browser:
            env["PUPPETEER_EXECUTABLE_PATH"] = browser
        subprocess.run(cmd, capture_output=True, timeout=180, env=env)
        if not os.path.exists(out_png):
            raise RuntimeError("mmdc 未生成图片")
        w, h = _png_size(out_png)
        return RenderResult(out_png, w // scale, h // scale, "mmdc",
                            os.path.splitext(out_png)[0] + ".svg")

    # -------------------------------------------------------------- kroki
    def _render_kroki(self, code: str, out_png: str) -> RenderResult | None:
        import urllib.request
        url = self.cfg.get("kroki_url") or "https://kroki.io/mermaid/png"
        data = json.dumps({"diagram_source": code, "diagram_type": "mermaid",
                           "output_format": "png", "scale": 1}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            blob = resp.read()
        with open(out_png, "wb") as fh:
            fh.write(blob)
        w, h = _png_size(out_png)
        return RenderResult(out_png, w, h, "kroki")

    def close(self):
        if self._server:
            self._server.stop()
            self._server = None


def _png_size(path: str) -> tuple[int, int]:
    """读 PNG 头拿宽高，省掉 Pillow 依赖。"""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("不是合法的 PNG 文件")
    return struct.unpack(">II", head[16:24])
