#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包界面版专用的入口脚本。

与 entry_cli.py 同理：文件名避开 md2docx，免得占了顶层模块名把
`src/md2docx/` 这个包遮住（详见 entry_cli.py 的说明）。
"""

from __future__ import annotations

import os
import sys

if not getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _path in (os.path.join(_ROOT, "src"), _ROOT):
        if os.path.isdir(_path) and _path not in sys.path:
            sys.path.insert(0, _path)

from gui.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
