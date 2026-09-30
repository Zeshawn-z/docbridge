"""User-triggered legacy Word engine download; independent of conversion jobs."""
import threading
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar
from docx2md.legacy import find_libreoffice
from docx2md.runtime import install_runtime, DownloadCancelled
from .icons import icon


class RuntimeWorker(QThread):
    progress = Signal(str, object, object)
    ready = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancel_event = threading.Event()

    def run(self):
        try:
            path = install_runtime(self.progress.emit, self.cancel_event.is_set)
            self.ready.emit(str(path))
        except DownloadCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class DocSupportOptions(QWidget):
    lock_during_conversion = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.busy = False
        self.worker = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 8)
        self.status = QLabel('未启用')
        self.status.setObjectName('sectionTitle')
        layout.addWidget(self.status)
        hint = QLabel('旧版 .doc 需要 LibreOffice 引擎。\n首次下载约 358 MB，占用约 1.2 GB。')
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        self.download_button = QPushButton('下载并启用')
        self.download_button.setIcon(icon('download'))
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton('取消下载')
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)
        self.detail = QLabel('')
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setObjectName('muted')
        layout.addWidget(self.detail)
        layout.addStretch()
        self.refresh()

    def refresh(self):
        try:
            path = find_libreoffice()
        except ValueError:
            self.status.setText('未启用')
            self.download_button.setEnabled(True)
        else:
            self.status.setText('已就绪')
            self.download_button.setEnabled(False)
            self.detail.setText(str(path))

    def start_download(self):
        if self.busy:
            return
        self.busy = True
        self.download_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.detail.clear()
        self.status.setText('正在连接')
        self.worker = RuntimeWorker(self)
        self.worker.progress.connect(self.on_progress)
        self.worker.ready.connect(lambda path: self.detail.setText(path))
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(lambda: self.status.setText('下载已取消'))
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, phase, current, total):
        self.status.setText(phase)
        if phase == '正在下载' and total:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, round(current * 100 / total)))
            self.detail.setText(f'{current / 1024**2:.1f} / {total / 1024**2:.1f} MB')
        else:
            self.progress.setRange(0, 0)
        if phase == '正在准备引擎':
            self.cancel_button.setText('取消启用')

    def cancel_download(self):
        if self.worker:
            self.worker.cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.detail.setText('正在取消；文件准备期间会等待当前操作结束。')

    def on_failed(self, message):
        self.status.setText('启用失败')
        self.detail.setText(message)

    def on_finished(self):
        self.busy = False
        self.progress.hide()
        self.cancel_button.hide()
        self.cancel_button.setText('取消下载')
        self.download_button.setEnabled(True)
        try:
            find_libreoffice()
        except ValueError:
            self.download_button.setText('下载并启用')
        else:
            self.status.setText('已就绪')
            self.download_button.setEnabled(False)
        self.worker.deleteLater()
        self.worker = None
