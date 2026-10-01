#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""两个 PyInstaller spec 共用的打包参数。

集中在这里的原因：data 文件、隐藏导入、排除列表一旦要改，只改一处，
不会出现"CLI 打进了一个文件、GUI 忘了打"这种事。
"""

from __future__ import annotations

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
PACKAGING = os.path.dirname(os.path.abspath(__file__))
for _path in (SRC, PACKAGING):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from md2docx import __version__, resources  # noqa: E402
from notices import license_files

ICON = os.path.join(PACKAGING, "md2docx.ico")


def icon() -> str | None:
    """图标由 packaging/make_icon.py 现场生成；没生成就退化成默认图标，
    不让直接跑 spec 的人卡在一个缺文件上。"""
    return ICON if os.path.exists(ICON) else None

#: 随 exe 一起携带的只读资源。dest 是解包目录（sys._MEIPASS）里的相对路径，
#: 与 src/md2docx/resources.py 的 resource_root() 约定一致。
DATAS = [
    (os.path.join(ROOT, "config"), "config"),
    (resources.mermaid_js_path(), os.path.join("tools", "vendor")),
    (os.path.join(resources.vendor_dir(), 'katex'), os.path.join('tools', 'vendor', 'katex')),
]
for package in ('latex2mathml',):
    DATAS.extend(collect_data_files(package))
DATAS.extend((str(source), target) for source, target in license_files())

#: PyInstaller 静态分析抓不到的导入（大多是条件导入或动态加载）。
#: 只写确实存在的模块名——写错会在日志里刷 ERROR，容易被误当成构建失败。
HIDDEN_IMPORTS = [
    "linkify_it", "mdurl",
    "yaml",
    "docx", "docx.opc.part", "docx.image", "lxml.etree", "lxml._elementpath",
    # 把包内模块写全：既防条件导入漏掉，也确保 md2docx 解析到 src/ 下的包
    # 而不是项目根那个同名的 md2docx.py 入口脚本
    "md2docx", "md2docx.cli", "md2docx.config", "md2docx.mermaid",
    "md2docx.numbering", "md2docx.ooxml", "md2docx.renderer", "md2docx.resources",
    "md2docx.units",
    "docbridge_math", "docbridge_math.codec", "docbridge_math.omml", "docbridge_math.katex",
    "latex2mathml.converter", "mathml2omml", "websocket",
    "mdit_py_plugins.dollarmath", "mdit_py_plugins.texmath",
]

#: 排除用不到的东西：tkinter 与仓库里没有的 Qt 模块是体积大头
EXCLUDES = [
    "tkinter", "_tkinter", "turtle",
    "unittest", "pydoc_data", "lib2to3", "distutils", "setuptools",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2", "PySide6.QtQuickTest",
    "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebView",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtBluetooth",
    "PySide6.QtNfc", "PySide6.QtSerialPort", "PySide6.QtSensors", "PySide6.QtHelp",
    "PySide6.QtUiTools", "PySide6.QtConcurrent", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtTextToSpeech", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtStateMachine", "PySide6.QtHttpServer",
]


def analysis_options() -> dict:
    """直接 `Analysis([...], **common.analysis_options())`。"""
    return {
        "pathex": [SRC, ROOT],
        "binaries": [],
        "datas": list(DATAS),
        "hiddenimports": list(HIDDEN_IMPORTS),
        "hookspath": [],
        "excludes": list(EXCLUDES),
        "noarchive": False,
        "optimize": 0,
    }


def entry(script: str) -> str:
    """入口脚本的绝对路径。

    先按项目根找，再按 packaging/ 找。打包用的入口刻意放在 packaging/ 下，
    文件名避开 md2docx，免得占了顶层模块名遮住 src/md2docx 包。
    """
    for base in (PACKAGING, ROOT):
        path = os.path.join(base, f"{script}.py")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"入口脚本不存在：{script}.py（找过 packaging/ 与项目根）")


def version_file(name: str, description: str) -> str:
    """在 build/ 下生成版本资源文件并返回路径。"""
    from version_info import write  # 同目录，SPECPATH 已在 sys.path 上

    target = os.path.join(ROOT, "build", f"version-{name}.txt")
    return write(target, version=__version__, description=description,
                 filename=f"{name}.exe")
