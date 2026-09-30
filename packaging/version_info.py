#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 PyInstaller 需要的 Windows 版本资源文件。

这样 exe 的"属性 → 详细信息"里能看到产品名与版本号，而不是一片空白。
版本号唯一来源是 md2docx.__version__，两个 spec 都调这里，不会各写一份。
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tuple4},
    prodvers={tuple4},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('080404b0', [
        StringStruct('CompanyName', 'DocBridge'),
        StringStruct('FileDescription', '{description}'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', '{internal}'),
        StringStruct('LegalCopyright', ''),
        StringStruct('OriginalFilename', '{filename}'),
        StringStruct('ProductName', 'DocBridge'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0804, 1200])])
  ]
)
"""


def version_tuple(version: str) -> str:
    """'1.1.0' → '(1, 1, 0, 0)'。"""
    parts = []
    for chunk in str(version).split(".")[:4]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 4:
        parts.append(0)
    return "(" + ", ".join(str(p) for p in parts) + ")"


def write(dest: str, *, version: str, description: str,
          filename: str, internal: str = "") -> str:
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.format(
            tuple4=version_tuple(version),
            version=version,
            description=description,
            filename=filename,
            internal=internal or os.path.splitext(filename)[0],
        ))
    return dest
