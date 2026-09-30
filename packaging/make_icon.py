#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 Windows 图标 packaging/md2docx.ico。

复用界面里那个应用标记（gui.widgets.app_pixmap），渲染成 16~256 的多个尺寸，
再手写 ICO 容器。Qt 的 ICO 插件只读不写，Pillow 又没装，所以按格式自己拼：
每个尺寸一条 DIB（BITMAPINFOHEADER + BGRA 像素 + AND 掩码），兼容性最好，
比只放 PNG 条目的 ICO 稳。

    .venv\\Scripts\\python.exe packaging\\make_icon.py
"""

from __future__ import annotations

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.widgets import app_pixmap  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "md2docx.ico")


def dib_bytes(image: QImage) -> bytes:
    """把 QImage 转成 ICO 里的 DIB 条目：自下而上的 BGRA + 全零 AND 掩码。"""
    width, height = image.width(), image.height()
    buffer = bytes(image.constBits())
    stride = image.bytesPerLine()

    header = struct.pack(
        "<IiiHHIIiiII",
        40,                 # biSize
        width,              # biWidth
        height * 2,         # biHeight：颜色位图 + 掩码位图，所以是两倍
        1,                  # biPlanes
        32,                 # biBitCount
        0,                  # biCompression = BI_RGB
        0, 0, 0, 0, 0,      # biSizeImage / XPelsPerMeter / YPelsPerMeter / ClrUsed / ClrImportant
    )

    rows = []
    for y in range(height - 1, -1, -1):        # DIB 是自下而上存的
        start = y * stride
        rows.append(buffer[start:start + width * 4])   # QImage ARGB32 在内存里就是 BGRA

    # 32 位带 alpha 的位图其实不看掩码，但格式要求必须有，按 4 字节对齐填零
    mask_stride = ((width + 31) // 32) * 4
    mask = b"\x00" * (mask_stride * height)

    return header + b"".join(rows) + mask


def build(sizes=SIZES, out_path: str = OUT_PATH) -> str:
    QApplication.instance() or QApplication(sys.argv[:1])

    entries = []
    blobs = []
    offset = 6 + 16 * len(sizes)            # ICONDIR 头 + 每个条目 16 字节
    for size in sizes:
        pixmap = app_pixmap(size)
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        blob = dib_bytes(image)
        entries.append(struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,      # 宽，256 记作 0
            size if size < 256 else 0,      # 高
            0,                              # 调色板颜色数
            0,                              # 保留
            1,                              # 色彩平面
            32,                             # 位深
            len(blob),
            offset,
        ))
        blobs.append(blob)
        offset += len(blob)

    icondir = struct.pack("<HHH", 0, 1, len(sizes))
    with open(out_path, "wb") as fh:
        fh.write(icondir)
        for entry in entries:
            fh.write(entry)
        for blob in blobs:
            fh.write(blob)

    return out_path


def main() -> int:
    path = build()
    print(f"icon written: {path} ({os.path.getsize(path)} bytes, {len(SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
