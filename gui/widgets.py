"""自绘控件集合。

为了做到"无边框、无分隔线、悬停有平滑过渡"，按钮、下拉、复选、分段控件
都改成自己画，QSS 只负责字体和窗口外沿。
"""

from __future__ import annotations

import os

from PySide6.QtCore import (QEvent, QPoint, QRectF, QSize, Qt, Property, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QSizePolicy, QVBoxLayout, QWidget)

from . import animations as anim
from .theme import Color, Font, Motion, Radius, Space

# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------


def _c(value) -> QColor:
    return value if isinstance(value, QColor) else QColor(value)


def mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
        round(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def draw_chevron(painter: QPainter, center: QPoint, size: float, color: QColor,
                 width: float = 1.6) -> None:
    """画一个向下的折角箭头，替代系统下拉箭头。"""
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    half = size / 2
    path = QPainterPath()
    path.moveTo(center.x() - half, center.y() - half * 0.45)
    path.lineTo(center.x(), center.y() + half * 0.5)
    path.lineTo(center.x() + half, center.y() - half * 0.45)
    painter.drawPath(path)


# --------------------------------------------------------------------------
# 按钮
# --------------------------------------------------------------------------


class SolidButton(QFrame):
    """实心按钮。primary 用主色，ghost 用透明底 + 主色文字。"""

    clicked = Signal()

    def __init__(self, text: str, *, kind: str = "primary",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._kind = kind
        self._text = text
        self._pressed = False
        self._hover = False
        self._base, self._hover_c, self._press_c, self._text_c = self._palette(kind)
        self._bg = QColor(self._base)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setFixedHeight(34 if kind != "ghost" else 26)

    @staticmethod
    def _palette(kind: str):
        if kind == "primary":
            return (Color.ACCENT, Color.ACCENT_HOVER, Color.ACCENT_PRESSED,
                    Color.TEXT_ON_ACCENT)
        if kind == "ghost":
            return (Color.BG, Color.SUNKEN, Color.HOVER, Color.ACCENT)
        return (Color.SUNKEN, Color.HOVER, Color.ACTIVE, Color.TEXT)

    # -- 可动画属性 ------------------------------------------------------
    def _get_bg(self) -> QColor:
        return self._bg

    def _set_bg(self, value: QColor) -> None:
        self._bg = value
        self.update()

    bgColor = Property(QColor, _get_bg, _set_bg)

    # -- 交互 ------------------------------------------------------------
    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        anim.animate_color(self, "hover", self._bg, _c(self._hover_c))

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self._pressed = False
        anim.animate_color(self, "hover", self._bg, _c(self._base))

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._pressed = True
            anim.animate_color(self, "press", self._bg, _c(self._press_c),
                               duration=80)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        was_pressed = self._pressed
        self._pressed = False
        target = self._hover_c if self._hover else self._base
        anim.animate_color(self, "hover", self._bg, _c(target))
        if was_pressed and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """交给 Qt 维护启用状态，只额外处理鼠标指针与重绘。

        不自己维护 _enabled 副本：Qt 内部（父级禁用、事件过滤）不会走 Python
        重载，两份状态迟早会对不上。
        """
        QFrame.setEnabled(self, enabled)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.update()

    def changeEvent(self, event):  # noqa: N802
        if event.type() == QEvent.EnabledChange:
            self.setCursor(Qt.PointingHandCursor if self.isEnabled() else Qt.ArrowCursor)
            self.update()
        super().changeEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self._label_font())
        width = metrics.horizontalAdvance(self._text) + (40 if self._kind == "primary" else 24)
        return QSize(max(width, 84), self.height())

    def _label_font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(Font.SIZE_BODY)
        font.setWeight(QFont.DemiBold if self._kind == "primary" else QFont.Medium)
        return font

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        enabled = self.isEnabled()
        background = self._bg if enabled else mix(self._bg, _c(Color.BG), 0.55)
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, Radius.CONTROL, Radius.CONTROL)

        text_color = _c(self._text_c)
        if not enabled:
            text_color = mix(text_color, _c(Color.BG), 0.3)
        painter.setPen(text_color)
        painter.setFont(self._label_font())
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        painter.end()


class IconButton(QFrame):
    """极简图标按钮：一条线或一个叉，悬停时底色浮起。"""

    clicked = Signal()

    MINIMIZE = "minimize"
    CLOSE = "close"
    REMOVE = "remove"
    FOLDER = "folder"
    REFRESH = "refresh"

    def __init__(self, glyph: str, *, size: int = 30, danger: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._glyph = glyph
        self._danger = danger
        self._hover = False
        self._bg = QColor(Qt.transparent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def _get_bg(self) -> QColor:
        return self._bg

    def _set_bg(self, value: QColor) -> None:
        self._bg = value
        self.update()

    bgColor = Property(QColor, _get_bg, _set_bg)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        target = Color.DANGER_SOFT if self._danger else Color.HOVER
        anim.animate_color(self, "hover", self._bg, QColor(target))

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        anim.animate_color(self, "hover", self._bg, QColor(Qt.transparent))

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._bg.alpha():
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._bg)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                                    Radius.SMALL, Radius.SMALL)
        color = QColor(Color.DANGER) if (self._danger and self._hover) else QColor(
            Color.TEXT_SECONDARY)
        if self._hover and not self._danger:
            color = QColor(Color.TEXT)
        painter.setPen(Qt.NoPen)
        rect = self.rect()
        cx, cy = rect.center().x() + 0.5, rect.center().y() + 0.5

        if self._glyph == self.MINIMIZE:
            pen = QPen(color, 1.4)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPoint(int(cx - 5), int(cy)), QPoint(int(cx + 5), int(cy)))
        elif self._glyph in (self.CLOSE, self.REMOVE):
            pen = QPen(color, 1.5)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            span = 4.4 if self._glyph == self.CLOSE else 3.8
            painter.drawLine(QPoint(int(cx - span), int(cy - span)),
                             QPoint(int(cx + span), int(cy + span)))
            painter.drawLine(QPoint(int(cx + span), int(cy - span)),
                             QPoint(int(cx - span), int(cy + span)))
        elif self._glyph == self.REFRESH:
            pen = QPen(color, 1.5)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(QRectF(cx - 5, cy - 5, 10, 10), 40 * 16, 280 * 16)
            painter.drawLine(QPoint(int(cx + 4), int(cy - 6)),
                             QPoint(int(cx + 5), int(cy - 1)))
        elif self._glyph == self.FOLDER:
            pen = QPen(color, 1.7)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(cx - 6, cy + 4)
            path.lineTo(cx - 6, cy - 4)
            path.lineTo(cx - 2, cy - 4)
            path.lineTo(cx - 0.5, cy - 2)
            path.lineTo(cx + 6, cy - 2)
            path.lineTo(cx + 6, cy + 4)
            path.closeSubpath()
            painter.drawPath(path)
        painter.end()


class TextButton(QFrame):
    """纯文字按钮，用于「添加文件」「清空」这类次级动作。"""

    clicked = Signal()

    def __init__(self, text: str, *, color: str = Color.ACCENT,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self._color = color
        self._hover = False
        self._bg = QColor(Qt.transparent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(26)
        # Fixed：默认的 Preferred 会在纵向布局里被拉满整行宽，文字看起来像居中
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _get_bg(self) -> QColor:
        return self._bg

    def _set_bg(self, value: QColor) -> None:
        self._bg = value
        self.update()

    bgColor = Property(QColor, _get_bg, _set_bg)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        anim.animate_color(self, "hover", self._bg, QColor(Color.SUNKEN), duration=110)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        anim.animate_color(self, "hover", self._bg, QColor(Qt.transparent), duration=110)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.clicked.emit()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self._font())
        return QSize(metrics.horizontalAdvance(self._text) + 16, 26)

    def _font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(Font.SIZE_SMALL)
        font.setWeight(QFont.Medium)
        return font

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._bg.alpha():
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._bg)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                                    Radius.SMALL, Radius.SMALL)
        painter.setPen(QColor(self._color))
        painter.setFont(self._font())
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        painter.end()


# --------------------------------------------------------------------------
# 复选框（自绘 + 打勾动画）
# --------------------------------------------------------------------------


class CheckBox(QFrame):
    toggled = Signal(bool)

    def __init__(self, text: str, *, checked: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self._checked = checked
        self._progress = 1.0 if checked else 0.0
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = value
        self.update()

    checkProgress = Property(float, _get_progress, _set_progress)

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, checked: bool, *, animate: bool = True) -> None:  # noqa: N802
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        target = 1.0 if checked else 0.0
        if animate:
            anim.animate_value(self, b"checkProgress", target, duration=170,
                               curve="OutBack")
        else:
            self._set_progress(target)
        self.toggled.emit(checked)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.setChecked(not self._checked)

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self.font())
        return QSize(metrics.horizontalAdvance(self._text) + 30, 24)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = QRectF(1, (self.height() - 16) / 2, 16, 16)
        fill = mix(QColor(Color.BG), QColor(Color.ACCENT), self._progress)
        border = QColor(Color.LINE_STRONG)
        if self._hover:
            border = QColor(Color.ACCENT_EDGE)
        border = mix(border, QColor(Color.ACCENT), self._progress)
        pen = QPen(border, 1.5)
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(box, 5, 5)

        if self._progress > 0.05:
            path = QPainterPath()
            path.moveTo(box.left() + 4.0, box.top() + 8.2)
            path.lineTo(box.left() + 7.0, box.top() + 11.2)
            path.lineTo(box.left() + 12.2, box.top() + 5.2)
            pen = QPen(QColor(Color.TEXT_ON_ACCENT), 1.8)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.save()
            painter.setClipRect(QRectF(box.left(), box.top(),
                                       box.width() * min(1.0, self._progress + 0.15),
                                       box.height()))
            painter.drawPath(path)
            painter.restore()

        painter.setPen(QColor(Color.TEXT if self._hover else Color.TEXT_SECONDARY))
        painter.drawText(QRectF(25, 0, self.width() - 25, self.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self._text)
        painter.end()


# --------------------------------------------------------------------------
# 分段控件（滑动指示器）
# --------------------------------------------------------------------------


class SegmentedControl(QFrame):
    """等宽分段选择。选中态是一块平滑滑动的白色指示块。"""

    changed = Signal(object)

    def __init__(self, items: list[tuple[str, object]], *, value=None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._items = list(items)
        self._index = 0
        self._indicator = 0.0
        if value is not None:
            for i, (_, val) in enumerate(self._items):
                if val == value:
                    self._index = i
                    break
        self._indicator = float(self._index)
        self._hover_index = -1
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._target = 0.0

    def _get_indicator(self) -> float:
        return self._indicator

    def _set_indicator(self, value: float) -> None:
        self._indicator = value
        self.update()

    indicatorPos = Property(float, _get_indicator, _set_indicator)

    def value(self):
        return self._items[self._index][1]

    def setValue(self, value, *, animate: bool = True) -> None:  # noqa: N802
        for i, (_, val) in enumerate(self._items):
            if val == value:
                if i == self._index:
                    return
                self._index = i
                if animate:
                    anim.animate_value(self, b"indicatorPos", float(i),
                                       duration=anim.Motion.SLOW,
                                       curve=anim.Motion.EASING_IN_OUT)
                else:
                    self._set_indicator(float(i))
                self.changed.emit(self.value())
                return

    def _segment_width(self) -> float:
        if not self._items:
            return 0.0
        return self.width() / len(self._items)

    def _index_at(self, x: float) -> int:
        width = self._segment_width()
        if width <= 0:
            return -1
        index = int(x // width)
        return max(0, min(len(self._items) - 1, index))

    def mouseMoveEvent(self, event):  # noqa: N802
        index = self._index_at(event.position().x())
        if index != self._hover_index:
            self._hover_index = index
            self.update()

    def leaveEvent(self, event):  # noqa: N802
        self._hover_index = -1
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        index = self._index_at(event.position().x())
        if 0 <= index < len(self._items) and index != self._index:
            self._index = index
            anim.animate_value(self, b"indicatorPos", float(index),
                               duration=anim.Motion.SLOW,
                               curve=anim.Motion.EASING_IN_OUT)
            self.changed.emit(self.value())

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(Color.SUNKEN))
        painter.drawRoundedRect(rect, Radius.CONTROL, Radius.CONTROL)

        seg = self._segment_width()
        pill = QRectF(rect.left() + self._indicator * seg + 3,
                      rect.top() + 3, max(0.0, seg - 6), rect.height() - 6)
        painter.setBrush(QColor(Color.BG))
        painter.drawRoundedRect(pill, Radius.SMALL, Radius.SMALL)

        font = QFont(self.font())
        font.setPixelSize(Font.SIZE_SMALL)
        for i, (label, _) in enumerate(self._items):
            active = i == self._index
            if active:
                font.setWeight(QFont.DemiBold)
                color = QColor(Color.TEXT)
            else:
                font.setWeight(QFont.Normal)
                color = QColor(Color.TEXT_SECONDARY if i == self._hover_index
                               else Color.TEXT_TERTIARY)
            painter.setFont(font)
            painter.setPen(color)
            painter.drawText(QRectF(rect.left() + i * seg, rect.top(), seg, rect.height()),
                             Qt.AlignCenter, label)
        painter.end()


# --------------------------------------------------------------------------
# 下拉框（自绘箭头）
# --------------------------------------------------------------------------


class SlimComboBox(QComboBox):
    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPoint(self.width() - 15, self.height() // 2 + 1)
        draw_chevron(painter, center, 7.5, QColor(Color.TEXT_TERTIARY), 1.5)
        painter.end()


class EditableCombo(QComboBox):
    """可输入也可以选的下拉。

    详细配置里「字号」「段前段后」这类项，预设值覆盖不了所有情况（比如
    "13pt"、"-2"），所以做成可写；同时给最常用的几个值，省得每次都敲。
    """

    def __init__(self, items: list[str] | None = None, *,
                 placeholder: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)   # 只当输入辅助，不往列表里塞值
        if items:
            self.addItems(items)
        if placeholder:
            self.lineEdit().setPlaceholderText(placeholder)
        # 内层行编辑要连 padding 一起清掉。只清 background/border 的话，QSS 里
        # 那条 `padding: 5px 8px` 仍然生效，文字会被整体右推 8px，右侧留给
        # chevron 的空间更紧——"Times New Roman" 就会被滚成 "mes New Roman"。
        self.lineEdit().setStyleSheet(
            "background:transparent; border:none; padding:0px; margin:0px;")
        self.lineEdit().setMinimumWidth(0)
        self.setFixedHeight(32)

    def value(self) -> str:
        return self.currentText().strip()

    def setValue(self, text: str) -> None:
        self.setEditText(str(text or ""))

    def showPopup(self) -> None:  # noqa: N802
        """展开时把宽度撑到内容需要的大小。

        详细分组在 296px 的侧栏里，"Times New Roman"、"chineseCountingThousand"
        这类候选值会被下拉框裁成半截，展开后临时放宽才看得全。
        """
        view = self.view()
        view.setMinimumWidth(self._popup_width())
        super().showPopup()

    def _popup_width(self) -> int:
        metrics = QFontMetrics(self.font())
        widest = max((metrics.horizontalAdvance(self.itemText(i))
                      for i in range(self.count())), default=0)
        # +48：给自绘 chevron 与左右内边距留位置
        return max(self.width(), widest + 48)

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPoint(self.width() - 15, self.height() // 2 + 1)
        draw_chevron(painter, center, 7.5, QColor(Color.TEXT_TERTIARY), 1.5)
        painter.end()


# --------------------------------------------------------------------------
# 窄输入框（数值 / 长度）
# --------------------------------------------------------------------------


class SlimLineEdit(QLineEdit):
    """窄输入框：无内框、底色区分，失焦时把内容收干净。"""

    def __init__(self, text: str = "", *, placeholder: str = "",
                 align_center: bool = False, parent: QWidget | None = None):
        super().__init__(text, parent)
        if placeholder:
            self.setPlaceholderText(placeholder)
        if align_center:
            self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(32)

    def value(self) -> str:
        return self.text().strip()

    def setValue(self, text: str) -> None:
        self.setText(str(text or ""))

    def focusOutEvent(self, event):  # noqa: N802
        super().focusOutEvent(event)
        # 用户可能顺手多敲了空格，离开时收拾干净，免得写进配置里
        self.setText(self.text().strip())


# --------------------------------------------------------------------------
# 折叠分组
# --------------------------------------------------------------------------


class CollapsibleSection(QWidget):
    """可折叠分组：标题行常驻，内容按需展开。

    设计上刻意不用卡片、不用横线——中文排版工具的参数很多，全平铺会让面板
    长得吓人；收起来之后标题行本身就是一层分组信息，靠字重和留白区分。

    收起时会把内容高度压成 0，同时借 `collapsed` 信号让宿主把相邻间距收紧：
    五个分组各留一份分组间距，光标题行就要吃掉一百多像素。
    """

    collapsed = Signal(bool)

    def __init__(self, title: str, content: QWidget, *,
                 expanded: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._hover = False
        self._expanded = bool(expanded)
        self._turn = 1.0 if expanded else 0.0
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.TIGHT)

        self._header = _SectionHeader(title)
        self._header.clicked.connect(self.toggle)
        self._header.hover_changed.connect(self._on_hover)
        layout.addWidget(self._header)

        content.setParent(self)
        layout.addWidget(content)
        self._content = content
        if not expanded:
            self._set_clamped(True)

    # -- 动画属性 --------------------------------------------------------
    def _get_turn(self) -> float:
        return self._turn

    def _set_turn(self, value: float) -> None:
        self._turn = value
        self._header.turn = value

    turn = Property(float, _get_turn, _set_turn)

    # -- 交互 ------------------------------------------------------------
    def _on_hover(self, hover: bool) -> None:
        self._hover = hover

    def isExpanded(self) -> bool:  # noqa: N802
        return self._expanded

    def toggle(self) -> None:
        self.setExpanded(not self._expanded)

    def setExpanded(self, expanded: bool, *, animate: bool = True) -> None:  # noqa: N802
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.collapsed.emit(not expanded)
        target = 1.0 if expanded else 0.0
        if animate:
            anim.animate_value(self, b"turn", target, duration=Motion.SLOW,
                               curve=Motion.EASING_SOFT)
        else:
            self._set_turn(target)
        if not animate:
            # 不做动画时没有 QPropertyAnimation 帮忙复位 maximumHeight，必须
            # 自己解开——否则构造函数里那个 setMaximumHeight(0) 会一直生效，
            # 分组看着展开了、sizeHint 却还是 26px，整块内容被裁掉。
            self._set_clamped(not expanded)
            return
        if expanded:
            # 动画期间箭头与高度同时走，但布局间距没法动画，所以在展开一开始
            # 就把标题行与内容之间的那道缝还回来
            self.layout().setSpacing(Space.TIGHT)
            anim.reveal(self._content, duration=Motion.SLOW)
        else:
            anim.collapse(self._content, duration=Motion.BASE,
                          on_done=lambda: self.layout().setSpacing(0))

    def _set_clamped(self, clamped: bool) -> None:
        """直接在"压成 0"和"不限制"之间切换，供无动画路径使用。"""
        layout = self.layout()
        if clamped:
            self._content.setVisible(False)
            self._content.setMaximumHeight(0)
            layout.setSpacing(0)
        else:
            self._content.setMaximumHeight(16777215)
            self._content.setVisible(True)
            layout.setSpacing(Space.TIGHT)
        self.updateGeometry()


class SectionStack(QWidget):
    """一列折叠分组。

    自己管间距：全收起时相邻标题行只留一点点缝，其中一组展开后再把那份
    分组间距还回去。把间距交给这里、而不是留给外面的布局，是因为外层只看到
    "一个控件"，算不出"现在有几组是收着的"。
    """

    def __init__(self, sections: list[CollapsibleSection], *,
                 spacing: int = Space.SECTION,
                 collapsed_spacing: int = Space.TIGHT + 3,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._spacing = spacing
        self._collapsed_spacing = collapsed_spacing
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(collapsed_spacing)
        self._layout = layout
        self._sections = list(sections)
        for section in self._sections:
            section.collapsed.connect(self._resync)
            layout.addWidget(section)
        self._resync()

    def sections(self) -> list[CollapsibleSection]:
        return list(self._sections)

    def _resync(self, *_args) -> None:
        """有任一组展开就用常规分组间距，全收起时收紧。

        QVBoxLayout 的 spacing 是全局的一个数，做不到"逐条缝不一样"，而
        全收起时那五份 16px 才是真正把面板顶高的东西。展开态的外观本来就
        被内容撑开了，用统一间距即可。
        """
        any_expanded = any(section.isExpanded() for section in self._sections)
        self._layout.setSpacing(self._spacing if any_expanded
                                else self._collapsed_spacing)
        self.updateGeometry()


class _SectionHeader(QFrame):
    """折叠分组的标题行：文字 + 右侧折角箭头。"""

    clicked = Signal()
    hover_changed = Signal(bool)

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._turn = 0.0
        self._hover = False
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(26)

    def _get_turn(self) -> float:
        return self._turn

    def _set_turn(self, value: float) -> None:
        self._turn = value
        self.update()

    turn = Property(float, _get_turn, _set_turn)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.hover_changed.emit(True)
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.hover_changed.emit(False)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(Font.SIZE_LABEL)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(Color.TEXT_SECONDARY if self._hover
                              else Color.TEXT_TERTIARY))
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, self._title)
        # 箭头：`turn` 0 表示收起、1 表示展开。`draw_chevron` 画的是朝下的折角，
        # 所以收起态要逆时针转 90° 变成朝右；用 `turn` 直接插值，展开过程就是
        # 一个从右转到下的连续动作。
        angle = -90.0 * (1.0 - self._turn)
        painter.save()
        center = QPoint(self.width() - 9, self.height() // 2 + 1)
        painter.translate(center)
        painter.rotate(angle)
        painter.translate(-center)
        draw_chevron(painter, QPoint(center.x(), center.y()), 6.5,
                     QColor(Color.ACCENT if self._hover else Color.TEXT_TERTIARY),
                     1.5)
        painter.restore()
        painter.end()


# --------------------------------------------------------------------------
# 进度条（窗口底边细线）
# --------------------------------------------------------------------------


class SlimProgress(QFrame):
    """贴着窗口底边的细进度线。空闲时完全隐形。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._progress = 0.0
        self.setFixedHeight(2)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = value
        self.update()

    value = Property(float, _get_progress, _set_progress)

    def set_progress(self, ratio: float, *, animate: bool = True) -> None:
        ratio = max(0.0, min(1.0, float(ratio)))
        if animate:
            anim.animate_value(self, b"value", ratio, duration=anim.Motion.SLOW,
                               curve=anim.Motion.EASING_IN_OUT)
        else:
            self._set_progress(ratio)

    def paintEvent(self, event):  # noqa: N802
        if self._progress <= 0.001:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width() * self._progress
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(Color.ACCENT))
        painter.drawRoundedRect(QRectF(0, 0, width, self.height()), 1, 1)
        painter.end()


# --------------------------------------------------------------------------
# 分组标签
# --------------------------------------------------------------------------


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionLabel")
    return label


class ElidedLabel(QWidget):
    """固定单行高度的说明文字，超出用省略号。

    不用 QLabel 的自动换行：wordWrap 的 QLabel 在 QScrollArea 里会报出一个
    偏大的最小高度，把设置面板顶出滚动条。
    """

    def __init__(self, text: str = "", *, color: str = Color.TEXT_TERTIARY,
                 size: int = Font.SIZE_SMALL, parent: QWidget | None = None):
        super().__init__(parent)
        self._full = text or ""
        self._color = QColor(color)
        self._size = size
        self.setFixedHeight(size + 5)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setToolTip(self._full)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text or ""
        self.setToolTip(self._full)
        self.update()

    def text(self) -> str:
        return self._full

    def setColor(self, color: str) -> None:  # noqa: N802
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        font = QFont(self.font())
        font.setPixelSize(self._size)
        painter.setFont(font)
        painter.setPen(self._color)
        metrics = QFontMetrics(font)
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter,
                         metrics.elidedText(self._full, Qt.ElideRight, self.width()))
        painter.end()


# --------------------------------------------------------------------------
# 文件行
# --------------------------------------------------------------------------

STATUS_COLORS = {
    "idle": Color.LINE_STRONG,
    "running": Color.ACCENT,
    "ok": Color.SUCCESS,
    "error": Color.DANGER,
    "skip": Color.WARNING,
}


class FileRow(QFrame):
    remove_requested = Signal(str)
    activated = Signal(str)

    def __init__(self, path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.path = path
        self._status = "idle"
        self._dot = QColor(STATUS_COLORS["idle"])
        self._hover = False
        self.setFixedHeight(42)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 0, 8, 0)   # 左边留出状态点的位置
        layout.setSpacing(10)

        self._name = QLabel(os.path.basename(path))
        self._name.setStyleSheet(
            f"font-size:{Font.SIZE_BODY}px; color:{Color.TEXT}; background:transparent;")
        self._meta = QLabel(self._meta_text(path))
        self._meta.setStyleSheet(
            f"font-size:{Font.SIZE_SMALL}px; color:{Color.TEXT_TERTIARY};"
            "background:transparent;")
        self._remove = IconButton(IconButton.REMOVE, size=26)
        self._remove.clicked.connect(lambda: self.remove_requested.emit(self.path))
        self._remove.setStyleSheet("background:transparent;")

        layout.addWidget(self._name, 1)
        layout.addWidget(self._meta, 0)
        layout.addWidget(self._remove, 0)

    @staticmethod
    def _meta_text(path: str) -> str:
        try:
            size = os.path.getsize(path)
        except OSError:
            return "文件不存在"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.1f} MB"

    # -- 属性 ------------------------------------------------------------
    def _get_dot(self) -> QColor:
        return self._dot

    def _set_dot(self, value: QColor) -> None:
        self._dot = value
        self.update()

    dotColor = Property(QColor, _get_dot, _set_dot)

    def _get_bg(self) -> QColor:
        return getattr(self, "_row_bg", QColor(Qt.transparent))

    def _set_bg(self, value: QColor) -> None:
        self._row_bg = value
        self.update()

    bgColor = Property(QColor, _get_bg, _set_bg)

    def set_status(self, status: str, *, animate: bool = True) -> None:
        if status not in STATUS_COLORS:
            return
        self._status = status
        target = QColor(STATUS_COLORS[status])
        if animate:
            anim.animate_color(self, "dot", self._dot, target, duration=200)
        else:
            self._set_dot(target)
        # 成功态不回写「已完成」——绿色圆点已经表达清楚了，重复三遍反而吵
        if status == "running":
            self._meta.setText("转换中…")
        elif status == "error":
            self._meta.setText("失败")
        else:
            self._meta.setText(self._meta_text(self.path))
        self._remove.setVisible(status != "running")
        self.layout().setContentsMargins(22, 0, 8, 0)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        anim.animate_color(self, "row", self._get_bg(), QColor(Color.SUNKEN),
                           duration=120)
        self._remove.setStyleSheet("background:transparent;")

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        anim.animate_color(self, "row", self._get_bg(), QColor(Qt.transparent),
                           duration=120)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.activated.emit(self.path)

    def paintEvent(self, event):  # noqa: N802
        bg = self._get_bg()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if bg.alpha():
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0, 1, 0, -1),
                                    Radius.CONTROL, Radius.CONTROL)
        # 左侧状态点
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._dot)
        painter.drawEllipse(QRectF(12, self.height() / 2 - 3, 6, 6))
        painter.end()


# --------------------------------------------------------------------------
# 拖放区
# --------------------------------------------------------------------------


class DropArea(QFrame):
    """空态时的拖放 / 点击导入区。虚线框只在有内容提示时才出现。"""

    clicked = Signal()
    files_dropped = Signal(list)

    MD_SUFFIXES = (".md", ".markdown", ".mdown", ".txt")

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._highlight = 0.0
        self._dragging = False
        self.setMinimumHeight(180)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setAcceptDrops(True)
        # 竖向撑满：空态不留大片空白，且切换到列表时不会纵向跳动
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _get_highlight(self) -> float:
        return self._highlight

    def _set_highlight(self, value: float) -> None:
        self._highlight = value
        self.update()

    highlight = Property(float, _get_highlight, _set_highlight)

    def _to(self, target: float) -> None:
        anim.animate_value(self, b"highlight", target, duration=anim.Motion.FAST,
                           curve=anim.Motion.EASING)

    def enterEvent(self, event):  # noqa: N802
        if not self._dragging:
            self._to(0.55)

    def leaveEvent(self, event):  # noqa: N802
        if not self._dragging:
            self._to(0.0 if not self.underMouse() else self._highlight)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.clicked.emit()

    # -- 拖放 ------------------------------------------------------------
    @classmethod
    def _accepts(cls, urls) -> list[str]:
        found = []
        for url in urls:
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if os.path.isdir(path):
                for name in sorted(os.listdir(path)):
                    if name.lower().endswith(cls.MD_SUFFIXES):
                        found.append(os.path.join(path, name))
            elif path.lower().endswith(cls.MD_SUFFIXES):
                found.append(path)
        return found

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls() and self._accepts(event.mimeData().urls()):
            event.acceptProposedAction()
            self._dragging = True
            self._to(1.0)

    def dragLeaveEvent(self, event):  # noqa: N802
        self._dragging = False
        self._to(0.0)

    def dropEvent(self, event):  # noqa: N802
        self._dragging = False
        self._to(0.4)
        files = self._accepts(event.mimeData().urls())
        if files:
            self.files_dropped.emit(files)
        event.acceptProposedAction()

    # -- 绘制 ------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        t = max(0.0, min(1.0, self._highlight))

        painter.setPen(Qt.NoPen)
        painter.setBrush(mix(QColor(255, 255, 255, 0), QColor(Color.ACCENT_SOFT), t))
        painter.drawRoundedRect(rect, Radius.PANEL, Radius.PANEL)

        pen = QPen(mix(QColor(Color.LINE_STRONG), QColor(Color.ACCENT), t), 1.4)
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([5, 4])
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, Radius.PANEL, Radius.PANEL)

        cx = rect.center().x()
        icon_center_y = rect.center().y() - 34
        radius = 25.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(mix(QColor(Color.SUNKEN), QColor(Color.ACCENT), t * 0.92))
        painter.drawEllipse(QRectF(cx - radius, icon_center_y - radius,
                                   radius * 2, radius * 2))

        glyph = mix(QColor(Color.TEXT_TERTIARY), QColor(Color.TEXT_ON_ACCENT), t * 0.95)
        pen = QPen(glyph, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(QPoint(int(cx), int(icon_center_y - 10)),
                         QPoint(int(cx), int(icon_center_y + 4)))
        painter.drawLine(QPoint(int(cx - 5), int(icon_center_y - 1)),
                         QPoint(int(cx), int(icon_center_y + 4)))
        painter.drawLine(QPoint(int(cx + 5), int(icon_center_y - 1)),
                         QPoint(int(cx), int(icon_center_y + 4)))
        painter.drawLine(QPoint(int(cx - 11), int(icon_center_y + 11)),
                         QPoint(int(cx + 11), int(icon_center_y + 11)))

        title_font = QFont(self.font())
        title_font.setPixelSize(Font.SIZE_TITLE)
        title_font.setWeight(QFont.Medium)
        painter.setFont(title_font)
        painter.setPen(mix(QColor(Color.TEXT_SECONDARY), QColor(Color.ACCENT_PRESSED), t))
        painter.drawText(QRectF(rect.left(), icon_center_y + 48, rect.width(), 22),
                         Qt.AlignCenter, "把 Markdown 拖到这里")

        hint_font = QFont(self.font())
        hint_font.setPixelSize(Font.SIZE_SMALL)
        painter.setFont(hint_font)
        painter.setPen(QColor(Color.TEXT_TERTIARY))
        painter.drawText(QRectF(rect.left(), icon_center_y + 72, rect.width(), 20),
                         Qt.AlignCenter, "或点击选择文件　·　支持一次拖入多个")
        painter.end()


# --------------------------------------------------------------------------
# 文件类型图标（用于导入提示）
# --------------------------------------------------------------------------


def app_pixmap(size: int = 20) -> QPixmap:
    """画一个小小的应用标记：圆角方块 + 白色 M 字折线。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(Color.ACCENT))
    painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.28, size * 0.28)
    pen = QPen(QColor(Color.TEXT_ON_ACCENT), max(1.4, size * 0.1))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    inset = size * 0.28
    path.moveTo(inset, size - inset)
    path.lineTo(inset, inset + size * 0.06)
    path.lineTo(size / 2, size * 0.6)
    path.lineTo(size - inset, inset + size * 0.06)
    path.lineTo(size - inset, size - inset)
    painter.drawPath(path)
    painter.end()
    return pixmap
