"""Navigation shell. Features own their conversion pages and task state."""
import sys
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QLabel, QPushButton, QStackedWidget, QMessageBox)
from .icons import icon
from .widgets import app_pixmap
from .styles import STYLES
from .window_chrome import FramelessWindow, WindowControls
from .conversion_page import ConversionPage
from .features import available_features


class MainWindow(FramelessWindow):
    def __init__(self, features=None):
        super().__init__()
        self.setWindowTitle('DocBridge')
        self.setWindowIcon(QIcon(app_pixmap(64)))
        self.resize(1280, 900)
        self.setMinimumSize(1080, 760)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLES)
        self.pages = {}
        self.mode_buttons = {}
        self.mode = None
        self.build_ui(tuple(features) if features is not None else available_features())
        self.enable_resize_tracking()
        QShortcut(QKeySequence('Ctrl+O'), self, activated=lambda: self.current_page.add_files())
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=lambda: self.current_page.start())
        QShortcut(QKeySequence('Escape'), self, activated=self.close)

    @property
    def current_page(self):
        return self.pages[self.mode]

    @property
    def busy(self):
        return any(page.busy or getattr(getattr(page, 'options', None), 'busy', False) for page in self.pages.values())

    def build_ui(self, features):
        if not features or len({f.key for f in features}) != len(features):
            raise ValueError('转换功能必须有唯一标识，且至少提供一个功能。')
        central = QWidget()
        central.setObjectName('appSurface')
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        sidebar = QFrame()
        self.sidebar = sidebar
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 26, 16, 22)
        side.setSpacing(15)
        logo = QLabel()
        logo.setPixmap(self.windowIcon().pixmap(42, 42))
        logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        brand_header = QWidget()
        brand_layout = QHBoxLayout(brand_header)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(10)
        brand_layout.addWidget(logo)
        brand = QLabel('DocBridge')
        brand.setObjectName('brand')
        brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        brand_layout.addWidget(brand)
        brand_layout.addStretch()
        side.addWidget(brand_header)
        self.register_drag_area(brand_header)
        side.addSpacing(30)
        self.register_drag_area(sidebar)
        self.page_stack = QStackedWidget()
        for feature in features:
            create_page = getattr(feature, 'create_page', None)
            page = create_page(self) if create_page else ConversionPage(feature, self)
            self.pages[feature.key] = page
            self.register_drag_area(page.header)
            self.page_stack.addWidget(page)
            button = QPushButton(feature.title)
            button.setIcon(icon(feature.icon_name, '#a9bedf'))
            button.setCheckable(True)
            button.setObjectName('navigation')
            button.clicked.connect(lambda _checked, key=feature.key: self.switch_mode(key))
            self.mode_buttons[feature.key] = button
            side.addWidget(button)
        side.addStretch()
        content.addWidget(sidebar)
        content.addWidget(self.page_stack, 1)
        layout.addLayout(content, 1)
        self.window_controls = WindowControls(self)
        self.window_controls.setParent(central)
        self.position_controls()
        self.sync_corner_style()
        self.switch_mode(features[0].key)

    def position_controls(self):
        if hasattr(self, 'window_controls'):
            self.window_controls.move(self.width() - self.window_controls.width() - 20, 23)
            self.window_controls.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_controls()

    def switch_mode(self, mode):
        if mode not in self.pages:
            raise ValueError(f'未知功能：{mode}')
        self.mode = mode
        self.page_stack.setCurrentWidget(self.pages[mode])
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode)
        self.window_controls.raise_()

    def dragEnterEvent(self, event):
        self.current_page.dragEnterEvent(event)

    def dropEvent(self, event):
        self.current_page.dropEvent(event)

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, '任务正在运行', '请停止转换或取消引擎下载，等待当前操作完成后关闭窗口。')
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('DocBridge')
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    return app.exec()
