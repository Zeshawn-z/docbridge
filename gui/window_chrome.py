"""Frameless window controls and OS-supported dragging/resizing."""
from PySide6.QtCore import Qt, QEvent, QSize
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QMainWindow, QApplication, QWidget
from .icons import icon


class WindowButton(QPushButton):
    def __init__(self, glyph, title, callback, parent=None):
        super().__init__(parent)
        self.glyph = glyph
        self.setObjectName('windowClose' if glyph == 'close' else 'windowControl')
        self.setFixedSize(46, 40)
        self.setIconSize(QSize(18, 18))
        self.setToolTip(title)
        self.setAccessibleName(title)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIcon(icon(glyph))
        self.clicked.connect(callback)

    def enterEvent(self, event):
        if self.glyph == 'close':
            self.setIcon(icon('close', '#ffffff'))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(icon(self.glyph))
        super().leaveEvent(event)


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__(window)
        self.host = window
        self.anchor = None
        self.setObjectName('titleBar')
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 2, 0)
        layout.setSpacing(8)
        mark = QLabel()
        mark.setPixmap(window.windowIcon().pixmap(22, 22))
        title = QLabel(window.windowTitle())
        for label in (mark, title):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(label)
        layout.addStretch()
        self.minimize = WindowButton('minimize', '最小化', window.showMinimized, self)
        self.maximize = WindowButton('maximize', '最大化', self.toggle_maximized, self)
        self.close_button = WindowButton('close', '关闭', window.close, self)
        for button in (self.minimize, self.maximize, self.close_button):
            layout.addWidget(button)

    def toggle_maximized(self):
        if self.host.isMaximized():
            self.host.showNormal()
        else:
            self.host.showMaximized()
        self.sync_state()

    def sync_state(self):
        maximized = self.host.isMaximized()
        self.maximize.glyph = 'restore' if maximized else 'maximize'
        self.maximize.setIcon(icon(self.maximize.glyph))
        title = '还原' if maximized else '最大化'
        self.maximize.setToolTip(title)
        self.maximize.setAccessibleName(title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.host.windowHandle()
            if not handle or not handle.startSystemMove():
                self.anchor = event.globalPosition().toPoint() - self.host.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.anchor is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.host.move(event.globalPosition().toPoint() - self.anchor)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.anchor = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class FramelessWindow(QMainWindow):
    RESIZE_MARGIN = 6

    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._resize_widget = None
        self._resize_cursor = None
        QApplication.instance().installEventFilter(self)

    def enable_resize_tracking(self):
        self.setMouseTracking(True)
        for widget in self.findChildren(QWidget):
            widget.setMouseTracking(True)

    def resize_edges(self, point):
        if self.isMaximized() or self.isFullScreen():
            return Qt.Edge(0)
        edges = Qt.Edge(0)
        margin = self.RESIZE_MARGIN
        if point.x() < margin:
            edges |= Qt.Edge.LeftEdge
        elif point.x() >= self.width() - margin:
            edges |= Qt.Edge.RightEdge
        if point.y() < margin:
            edges |= Qt.Edge.TopEdge
        elif point.y() >= self.height() - margin:
            edges |= Qt.Edge.BottomEdge
        return edges

    def eventFilter(self, watched, event):
        if not isinstance(watched, QWidget) or watched.window() is not self:
            return False
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            point = self.mapFromGlobal(event.globalPosition().toPoint())
            edges = self.resize_edges(point)
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and edges:
                handle = self.windowHandle()
                if handle and handle.startSystemResize(edges):
                    return True
            if event.type() == QEvent.Type.MouseMove:
                if self._resize_widget is not None:
                    self._resize_widget.setCursor(self._resize_cursor)
                    self._resize_widget = None
                if edges:
                    self._resize_widget, self._resize_cursor = watched, watched.cursor()
                    horizontal = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
                    vertical = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
                    if horizontal and vertical:
                        diagonal = edges in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
                        cursor = Qt.CursorShape.SizeFDiagCursor if diagonal else Qt.CursorShape.SizeBDiagCursor
                    else:
                        cursor = Qt.CursorShape.SizeHorCursor if horizontal else Qt.CursorShape.SizeVerCursor
                    watched.setCursor(cursor)
        return False

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, 'title_bar'):
            self.title_bar.sync_state()
