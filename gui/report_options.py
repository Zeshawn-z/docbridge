"""Template-preserving report controls and a native Qt advanced editor."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                              QComboBox, QCheckBox, QPushButton, QFileDialog, QDialog,
                              QMessageBox)

from md2docx.config import load_config
from . import config_bridge as bridge
from .layout_editor import AdvancedOptions, choice
from .icons import icon


class ReportOptions(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.advanced = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        title = QLabel('排版模板')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        self.template_combo = QComboBox()
        for spec in bridge.template_choices():
            self.template_combo.addItem(spec['label'], spec['path'])
        layout.addWidget(self.template_combo)
        self.template_combo.currentIndexChanged.connect(self.update_template_desc)
        self.update_template_desc()
        row = QHBoxLayout()
        custom = QPushButton('导入模板')
        custom.setIcon(icon('file'))
        custom.clicked.connect(self.import_template)
        details = QPushButton('排版设置')
        details.setIcon(icon('settings'))
        self.details_button = details
        details.clicked.connect(self.show_advanced)
        row.addWidget(custom)
        row.addWidget(details)
        layout.addLayout(row)
        form = QFormLayout()
        self.body_size = choice([(size, size) for size in bridge.FONT_SIZE_CHOICES])
        self.line_spacing = choice([(title + ' 倍', value) for title, value in bridge.LINE_SPACING_CHOICES])
        form.addRow('正文字号', self.body_size)
        form.addRow('全局行距', self.line_spacing)
        layout.addLayout(form)
        self.toc = QCheckBox('插入目录')
        self.page_number = QCheckBox('页脚页码')
        self.mermaid = QCheckBox('渲染 Mermaid 图表')
        for checkbox in (self.toc, self.page_number, self.mermaid):
            checkbox.setTristate(True)
            checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
            checkbox.setToolTip('横线：沿用模板；勾选：开启；空框：关闭。')
        flags = QHBoxLayout()
        flags.addWidget(self.toc)
        flags.addWidget(self.page_number)
        layout.addLayout(flags)
        layout.addWidget(self.mermaid)
        self.modified = QLabel('使用模板设置')
        self.modified.setObjectName('muted')
        self.modified.setWordWrap(True)
        self.modified.hide()
        layout.addWidget(self.modified)

    def template_path(self):
        return self.template_combo.currentData()

    def update_template_desc(self):
        from pathlib import Path
        path = self.template_path()
        name = Path(path).name if path else 'default.yaml'
        self.template_combo.setToolTip(bridge.TEMPLATE_DESC.get(name, '自定义排版模板').replace(' · ', '，'))

    def import_template(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入排版模板', '', 'YAML 模板 (*.yaml *.yml)')
        if path:
            try:
                load_config(path)
            except Exception as exc:
                QMessageBox.warning(self, '模板无效', str(exc))
                return
            self.template_combo.addItem('自定义：' + path.rsplit('/', 1)[-1], path)
            self.template_combo.setCurrentIndex(self.template_combo.count() - 1)

    def quick_overrides(self):
        def flag(checkbox):
            state = checkbox.checkState()
            return None if state == Qt.CheckState.PartiallyChecked else state == Qt.CheckState.Checked
        quick = bridge.build_overrides(body_size=self.body_size.currentData(), line_spacing=self.line_spacing.currentData(),
                                       toc=flag(self.toc), page_number=flag(self.page_number), mermaid=flag(self.mermaid))
        return quick

    def overrides(self):
        return {**self.quick_overrides(), **self.advanced}

    def show_advanced(self):
        dialog = AdvancedOptions(self.template_path(), self.advanced, self, inherited=self.quick_overrides())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.advanced = dialog.values
            self.modified.setVisible(bool(self.advanced))
            self.modified.setText(f'{len(self.advanced)} 项详细参数已修改' if self.advanced else '使用模板设置')
