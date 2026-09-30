#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包命令行版专用的入口脚本。

**刻意不叫 md2docx.py。** PyInstaller 会用入口脚本的文件名当顶层模块名，
而项目里已经有一个同名的包 `src/md2docx/`。两者撞名时，冻结后的
`from md2docx import resources` 会命中脚本自己，报：

    ModuleNotFoundError: No module named 'md2docx.cli'; 'md2docx' is not a package

源码运行时之所以看不出问题，是因为 `md2docx.py` 把 `src` 插到了 sys.path 最前面，
包先于脚本被找到。冻结环境没有这层顺序，问题就暴露了。

所以这里换一个不会撞名的文件名，把"用户敲的命令"和"给打包器看的入口"分开。
"""

from __future__ import annotations

import os
import sys

if not getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from md2docx.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
