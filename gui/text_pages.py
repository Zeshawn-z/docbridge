"""Simple text workflows. Each page owns its input, settings, result and worker."""
from pathlib import Path
import re

from PySide6.QtCore import Qt, QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QPushButton, QFileDialog, QDialog, QLineEdit,
    QProgressBar)

from docbridge_text import read_docx, write_docx, unwrap_markdown
from .conversion_page import card, label
from .icons import icon
from .text_worker import TextWorker


class TextPage(QWidget):
    def __init__(self, feature, parent=None):
        super().__init__(parent)
        self.feature = feature
        self.busy = False
        self.worker = None
        self.result = None
        self.options = None
        self.controls = []
        base = QVBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)
        self.workspace = QWidget()
        self.workspace.setObjectName('workspace')
        self.layout = QVBoxLayout(self.workspace)
        self.layout.setContentsMargins(28, 25, 28, 22)
        self.layout.setSpacing(17)
        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 150, 0)
        self.header.setMinimumHeight(40)
        title = label(feature.title, 'title')
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header.addWidget(title)
        header.addStretch()
        self.layout.addWidget(self.header)
        base.addWidget(self.workspace)

    def build_footer(self):
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.layout.addWidget(self.progress)
        self.status = label('就绪', 'muted', True)
        self.layout.addWidget(self.status)

    def run_operation(self, operation, on_success):
        if self.busy:
            return
        self.busy = True
        for control in self.controls:
            control.setEnabled(False)
        self.progress.show()
        self.status.setText('正在转换…')
        self.worker = TextWorker(operation, self)
        self.worker.succeeded.connect(on_success)
        self.worker.failed.connect(lambda message: self.status.setText('转换失败：' + message))
        self.worker.finished.connect(self.finish_operation)
        self.worker.start()

    def finish_operation(self):
        self.busy = False
        self.progress.hide()
        for control in self.controls:
            control.setEnabled(True)
        self.worker.deleteLater()
        self.worker = None
        self.update_actions()

    def set_result_status(self, text, warnings):
        self.status.setText(text + ('；' + '；'.join(warnings) if warnings else ''))


class PasteToWordPage(TextPage):
    def __init__(self, feature, parent=None):
        super().__init__(feature, parent)
        from .report_options import ReportOptions
        self.options = ReportOptions(self, text_only=True, overrides={'markdown.emphasis_as_bold': False})
        self.last_directory = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        frame, content = card()
        toolbar = QHBoxLayout()
        toolbar.addWidget(label('粘贴内容', 'sectionTitle'))
        toolbar.addStretch()
        self.paste_button = QPushButton('粘贴')
        self.paste_button.setIcon(icon('paste'))
        self.paste_button.clicked.connect(self.paste)
        self.clear_button = QPushButton('清空')
        self.clear_button.setObjectName('quiet')
        self.editor = QPlainTextEdit()
        self.clear_button.clicked.connect(self.editor.clear)
        toolbar.addWidget(self.paste_button)
        toolbar.addWidget(self.clear_button)
        content.addLayout(toolbar)
        self.editor.setPlaceholderText('在这里粘贴 AI 输出或 Markdown 文本。')
        self.editor.textChanged.connect(self.input_changed)
        content.addWidget(self.editor, 1)
        self.layout.addWidget(frame, 1)
        actions = QHBoxLayout()
        self.settings_button = self.options.details_button
        actions.addWidget(self.options)
        actions.addStretch()
        self.open_button = QPushButton('打开 Word')
        self.open_button.setIcon(icon('file'))
        self.open_button.clicked.connect(self.open_result)
        self.open_button.hide()
        actions.addWidget(self.open_button)
        self.convert_button = QPushButton('保存为 Word')
        self.convert_button.setObjectName('primary')
        self.convert_button.setIcon(icon('download', '#ffffff'))
        self.convert_button.clicked.connect(self.start)
        actions.addWidget(self.convert_button)
        self.layout.addLayout(actions)
        self.controls = [self.editor, self.paste_button, self.clear_button,
                         self.settings_button, self.convert_button, self.open_button]
        self.build_footer()
        self.update_actions()

    def paste(self):
        if not self.busy:
            self.editor.insertPlainText(QApplication.clipboard().text())

    def input_changed(self):
        self.result = None
        self.open_button.hide()
        self.status.setText('就绪')
        self.update_actions()

    def update_actions(self):
        self.convert_button.setEnabled(not self.busy and bool(self.editor.toPlainText().strip()))
        self.open_button.setVisible(self.result is not None)

    def edit_layout(self):
        self.options.show_advanced()

    def suggested_name(self):
        text = unwrap_markdown(self.editor.toPlainText())
        title = next((line.lstrip('#').strip() for line in text.splitlines() if line.startswith('# ')), '未命名文档')
        title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title).strip().rstrip('.')[:80] or '未命名文档'
        if title.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
            title = '文档_' + title
        return title + '.docx'

    def start(self):
        if self.busy or not self.editor.toPlainText().strip():
            return
        output, _ = QFileDialog.getSaveFileName(self, '保存 Word 文档',
            str(Path(self.last_directory) / self.suggested_name()), 'Word 文档 (*.docx)')
        if output:
            self.save_to(output)

    def save_to(self, output):
        if self.busy:
            return
        output = Path(output)
        if output.suffix.lower() != '.docx':
            output = Path(str(output) + '.docx')
        self.last_directory = str(output.parent)
        text, template, overrides = self.editor.toPlainText(), self.options.template_path(), self.options.overrides()
        self.run_operation(lambda: write_docx(text, output, template=template, overrides=overrides, overwrite=True), self.saved)

    def saved(self, result):
        self.result = result
        self.set_result_status('已保存：' + str(result.output), result.warnings)

    def open_result(self):
        if self.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result.output)))

    def add_files(self):
        self.paste()


class WordToTextPage(TextPage):
    def __init__(self, feature, parent=None):
        super().__init__(feature, parent)
        self.source = None
        self.setAcceptDrops(True)
        file_frame, file_layout = card()
        row = QHBoxLayout()
        self.select_button = QPushButton('选择 Word 文件')
        self.select_button.setIcon(icon('folder'))
        self.select_button.clicked.connect(self.add_files)
        row.addWidget(self.select_button)
        self.filename = QLineEdit()
        self.filename.setReadOnly(True)
        self.filename.setPlaceholderText('也可以拖入一个 Word 文件')
        row.addWidget(self.filename, 1)
        self.read_button = QPushButton('重新读取')
        self.read_button.setIcon(icon('convert'))
        self.read_button.clicked.connect(self.start)
        row.addWidget(self.read_button)
        file_layout.addLayout(row)
        self.layout.addWidget(file_frame)
        frame, content = card()
        toolbar = QHBoxLayout()
        toolbar.addWidget(label('Markdown 文本', 'sectionTitle'))
        toolbar.addStretch()
        self.copy_button = QPushButton('复制全部')
        self.copy_button.setObjectName('primary')
        self.copy_button.setIcon(icon('copy', '#ffffff'))
        self.copy_button.clicked.connect(self.copy)
        toolbar.addWidget(self.copy_button)
        content.addLayout(toolbar)
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText('选择 Word 文件后，文本会显示在这里。')
        content.addWidget(self.editor, 1)
        self.layout.addWidget(frame, 1)
        self.controls = [self.select_button, self.read_button, self.copy_button]
        self.build_footer()
        self.update_actions()

    def update_actions(self):
        self.read_button.setEnabled(not self.busy and self.source is not None)
        self.copy_button.setEnabled(not self.busy and bool(self.editor.toPlainText().strip()))

    def add_files(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, '选择 Word 文件', '', 'Word 文档 (*.docx *.doc)')
        if path:
            self.load_file(path)

    def load_file(self, path):
        if self.busy:
            return
        self.source = Path(path).resolve()
        self.filename.setText(str(self.source))
        self.result = None
        self.editor.clear()
        self.start()

    def start(self):
        if self.busy or self.source is None:
            return
        self.result = None
        self.editor.clear()
        source = self.source
        self.run_operation(lambda: read_docx(source), self.loaded)

    def loaded(self, result):
        self.result = result
        self.editor.setPlainText(result.markdown)
        self.set_result_status('读取完成' if result.markdown.strip() else '文档没有可复制的正文', result.warnings)

    def copy(self):
        if not self.busy and self.editor.toPlainText().strip():
            QApplication.clipboard().setText(self.editor.toPlainText())
            self.status.setText('已复制到剪贴板')

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if not self.busy and len(urls) == 1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in ('.docx', '.doc'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not self.busy and len(urls) == 1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in ('.docx', '.doc'):
            self.load_file(urls[0].toLocalFile())
            event.acceptProposedAction()
