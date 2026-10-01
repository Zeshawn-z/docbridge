"""应用装配：QApplication、全局样式、主窗口。

界面线程只做展示，转换在 ConvertWorker 里跑，互不阻塞。
附带一个 `--selftest`：不上屏、渲染一帧、按结果返回退出码。
打包成 exe 之后没有控制台，靠退出码和产出的 PNG 判断"这个 exe 到底能不能跑起来"。
"""

from __future__ import annotations

import os
import sys

from . import theme
from .preview import prepare, snapshot


def make_app():
    """按统一的视觉基线装配 QApplication（main 与自检共用）。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("DocBridge")
    app.setApplicationDisplayName("DocBridge")
    app.setOrganizationName("md2docx")

    # Fusion 作为跨平台基线，再用自己的 QSS 覆盖成极简浅色
    app.setStyle("Fusion")
    base_font = QFont()
    base_font.setFamily("Microsoft YaHei UI")
    base_font.setPixelSize(theme.Font.SIZE_BODY)
    base_font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(base_font)
    app.setStyleSheet("")
    return app


def selftest(output: str | None = None, conversion_input: str | None = None) -> int:
    """渲染一帧界面并出图，返回 0 表示正常。

    这是给 CI / 用户排查打包问题用的：如果 Qt 平台插件没打进包里、
    或者样式表解析失败，这里会以非 0 退出。
    """
    from .workbench import MainWindow

    target = os.path.abspath(output or "md2docx-gui-selftest.png")
    info = []

    def log(line: str) -> None:
        info.append(line)

    try:
        app = make_app()
        from PySide6.QtGui import QFontDatabase

        log(f"py={sys.version.split()[0]} frozen={getattr(sys, 'frozen', False)}")
        log(f"platform={app.platformName()} families={len(QFontDatabase.families())}")
        window = MainWindow()
        window.resize(1280, 900)
        prepare(window)
        if conversion_input:
            import time
            from pathlib import Path
            source = Path(conversion_input).resolve()
            window.switch_mode('md2word' if source.suffix.lower() in ('.md', '.markdown') else 'word2md')
            page = window.current_page
            page.append_files([source])
            if not page.files:
                raise ValueError(f'不支持此自检输入：{source}')
            page.start()
            deadline = time.monotonic() + 150
            while page.busy and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            if page.busy or not page.results:
                raise RuntimeError('转换自检失败：' + page.log.toPlainText())
            result = next(iter(page.results.values()))
            log(f'converted={page.result_path(result)} images={result.image_count}')
            if source.suffix.lower() in ('.md', '.markdown'):
                window.switch_mode('paste2word')
                pasted = window.current_page
                pasted.editor.setPlainText(source.read_text(encoding='utf-8-sig'))
                pasted.save_to(Path(target).with_suffix('.text.docx'))
                deadline = time.monotonic() + 90
                while pasted.busy and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(.01)
                if pasted.busy or pasted.result is None:
                    raise RuntimeError('文本写入自检失败：' + pasted.status.text())
                window.switch_mode('word2text')
                text_page = window.current_page
                text_page.load_file(pasted.result.output)
                deadline = time.monotonic() + 90
                while text_page.busy and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(.01)
                if text_page.busy or text_page.result is None or not text_page.editor.toPlainText().strip():
                    raise RuntimeError('文本读取自检失败：' + text_page.status.text())
                log('text-workflows=OK')
                window.switch_mode('md2word')
        snapshot(window, target, background="#E9EDF2")
        size = os.path.getsize(target)
        log(f"screenshot={target} bytes={size}")
        ok = size > 5000
        log("selftest=OK" if ok else "selftest=FAIL 截图过小，界面可能没渲染出来")
        return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        log(f"selftest=FAIL {type(exc).__name__}: {exc}")
        import traceback
        log(traceback.format_exc())
        return 1
    finally:
        text = "\n".join(info)
        try:
            with open(target + ".log", "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
        # 打包成 windowed exe 后 sys.stdout 可能是 None，别在这里崩掉
        try:
            stream = sys.stdout
            if stream is not None:
                stream.write(text + "\n")
                stream.flush()
        except (OSError, ValueError, AttributeError):
            pass


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--selftest" in argv:
        index = argv.index("--selftest")
        rest = argv[index + 1:]
        conversion_input = None
        if '--selftest-convert' in argv:
            source_index = argv.index('--selftest-convert')
            if source_index + 1 < len(argv):
                conversion_input = argv[source_index + 1]
        return selftest(rest[0] if rest and not rest[0].startswith('--') else None, conversion_input)

    from .workbench import MainWindow

    app = make_app()
    window = MainWindow()
    window.show()
    return app.exec()
