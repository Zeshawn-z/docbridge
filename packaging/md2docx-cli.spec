# -*- mode: python ; coding: utf-8 -*-
"""打包命令行版：md2docx.exe（保留控制台，方便批量转换与看日志）。

    python -m PyInstaller --noconfirm --clean packaging/md2docx-cli.spec
"""

import os
import sys

sys.path.insert(0, SPECPATH)
import common  # noqa: E402

NAME = "md2docx"
ENTRY = "entry_cli"          # 打包专用入口，见 packaging/entry_cli.py 的说明

a = Analysis([common.entry(ENTRY)], **common.analysis_options())

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                     # UPX 压过的 Qt DLL 容易出问题，不启用
    runtime_tmpdir=None,
    console=True,                  # 命令行工具，保留控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=common.icon(),
    version=common.version_file(NAME, "md2docx 命令行转换工具"),
)
