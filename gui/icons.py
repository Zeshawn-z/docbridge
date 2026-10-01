"""Small stroke icons rendered from SVG, independent of installed fonts."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    'paste': '<path d="M8 5H5v16h14V5h-3M8 3h8v5H8zM8 12h8M8 16h6"/>',
    'copy': '<path d="M8 8h12v13H8zM16 8V3H3v13h5"/>',
    'minimize': '<path d="M5 16h14"/>',
    'maximize': '<path d="M5 5h14v14H5z"/>',
    'restore': '<path d="M8 8h11v11H8zM5 15V5h10"/>',
    'close': '<path d="m6 6 12 12M18 6 6 18"/>',
    'convert': '<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
    'arrow': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    'file': '<path d="M14 3H5v18h14V8zM14 3v5h5M8 12h8M8 16h6"/>',
    'folder': '<path d="M3 6h6l2 2h10v12H3z"/>',
    'add': '<path d="M12 5v14M5 12h14"/>',
    'upload': '<path d="M12 16V3m-5 5 5-5 5 5M4 14v7h16v-7"/>',
    'download': '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    'trash': '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
    'font': '<path d="m3 20 6-16 6 16M5 15h8M16 12h5m-2-2v10"/>',
    'paragraph': '<path d="M14 4v16m4-16v16M18 4h-7a5 5 0 0 0 0 10h3"/>',
    'page': '<path d="M5 3h14v18H5zM8 7h8M8 11h8M8 15h8"/>',
    'list': '<path d="M9 6h12M9 12h12M9 18h12M3 5h1v3M3 11h2l-2 3h2M3 17h2v3H3"/>',
    'style': '<path d="m4 20 4-12 4 12M5 16h6m2-11 2-2 6 6-2 2zM13 5l-2 6 6-2"/>',
    'table': '<path d="M3 4h18v16H3zM3 9h18M3 14h18M9 4v16M15 4v16"/>',
    'image': '<path d="M3 3h18v18H3zM3 17l6-6 4 4 3-3 5 5"/><circle cx="15" cy="7" r="1.5"/>',
    'settings': '<path d="M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6"/>',
    'heading': '<path d="M5 4v16M17 4v16M5 12h12"/>',
}


def icon(name, color='#5c6c83', size=24):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
           f'stroke-linejoin="round">{PATHS[name]}</svg>')
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
