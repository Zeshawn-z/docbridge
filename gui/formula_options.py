"""Formula output controls. No conversion code or document-engine state."""
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox


class FormulaOptions(QWidget):
    def __init__(self, target, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox()
        choices = ([('Word 可编辑公式', 'omml'),
                    ('PNG 图片（KaTeX）', 'image'), ('LaTeX 源码', 'text')] if target == 'word'
                   else [('LaTeX', 'latex'), ('PNG 图片（KaTeX）', 'image')])
        for title, value in choices:
            self.mode.addItem(title, value)
        form.addRow('公式格式', self.mode)
        self.mode.setToolTip('图片由内置 KaTeX 和本机 Edge / Chrome 离线渲染。')

    def values(self):
        mode = self.mode.currentData()
        return {'math_mode': mode} if mode is not None else {}
