"""后台转换线程。

界面只跟信号打交道：每转完一个文件回一次进度，全程不阻塞 UI。
转换本身直接复用 src/md2docx 的引擎，不另起进程。
"""

from __future__ import annotations

import os
import time
import traceback

from PySide6.QtCore import QThread, Signal

from md2docx.config import load_config
from md2docx.renderer import MarkdownToDocx


class ConvertJob:
    """一个待转换文件。"""

    def __init__(self, src: str, out: str):
        self.src = src
        self.out = out


class ConvertWorker(QThread):
    log = Signal(str)
    file_started = Signal(str)
    file_done = Signal(str, str, bool, str)     # src, out, ok, message
    progress = Signal(int, int)                 # 已处理, 总数
    finished_all = Signal(int, int, int)        # 成功, 失败, 总耗时(秒)

    def __init__(self, jobs: list[ConvertJob], template: str | None,
                 overrides: dict | None, parent=None):
        super().__init__(parent)
        self._jobs = jobs
        self._template = template
        self._overrides = overrides or {}
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D102
        started = time.time()
        ok_count = 0
        fail_count = 0
        try:
            config = load_config(self._template, self._overrides)
            self.log.emit(f"模板：{config.get('_meta', {}).get('template', 'default.yaml')}"
                          f"　待转换 {len(self._jobs)} 个文件")
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"配置加载失败：{exc}")
            self.finished_all.emit(0, len(self._jobs), 0)
            return

        for index, job in enumerate(self._jobs, 1):
            if self._cancel:
                self.log.emit("已取消，剩余文件未处理")
                break
            self.file_started.emit(job.src)
            self.log.emit(f"[{index}/{len(self._jobs)}] {os.path.basename(job.src)}")
            converter = None
            try:
                converter = MarkdownToDocx(
                    config, job.src, job.out,
                    log=lambda line: self.log.emit("    " + str(line).strip()))
                with open(job.src, "r", encoding="utf-8") as fh:
                    text = fh.read()
                converter.render(text)
                for warning in converter.warnings:
                    self.log.emit(f"    ! {warning}")
                converter.save()
                counters = converter.counters
                message = (f"{os.path.getsize(job.out) / 1024:.0f} KB ／ "
                           f"标题 {counters['heading']}　段落 {counters['paragraph']}　"
                           f"表格 {counters['table']}　列表 {counters['list']}　"
                           f"mermaid 图 {counters['mermaid']}")
                self.file_done.emit(job.src, job.out, True, message)
                self.log.emit(f"    完成 {message}")
                ok_count += 1
            except Exception as exc:  # noqa: BLE001
                fail_count += 1
                detail = f"{type(exc).__name__}: {exc}"
                self.log.emit(f"    [失败] {detail}")
                if os.environ.get("MD2DOCX_DEBUG"):
                    self.log.emit(traceback.format_exc())
                self.file_done.emit(job.src, job.out, False, detail)
            finally:
                if converter is not None and converter._mermaid is not None:
                    converter._mermaid.close()
            self.progress.emit(index, len(self._jobs))

        self.finished_all.emit(ok_count, fail_count, int(time.time() - started))
