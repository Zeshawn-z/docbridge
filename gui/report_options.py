"""A shared entry point and independent state for each page's layout dialog."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog
from md2docx.config import load_config
from .layout_editor import AdvancedOptions
from .icons import icon


class ReportOptions(QWidget):
    changed = Signal()

    def __init__(self, parent=None, *, text_only=False, overrides=None):
        super().__init__(parent)
        self.template = None
        self.advanced = dict(overrides or {})
        self.text_only = text_only
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.details_button = QPushButton('排版设置')
        self.details_button.setIcon(icon('settings'))
        self.details_button.clicked.connect(self.show_advanced)
        layout.addWidget(self.details_button)

    def template_path(self):
        return self.template

    def overrides(self):
        values = dict(self.advanced)
        if self.text_only:
            config = load_config(self.template, values)
            values['markdown.emphasis_as_bold'] = config['markdown']['emphasis_as_bold']
            mode = config.get('math', {}).get('mode', 'omml')
            values['math.mode'] = 'omml' if mode == 'image' else mode
        return values

    def show_advanced(self):
        dialog = AdvancedOptions(self.template, self.advanced, self, text_only=self.text_only)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.template = dialog.template
            self.advanced = dict(dialog.values)
            self.changed.emit()
