# -*- mode: python ; coding: utf-8 -*-
import sys
sys.path.insert(0, SPECPATH)
import common

NAME = 'docx2md'
a = Analysis([common.entry('entry_docx2md')], **common.analysis_options())
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=NAME,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, disable_windowed_traceback=False, icon=common.icon(),
          version=common.version_file(NAME, 'DocBridge Word 转 Markdown 命令行工具'))
