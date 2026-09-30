# -*- mode: python ; coding: utf-8 -*-
"""打包图形界面版：md2docx-gui.exe（不带控制台窗口）。

    python -m PyInstaller --noconfirm --clean packaging/md2docx-gui.spec
"""

import os
import sys

sys.path.insert(0, SPECPATH)
import common  # noqa: E402

NAME = "docbridge"
ENTRY = "entry_gui"          # exe 名用连字符，入口脚本避开 md2docx 重名

a = Analysis([common.entry(ENTRY)], **common.analysis_options())

# Qt 6 uses the ICU API provided by Windows. An unrelated icuuc.dll from
# Poppler on the build machine's PATH exports a different ABI and prevents
# QtCore from loading. Let Windows resolve its own platform library.
a.binaries = [entry for entry in a.binaries
              if os.path.basename(entry[0]).lower() != 'icuuc.dll']

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
    upx=False,
    runtime_tmpdir=None,
    console=False,                 # 双击不要弹黑框；--selftest 靠退出码与日志文件回报
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=common.icon(),
    version=common.version_file(NAME, "DocBridge Word 与 Markdown 转换工具"),
)
