#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""md2docx 图形界面入口。

双击运行，或：
    .venv\\Scripts\\python.exe md2docx_gui.py

功能与命令行一致：把 Markdown 拖进窗口 → 选模板 → 开始转换。
转换在后台线程执行，界面不会卡住。

排查用：
    md2docx_gui.py --selftest [输出.png]    # 不上屏渲染一帧，按结果返回退出码
"""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.join(ROOT, "src"), ROOT):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

if importlib.util.find_spec("PySide6") is None:
    sys.stderr.write(
        "缺少 PySide6，图形界面无法启动。先安装：\n"
        f'  "{os.path.join(ROOT, ".venv", "Scripts", "python.exe")}" '
        "-m pip install PySide6-Essentials "
        "-i https://mirrors.aliyun.com/pypi/simple/\n"
        "（只做 Markdown 转换的话可以不用界面：md2docx.py 报告.md）\n")
    raise SystemExit(2)

from gui.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
