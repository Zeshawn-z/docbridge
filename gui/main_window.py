"""主窗口。

无边框圆角窗口：自定义标题栏负责拖动，窗口四周留出阴影边距并做边缘缩放。
内容分三块——左侧文件区、右侧设置、底部状态与主操作。
"""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QPlainTextEdit, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import animations as anim
from . import config_bridge as bridge
from .settings_panel import SettingsPanel
from .theme import Color, Motion, Radius, Space
from .widgets import (DropArea, ElidedLabel, FileRow, IconButton, SlimProgress,
                      SolidButton, TextButton, app_pixmap)
from .worker import ConvertJob, ConvertWorker

SHADOW_MARGIN = 16
EDGE_GRAB = 6


def open_path(path: str) -> None:
    """用系统默认程序打开文件或目录。"""
    if not path or not os.path.exists(path):
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError:
        pass


class TitleBar(QFrame):
    """自绘标题栏：左边是应用标记与名称，右边是最小化与关闭。"""

    def __init__(self, window: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)
        self._window = window
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(9)

        mark = QLabel()
        mark.setPixmap(app_pixmap(20))
        mark.setFixedSize(20, 20)
        mark.setStyleSheet("background:transparent;")
        layout.addWidget(mark)

        title = QLabel("md2docx")
        title.setObjectName("TitleText")
        title.setStyleSheet("background:transparent;")
        layout.addWidget(title)

        version = QLabel("Markdown → Word")
        version.setObjectName("TitleVersion")
        version.setStyleSheet("background:transparent;")
        layout.addWidget(version)
        layout.addStretch(1)

        minimize = IconButton(IconButton.MINIMIZE, size=30)
        minimize.clicked.connect(window.showMinimized)
        close = IconButton(IconButton.CLOSE, size=30, danger=True)
        close.clicked.connect(window.close)
        layout.addWidget(minimize)
        layout.addWidget(close)

    # -- 拖动窗口 --------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = (event.globalPosition().toPoint()
                                 - self._window.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_offset is not None and (event.buttons() & Qt.LeftButton):
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_offset = None


class MainWindow(QWidget):
    #: 最小尺寸按"右侧面板能完整显示详细配置"倒推。面板首屏那一屏本身就要
    #: 820px（含五个收起的分组标题与"详细配置"标签），窗口再小就得靠滚动条
    #: 才能看到"恢复默认设置"，所以下限定在 900 高而不是 640。
    MIN_WIDTH = 900
    MIN_HEIGHT = 860

    #: 默认尺寸。高度按屏幕工作区的 88% 取，上限 1020——本机 1152 高、任务栏
    #: 占 48px，用 88% 正好落在 950 附近，面板一屏放得下且不至于顶天立地。
    DEFAULT_WIDTH = 1120
    DEFAULT_HEIGHT = 968

    def __init__(self):
        super().__init__()
        self.setWindowTitle("md2docx · Markdown 转规范排版 Word")
        self.setWindowIcon(app_pixmap(64))
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(*self._initial_size())

        self._rows: dict[str, FileRow] = {}
        self._order: list[str] = []
        self._outputs: dict[str, str] = {}
        self._converted: list[str] = []
        self._worker: ConvertWorker | None = None
        self._cancelling = False
        self._status_kind = ""
        self._resize_edge: str | None = None
        self._resize_origin: QRect | None = None
        self._resize_start: QPoint | None = None
        self.setMouseTracking(True)

        self._build()
        self._bind_shortcuts()
        self._set_status("就绪　把 Markdown 拖进来，或点击虚框选择文件")

    @classmethod
    def _initial_size(cls) -> tuple[int, int]:
        """按屏幕工作区算一个合适的开窗尺寸。

        小屏上不硬撑：拿不到工作区或算出来比最小尺寸还小，就退回最小尺寸，
        让滚动条兜底，而不是开出一个装不下的窗口。
        """
        width, height = cls.DEFAULT_WIDTH, cls.DEFAULT_HEIGHT
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            height = min(height, max(cls.MIN_HEIGHT, int(area.height() * 0.88)))
            width = min(width, max(cls.MIN_WIDTH, area.width() - 80))
        return width, height

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW_MARGIN, SHADOW_MARGIN,
                                 SHADOW_MARGIN, SHADOW_MARGIN + 2)
        outer.setSpacing(0)

        root = QFrame()
        root.setObjectName("Root")
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(TitleBar(self, root))

        content = QWidget()
        content.setObjectName("ContentArea")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(Space.WINDOW_PAD, 4, Space.WINDOW_PAD, 0)
        content_layout.setSpacing(30)
        content_layout.addWidget(self._build_left(content), 1)
        self.settings = SettingsPanel(content)
        self.settings.changed.connect(self._on_settings_changed)
        content_layout.addWidget(self.settings, 0)
        layout.addWidget(content, 1)

        layout.addWidget(self._build_footer(root))

    def _build_left(self, parent: QWidget) -> QWidget:
        host = QWidget(parent)
        host.setObjectName("ContentArea")
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hero = QLabel("Markdown → 规范排版 Word")
        hero.setObjectName("HeroTitle")
        hero.setStyleSheet("background:transparent;")
        subtitle = QLabel("正文小四宋体、标题黑体、1.25 倍行距，mermaid 自动出图")
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setStyleSheet("background:transparent;")
        layout.addWidget(hero)
        layout.addSpacing(3)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        # 空态 / 列表 两态切换
        self._drop = DropArea()
        self._drop.clicked.connect(self._pick_files)
        self._drop.files_dropped.connect(self.add_files)

        list_host = QWidget()
        list_host.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)
        self._list_layout.addStretch(1)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QScrollArea.NoFrame)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_scroll.setWidget(list_host)
        self._list_scroll.setStyleSheet("background:transparent;")

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._stack.addWidget(self._drop)
        self._stack.addWidget(self._list_scroll)
        layout.addWidget(self._stack, 1)

        # 文件操作行
        self._actions = QWidget()
        self._actions.setStyleSheet("background:transparent;")
        action_layout = QHBoxLayout(self._actions)
        action_layout.setContentsMargins(2, 8, 2, 0)
        action_layout.setSpacing(4)
        self._count_label = ElidedLabel("", color=Color.TEXT_TERTIARY)
        add_button = TextButton("添加文件")
        add_button.clicked.connect(self._pick_files)
        clear_button = TextButton("清空", color=Color.TEXT_TERTIARY)
        clear_button.clicked.connect(self.clear_files)
        action_layout.addWidget(self._count_label)
        action_layout.addStretch(1)
        action_layout.addWidget(add_button)
        action_layout.addWidget(clear_button)
        self._actions.setVisible(False)
        layout.addWidget(self._actions)

        # 日志（默认收起）
        self._log_box = QFrame()
        self._log_box.setStyleSheet("background:transparent;")
        log_layout = QVBoxLayout(self._log_box)
        log_layout.setContentsMargins(0, 14, 0, 0)
        log_layout.setSpacing(0)
        self._log = QPlainTextEdit()
        self._log.setObjectName("LogView")
        self._log.setReadOnly(True)
        self._log.setFixedHeight(126)
        # 按控件宽度换行 + 关掉横向滚动条：日志区出现横向滚动条很难看
        self._log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        log_layout.addWidget(self._log)
        self._log_box.setVisible(False)
        self._log_box.setMaximumHeight(0)
        layout.addWidget(self._log_box)

        return host

    def _build_footer(self, parent: QWidget) -> QWidget:
        footer = QWidget(parent)
        footer.setObjectName("Footer")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(Space.WINDOW_PAD, 6, Space.WINDOW_PAD, 16)
        layout.setSpacing(11)

        self._progress = SlimProgress()
        anim.set_opacity(self._progress, 1.0)
        layout.addWidget(self._progress)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self._status = QLabel("")
        self._status.setObjectName("StatusText")
        self._status.setStyleSheet("background:transparent;")
        row.addWidget(self._status)
        row.addStretch(1)

        self._open_dir = TextButton("打开输出目录", color=Color.TEXT_SECONDARY)
        self._open_dir.clicked.connect(self._open_output_dir)
        self._open_dir.setVisible(False)
        row.addWidget(self._open_dir)

        self._cancel = TextButton("取消", color=Color.DANGER)
        self._cancel.clicked.connect(self._cancel_convert)
        self._cancel.setVisible(False)
        row.addWidget(self._cancel)

        self._convert = SolidButton("开始转换")
        self._convert.clicked.connect(self._start_convert)
        row.addWidget(self._convert)

        layout.addLayout(row)
        return footer

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, self._pick_files)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._start_convert)
        QShortcut(QKeySequence("Esc"), self, self.close)

    # ------------------------------------------------------------------ 文件
    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择 Markdown 文件", bridge.default_output_dir(),
            "Markdown (*.md *.markdown);;所有文件 (*)")
        if files:
            self.add_files(files)

    def add_files(self, paths: list[str]) -> None:
        added: list[FileRow] = []
        for path in paths:
            real = os.path.abspath(path)
            if real in self._rows:
                continue
            row = FileRow(real)
            row.remove_requested.connect(self._remove_file)
            row.activated.connect(self._open_result)
            self._rows[real] = row
            self._order.append(real)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            added.append(row)
        if not added:
            return
        self._sync_state()
        anim.stagger(added, step=40)
        if self._stack.currentIndex() != 1:
            self._switch_to_list()

    def _switch_to_list(self) -> None:
        self._stack.setCurrentIndex(1)
        self._list_scroll.setGraphicsEffect(None)
        anim.fade(self._list_scroll, duration=Motion.BASE)

    def _switch_to_empty(self) -> None:
        self._stack.setCurrentIndex(0)
        anim.fade(self._drop, duration=Motion.BASE)

    def _remove_file(self, path: str) -> None:
        row = self._rows.pop(path, None)
        if row is None:
            return
        self._order.remove(path)
        self._outputs.pop(path, None)
        if path in self._converted:
            self._converted.remove(path)
        self._list_layout.removeWidget(row)
        anim.collapse(row, duration=Motion.FAST, on_done=lambda r=row: r.deleteLater())
        self._sync_state()

    def clear_files(self) -> None:
        for path in list(self._order):
            self._remove_file(path)
        self._log.clear()
        if not self._converted:
            self._collapse_log()

    def _sync_state(self) -> None:
        count = len(self._order)
        self._actions.setVisible(count > 0)
        self._count_label.setText(f"共 {count} 个文件")
        if count == 0:
            self._switch_to_empty()
        self._convert.setEnabled(count > 0 and self._worker is None)

    def _open_result(self, src: str) -> None:
        target = self._outputs.get(src)
        if target and os.path.exists(target):
            open_path(target)
        elif os.path.exists(src):
            open_path(src)

    def _open_output_dir(self) -> None:
        directory = self.settings.effective_output_dir(self._order)
        if directory:
            open_path(directory)

    # ------------------------------------------------------------------ 设置
    def _on_settings_changed(self) -> None:
        if self._worker is None:
            self._set_status("参数已更新，点「开始转换」生效")

    # ------------------------------------------------------------------ 转换
    def _start_convert(self) -> None:
        if self._worker is not None or not self._order:
            return
        pending = [p for p in self._order if not os.path.exists(p)]
        for path in pending:
            row = self._rows.get(path)
            if row:
                row.set_status("error")
        jobs = [ConvertJob(src, self.settings.output_target(src))
                for src in self._order if os.path.exists(src)]
        if not jobs:
            self._set_status("列表里的文件都不存在了", kind="error")
            return

        self._outputs = {}
        self._converted = []
        for row in self._rows.values():
            row.set_status("idle", animate=False)

        self._expand_log()
        self._log.clear()
        self._log.appendPlainText(bridge.describe_overrides(self.settings.overrides()))
        self._progress.set_progress(0.0, animate=False)
        anim.set_opacity(self._progress, 1.0)
        self._progress.setVisible(True)

        self._convert.setEnabled(False)
        self._convert.setText("转换中…")
        self._cancel.setVisible(True)
        self._open_dir.setVisible(False)
        self._set_status(f"正在转换　0/{len(jobs)}")

        worker = ConvertWorker(jobs, self.settings.template_path(),
                               self.settings.overrides(), self)
        worker.log.connect(self._append_log)
        worker.file_started.connect(self._on_file_started)
        worker.file_done.connect(self._on_file_done)
        worker.progress.connect(self._on_progress)
        worker.finished_all.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def _cancel_convert(self) -> None:
        if self._worker is not None:
            self._cancelling = True
            self._worker.cancel()
            self._cancel.setVisible(False)
            self._set_status("正在停止…", kind="warn")

    def _on_file_started(self, src: str) -> None:
        row = self._rows.get(src)
        if row:
            row.set_status("running")

    def _on_file_done(self, src: str, out: str, ok: bool, message: str) -> None:
        row = self._rows.get(src)
        if row:
            row.set_status("ok" if ok else "error")
        if ok:
            self._outputs[src] = out
            self._converted.append(src)

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.set_progress(done / max(1, total))
        if not self._cancelling:
            self._set_status(f"正在转换　{done}/{total}")

    def _on_finished(self, ok_count: int, fail_count: int, seconds: int) -> None:
        self._worker = None
        self._cancelling = False
        self._convert.setEnabled(bool(self._order))
        self._convert.setText("开始转换")
        self._cancel.setVisible(False)
        self._open_dir.setVisible(bool(self._converted))

        if fail_count and not ok_count:
            self._set_status(f"转换失败　{fail_count} 个文件未能完成，详见日志", kind="error")
        elif fail_count:
            self._set_status(f"部分完成　成功 {ok_count} 个，失败 {fail_count} 个",
                             kind="warn")
        else:
            self._set_status(f"已完成 {ok_count} 个文件　用时 {seconds} 秒，"
                             f"双击列表项可直接打开", kind="ok")
        # 满格的进度线会变成一条横贯窗口的蓝线，像分隔线；让它亮一下再淡出
        self._progress.set_progress(1.0)
        QTimer.singleShot(140, self._fade_progress)

    def _fade_progress(self) -> None:
        anim.fade(self._progress, start=1.0, end=0.0, duration=320,
                  on_done=lambda: self._progress.setVisible(False))

    # ------------------------------------------------------------------ 日志
    def _append_log(self, line: str) -> None:
        self._log.appendPlainText(line)
        bar = self._log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _expand_log(self) -> None:
        if self._log_box.isVisible():
            return
        anim.reveal(self._log_box, duration=Motion.SLOW)

    def _collapse_log(self) -> None:
        if self._log_box.isVisible():
            anim.collapse(self._log_box)

    def _set_status(self, text: str, kind: str = "info") -> None:
        colors = {"ok": Color.SUCCESS, "warn": Color.WARNING,
                  "error": Color.DANGER, "info": Color.TEXT_SECONDARY}
        names = {"ok": "StatusOk", "warn": "StatusWarn",
                 "error": "StatusError", "info": "StatusText"}
        self._status.setObjectName(names.get(kind, "StatusText"))
        self._status.setStyleSheet(
            f"background:transparent; color:{colors.get(kind, Color.TEXT_SECONDARY)};")
        self._status.setText(text)
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)
        if kind != self._status_kind:
            self._status_kind = kind
            anim.fade(self._status, duration=Motion.BASE)

    # ------------------------------------------------------------------ 拖放
    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls() and DropArea._accepts(event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        files = DropArea._accepts(event.mimeData().urls())
        if files:
            self.add_files(files)
        event.acceptProposedAction()

    # ------------------------------------------------------------------ 缩放
    def paintEvent(self, event):  # noqa: N802
        """在窗口四周的透明边距里画出柔和投影。

        用几层渐隐的圆角矩形叠出来，比 QGraphicsDropShadowEffect 便宜得多——
        后者会把整窗做一次高斯模糊，子控件每帧动画都要重算，明显掉帧。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        panel = QRectF(self.rect()).adjusted(
            SHADOW_MARGIN, SHADOW_MARGIN, -SHADOW_MARGIN, -SHADOW_MARGIN - 2)
        layers = 11
        for index in range(layers, 0, -1):
            grow = index * 1.5
            alpha = int(10 * (1 - index / layers) ** 1.4) + 1
            painter.setBrush(QColor(15, 23, 42, alpha))
            rect = panel.adjusted(-grow, -grow + 3.0, grow, grow + 3.0)
            painter.drawRoundedRect(rect, Radius.WINDOW + grow * 0.9,
                                    Radius.WINDOW + grow * 0.9)
        painter.end()

    def _edge_at(self, pos: QPoint) -> str | None:
        margin = SHADOW_MARGIN + EDGE_GRAB
        rect = self.rect()
        left = pos.x() <= rect.left() + margin
        right = pos.x() >= rect.right() - margin
        top = pos.y() <= rect.top() + margin
        bottom = pos.y() >= rect.bottom() - margin
        vertical = ("top" if top else "") + ("bottom" if bottom else "")
        horizontal = ("left" if left else "") + ("right" if right else "")
        if vertical and horizontal:
            return vertical + "_" + horizontal
        return vertical or horizontal or None

    CURSORS = {
        "left": Qt.SizeHorCursor, "right": Qt.SizeHorCursor,
        "top": Qt.SizeVerCursor, "bottom": Qt.SizeVerCursor,
        "top_left": Qt.SizeFDiagCursor, "bottom_right": Qt.SizeFDiagCursor,
        "top_right": Qt.SizeBDiagCursor, "bottom_left": Qt.SizeBDiagCursor,
    }

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            edge = self._edge_at(event.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._resize_origin = self.geometry()
                self._resize_start = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):  # noqa: N802
        pos = event.position().toPoint()
        if self._resize_edge and self._resize_origin and self._resize_start:
            self._perform_resize(event.globalPosition().toPoint())
            return
        edge = self._edge_at(pos)
        self.setCursor(self.CURSORS.get(edge, Qt.ArrowCursor) if edge else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._resize_edge = None
        self._resize_origin = None
        self._resize_start = None

    def _perform_resize(self, global_pos: QPoint) -> None:
        delta = global_pos - self._resize_start
        origin = QRect(self._resize_origin)
        edge = self._resize_edge or ""
        left, top, right, bottom = (origin.left(), origin.top(),
                                    origin.right(), origin.bottom())
        if "left" in edge:
            left = min(origin.left() + delta.x(), right - self.MIN_WIDTH)
        if "right" in edge:
            right = max(origin.right() + delta.x(), left + self.MIN_WIDTH)
        if "top" in edge:
            top = min(origin.top() + delta.y(), bottom - self.MIN_HEIGHT)
        if "bottom" in edge:
            bottom = max(origin.bottom() + delta.y(), top + self.MIN_HEIGHT)
        self.setGeometry(QRect(QPoint(left, top), QPoint(right, bottom)))

    # ------------------------------------------------------------------ 收尾
    def closeEvent(self, event):  # noqa: N802
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(4000)
        event.accept()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
