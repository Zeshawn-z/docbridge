"""Reusable task view. Every instance owns its widgets, queue, results and worker."""
from __future__ import annotations
import html
import re
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import (QWidget, QAbstractItemView, QCheckBox, QFileDialog,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextBrowser, QPlainTextEdit, QVBoxLayout)
from .file_inputs import collect_files
from .features.base import ConversionFeature
from .icons import icon
from .task_worker import ConversionWorker

def label(text, name=None, wrap=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def card():
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


class ConversionPage(QWidget):
    def __init__(self, feature: ConversionFeature, parent=None):
        super().__init__(parent)
        self.feature = feature
        self.had_run = False
        self.files = []
        self.rows = {}
        self.results = {}
        self.worker = None
        self.busy = False
        self.completed = 0
        self.mode = feature.key
        self.setAcceptDrops(True)
        self.build_ui()
        self.update_ui()

    def build_ui(self):
        base = QVBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)
        workspace = QWidget()
        self.workspace = workspace
        workspace.setObjectName('workspace')
        main = QVBoxLayout(workspace)
        main.setContentsMargins(28, 25, 28, 22)
        main.setSpacing(17)

        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 150, 0)
        self.header.setMinimumHeight(40)
        self.title_label = label('', 'title')
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header.addWidget(self.title_label)
        header.addStretch()
        main.addWidget(self.header)
        body = QHBoxLayout()
        body.setSpacing(17)
        left = QVBoxLayout()
        left.setSpacing(17)
        file_card, files_layout = card()
        toolbar = QHBoxLayout()
        toolbar.addWidget(label('待转换文件', 'sectionTitle'))
        self.count = label('0 个文件', 'count')
        toolbar.addWidget(self.count)
        toolbar.addStretch()
        self.remove_button = QPushButton('移除')
        self.clear_button = QPushButton('清空')
        for button in (self.remove_button, self.clear_button):
            button.setObjectName('quiet')
            toolbar.addWidget(button)
        files_layout.addLayout(toolbar)
        addbar = QHBoxLayout()
        self.add_button = QPushButton('添加文件')
        self.add_button.setIcon(icon('add'))
        self.folder_button = QPushButton('添加目录')
        self.folder_button.setIcon(icon('folder'))
        addbar.addWidget(self.add_button)
        addbar.addWidget(self.folder_button)
        addbar.addStretch()
        files_layout.addLayout(addbar)
        self.file_stack = QStackedWidget()
        empty = QFrame()
        empty.setObjectName('drop')
        drop = QVBoxLayout(empty)
        drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_icon = QLabel()
        drop_icon.setPixmap(icon('upload', '#7394d2', 44).pixmap(44, 44))
        drop.addWidget(drop_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        for text, name in [('拖入文件或文件夹', 'dropTitle')]:
            item = label(text, name)
            item.setAlignment(Qt.AlignmentFlag.AlignCenter)
            drop.addWidget(item)
        drop.addSpacing(15)
        self.select_button = select = QPushButton('选择文件')
        select.clicked.connect(self.add_files)
        drop.addWidget(select, alignment=Qt.AlignmentFlag.AlignCenter)
        self.file_stack.addWidget(empty)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['文件名', '所在目录', '状态'])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 105)
        self.table.itemSelectionChanged.connect(self.preview_selected)
        self.file_stack.addWidget(self.table)
        files_layout.addWidget(self.file_stack, 1)
        left.addWidget(file_card, 3)
        preview_card, preview_layout = card()
        preview_layout.setContentsMargins(14, 7, 14, 12)
        self.tabs = QTabWidget()
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setOpenLinks(False)
        self.preview.anchorClicked.connect(lambda url: self.preview.scrollToAnchor(url.fragment()) if url.fragment() else None)
        self.preview.document().setDefaultStyleSheet('h1 { margin-top: 8px; margin-bottom: 14px; } h2 { margin-top: 14px; margin-bottom: 8px; } p { margin-top: 6px; margin-bottom: 8px; }')
        self.preview.clear()
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setFont(QFont('Consolas', 10))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.tabs.addTab(self.preview, '结果预览')
        self.tabs.addTab(self.source, '源码')
        self.tabs.addTab(self.log, '日志')
        preview_layout.addWidget(self.tabs)
        self.open_result_button = QPushButton('打开选中结果')
        self.open_result_button.clicked.connect(self.open_result)
        preview_layout.addWidget(self.open_result_button, alignment=Qt.AlignmentFlag.AlignRight)
        left.addWidget(preview_card, 2)
        body.addLayout(left, 1)
        right = QVBoxLayout()
        right.setSpacing(17)
        settings_card, settings_shell = card()
        settings_shell.setContentsMargins(14, 7, 14, 16)
        self.settings_tabs = QTabWidget()
        settings_shell.addWidget(self.settings_tabs)
        output_page = QWidget()
        settings = QVBoxLayout(output_page)
        settings.setContentsMargins(6, 12, 6, 8)
        settings.setSpacing(8)
        settings_card.setFixedWidth(326)
        settings.addWidget(label('输出设置', 'sectionTitle'))
        settings.addSpacing(7)
        settings.addWidget(label('保存位置', 'muted'))
        self.output = QLineEdit()
        self.output.setPlaceholderText('原文件所在目录（默认）')
        self.output.setCursorPosition(0)
        self.output.setToolTip('留空保存到原文件所在目录。')
        settings.addWidget(self.output)
        self.browse_button = QPushButton('选择输出目录…')
        settings.addWidget(self.browse_button)
        self.output_hint = label('', 'muted', True)
        settings.addWidget(self.output_hint)
        settings.addSpacing(8)
        self.overwrite = QCheckBox('覆盖已有转换结果')
        settings.addWidget(self.overwrite)
        self.overwrite.setToolTip('未勾选时，重名结果自动添加编号。')
        create_output_options = getattr(self.feature, 'create_output_options', None)
        self.output_options = create_output_options(self) if create_output_options else None
        if self.output_options is not None:
            settings.addSpacing(8)
            settings.addWidget(self.output_options)
        settings.addSpacing(12)
        settings.addStretch()
        mode_page = QWidget()
        mode_layout = QVBoxLayout(mode_page)
        mode_layout.setContentsMargins(6, 12, 6, 8)
        self.options = self.feature.create_options(self)
        if self.options is not None:
            mode_layout.addWidget(self.options)
        mode_layout.addStretch()
        if self.options is not None:
            self.settings_tabs.addTab(mode_page, self.feature.settings_label)
        self.settings_tabs.addTab(output_page, '输出')
        self.settings_tabs.setCurrentIndex(getattr(self.feature, 'default_settings_tab', 0))
        right.addWidget(settings_card, 1)
        conversion_card, conversion = card()
        conversion.setSpacing(9)
        conversion_card.setFixedWidth(326)
        self.summary = label('待转换', 'summary', True)
        conversion.addWidget(self.summary)
        self.detail = label('尚未添加文件', 'muted', True)
        conversion.addWidget(self.detail)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        conversion.addWidget(self.progress)
        self.convert_button = QPushButton('开始转换')
        self.convert_button.setObjectName('primary')
        self.convert_button.setIcon(icon('arrow', '#ffffff'))
        conversion.addWidget(self.convert_button)
        self.cancel_button = QPushButton('当前文件完成后停止')
        self.cancel_button.hide()
        conversion.addWidget(self.cancel_button)
        self.open_button = QPushButton('打开输出目录')
        self.open_button.setIcon(icon('folder'))
        conversion.addWidget(self.open_button)
        right.addWidget(conversion_card)
        body.addLayout(right)
        main.addLayout(body, 1)
        footer = QHBoxLayout()
        self.status = label('就绪', 'muted')
        footer.addWidget(self.status)
        footer.addStretch()

        main.addLayout(footer)
        base.addWidget(workspace, 1)
        self.controls = [self.add_button, self.folder_button, self.remove_button,
                         self.clear_button, self.output, self.browse_button, self.overwrite,
                         self.convert_button, select]
        if self.options is not None and getattr(self.options, 'lock_during_conversion', True):
            self.controls.append(self.options)
        if self.output_options is not None:
            self.controls.append(self.output_options)
        self.add_button.clicked.connect(self.add_files)
        self.folder_button.clicked.connect(self.add_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_files)
        self.browse_button.clicked.connect(self.choose_output)
        self.convert_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.stop)
        self.open_button.clicked.connect(self.open_output)

    def append_files(self, paths):
        if self.busy:
            return
        for item in paths:
            path = Path(item).resolve()
            if (not path.is_file() or path.suffix.lower() not in self.extensions() or
                    path.name.startswith('~$') or str(path) in self.rows):
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.rows[str(path)] = row
            self.files.append(path)
            self.had_run = False
            self.convert_button.setText('开始转换')
            for column, text in enumerate((path.name, str(path.parent), '等待转换')):
                cell = QTableWidgetItem(text)
                cell.setToolTip(str(path) if column < 2 else text)
                self.table.setItem(row, column, cell)
            self.set_status(str(path), '等待转换')
        self.refresh_count()

    def refresh_count(self):
        self.count.setText(f'{len(self.files)} 个文件')
        self.file_stack.setCurrentIndex(1 if self.files else 0)
        self.summary.setText(f'{len(self.files)} 个文件待转换' if self.files else '待转换')
        self.detail.setText('已添加文件' if self.files else '尚未添加文件')
        self.status.setText(f'已选择 {len(self.files)} 个文件')

    def add_files(self):
        if self.busy:
            return
        file_filter = self.feature.file_filter
        paths, _ = QFileDialog.getOpenFileNames(self, '选择输入文件', '', file_filter)
        self.append_files(paths)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择输入目录（包含子目录）')
        if folder:
            self.import_paths([folder])

    def import_paths(self, paths):
        try:
            self.append_files(collect_files(paths, recursive=True, extensions=self.extensions()))
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, '添加失败', str(exc))

    def remove_selected(self):
        if self.busy:
            return
        selected = {index.row() for index in self.table.selectionModel().selectedRows()}
        for row in sorted(selected, reverse=True):
            path = self.files.pop(row)
            self.results.pop(str(path), None)
            self.table.removeRow(row)
        self.rows = {str(path): i for i, path in enumerate(self.files)}
        if not self.files:
            self.clear_files()
        else:
            self.refresh_count()

    def clear_files(self):
        if self.busy:
            return
        self.had_run = False
        self.convert_button.setText('开始转换')
        self.log.clear()
        self.files.clear()
        self.rows.clear()
        self.results.clear()
        self.table.setRowCount(0)
        self.source.clear()
        self.preview.clear()
        self.progress.setValue(0)
        self.completed = 0
        self.detail.setText('尚未添加文件')
        self.refresh_count()

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(self, '选择输出目录', self.output.text())
        if folder:
            self.output.setText(folder)

    def open_output(self):
        text = self.output.text().strip()
        selected = self.table.selectionModel().selectedRows()
        selected_result = self.results.get(str(self.files[selected[0].row()])) if selected and selected[0].row() < len(self.files) else None
        path = (self.result_path(selected_result).parent if selected_result else
                Path(text).expanduser() if text else self.files[0].parent if self.files else None)
        if path is None or not path.is_dir():
            QMessageBox.information(self, '输出目录', '目录尚未创建，请先转换文件。')
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
            QMessageBox.warning(self, '打开失败', '无法打开输出目录。')

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.busy:
            self.import_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
            event.acceptProposedAction()

    def set_status(self, key, text):
        row = self.rows[key]
        colors = {'等待转换': ('#eef2f7', '#8793a5'), '转换中': ('#eaf0ff', '#3669e8'),
                  '完成': ('#e8f7f0', '#278765'), '完成（有提示）': ('#fff4df', '#a77c29'),
                  '失败': ('#feeeee', '#c65b61'), '已停止': ('#eef2f7', '#8793a5')}
        background, foreground = colors.get(text, colors['等待转换'])
        badge = label(text)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(28)
        badge.setStyleSheet(f'background:{background};color:{foreground};border-radius:7px;padding:4px;font-size:12px;')
        holder = QWidget()
        holder.setStyleSheet('background: white;')
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(badge)
        self.table.setCellWidget(row, 2, holder)
        self.table.item(row, 2).setText(text)

    def start(self):
        if self.busy:
            return
        if not self.files:
            QMessageBox.information(self, '选择文件', '请先添加待转换文件。')
            return
        self.busy = True
        self.completed = 0
        self.results.clear()
        self.source.clear()
        self.preview.clear()
        self.log.clear()
        for path in self.files:
            self.set_status(str(path), '等待转换')
        for control in self.controls:
            control.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText('当前文件完成后停止')
        self.cancel_button.show()
        self.progress.setRange(0, len(self.files))
        self.progress.setValue(0)
        self.convert_button.setText('正在转换…')
        self.summary.setText('转换进行中')
        settings = dict(self.feature.read_options(self.options))
        if self.output_options is not None:
            settings.update(self.output_options.values())
        self.worker = ConversionWorker(self.files, self.output.text().strip() or None, self.overwrite.isChecked(),
                                       self.feature.convert, settings, self)
        self.worker.log_message.connect(self.log.appendPlainText)
        self.worker.file_started.connect(self.on_started)
        self.worker.file_result.connect(self.on_result)
        self.worker.file_error.connect(self.on_error)
        self.worker.batch_done.connect(self.on_done)
        self.worker.finished.connect(self.unlock)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def on_started(self, key):
        self.set_status(key, '转换中')
        self.detail.setText(f'{self.completed + 1} / {len(self.files)}  {Path(key).name}')
        self.status.setText(f'正在转换：{Path(key).name}')

    def on_result(self, key, result):
        self.results[key] = result
        self.set_status(key, '完成（有提示）' if result.warnings else '完成')
        self.log.appendPlainText(f'完成：{self.result_path(result)}\n图片：{result.image_count} 张')
        for warning in result.warnings:
            self.log.appendPlainText('  提示：' + warning)
        self.completed += 1
        self.progress.setValue(self.completed)
        self.table.selectRow(self.rows[key])
        self.preview_selected()

    def on_error(self, key, error):
        self.set_status(key, '失败')
        self.log.appendPlainText(f'失败：{key}\n  {error}')
        self.completed += 1
        self.progress.setValue(self.completed)

    def on_done(self, success, failed, total, stopped):
        for path in self.files:
            row = self.rows[str(path)]
            if self.table.item(row, 2).text() == '等待转换':
                self.set_status(str(path), '已停止')
        self.summary.setText('本批转换已停止' if stopped and self.completed < total else '转换完成')
        self.detail.setText(f'成功 {success}，失败 {failed}，未处理 {total - self.completed}')
        self.status.setText(f'{self.summary.text()}：{self.detail.text()}')
        if failed and not success:
            self.tabs.setCurrentWidget(self.log)

    def unlock(self):
        self.busy = False
        self.had_run = True
        for control in self.controls:
            control.setEnabled(True)
        self.cancel_button.hide()
        self.convert_button.setText('再次转换')

    def stop(self):
        if self.worker and self.busy:
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText('等待当前文件完成…')

    def preview_selected(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected or selected[0].row() >= len(self.files):
            return
        key = str(self.files[selected[0].row()])
        result = self.results.get(key)
        if not result:
            self.source.clear()
            self.preview.clear()
            return
        try:
            preview_path = self.feature.preview_path(result)
            text = preview_path.read_text(encoding='utf-8-sig')
            self.source.setPlainText(text)
            self.preview.document().setBaseUrl(QUrl.fromLocalFile(str(preview_path.parent) + '/'))
            self.preview.setSearchPaths([str(preview_path.parent)])
            from .formula_preview import show_markdown
            show_markdown(self.preview, text)
            self.restore_preview_anchors(text)
        except OSError as exc:
            self.preview.setHtml('<p>无法读取结果：' + html.escape(str(exc)) + '</p>')

    def restore_preview_anchors(self, markdown):
        # Qt's Markdown parser discards empty HTML anchors. Restore heading
        # anchors in the QTextDocument so TOC links also work inside the GUI.
        anchors, pending, heading_index = {}, [], 0
        for line in markdown.splitlines():
            match = re.fullmatch(r'<a id="([^"]+)"></a>', line)
            if match:
                pending.append(html.unescape(match[1]))
            elif re.match(r'^#{1,6}\s', line):
                anchors[heading_index] = pending
                heading_index += 1
                pending = []
            elif line.strip():
                pending = []
        block, index = self.preview.document().begin(), 0
        while block.isValid():
            if block.blockFormat().headingLevel():
                names = anchors.get(index, [])
                if names:
                    cursor = QTextCursor(block)
                    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                    fmt = QTextCharFormat()
                    fmt.setAnchor(True)
                    fmt.setAnchorNames(names)
                    cursor.mergeCharFormat(fmt)
                index += 1
            block = block.next()

    def extensions(self):
        return self.feature.extensions

    def result_path(self, result):
        return self.feature.result_path(result)

    def open_result(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        result = self.results.get(str(self.files[selected[0].row()]))
        if result:
            path = self.result_path(result)
            if not path.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                QMessageBox.warning(self, '打开失败', '结果文件已移动，或系统没有可打开它的程序。')

    def update_ui(self):
        self.title_label.setText(self.feature.title)
        self.select_button.setText(self.feature.select_label)
        self.output_hint.setText(self.feature.output_hint)
        self.tabs.setTabText(0, self.feature.preview_label)
        self.open_result_button.setText(self.feature.open_label)
