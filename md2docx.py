#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""md2docx 命令行入口。

用法：
    python md2docx.py 报告.md
    python md2docx.py 报告.md -o 输出.docx -c config/thesis.yaml
    python md2docx.py docs/ -o out/

默认排版规范（可用 -c 模板覆盖）：
  正文          小四（12pt），中文宋体 / 西文 Times New Roman，首行缩进 2 字符
  一级标题      小三（15pt），中文黑体 / 西文 Times New Roman
  二级标题      四号（14pt），中文黑体 / 西文 Times New Roman
  三级标题      小四（12pt），中文黑体 / 西文 Times New Roman
  行距          全篇 1.25 倍
  mermaid       渲染成图片后插入
  markdown 强调 统一转成加粗，语法标记不进正文
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from md2docx.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
