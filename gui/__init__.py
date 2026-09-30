"""md2docx 图形界面。

在这里做一次 sys.path 兜底，这样无论从项目根、`gui/` 子目录还是打包后的
exe 里导入，`md2docx` 都能被找到。
"""

from __future__ import annotations

import os
import sys

__all__ = ["main"]

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (os.path.join(_ROOT, "src"), _ROOT):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)


def main() -> int:
    from .app import main as _main
    return _main()
