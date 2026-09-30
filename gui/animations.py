"""动效工具：淡入、高度展开、数值平滑、颜色过渡。

统一入口，避免每个控件各写一遍 QPropertyAnimation。所有动画用
DeleteWhenStopped 自我回收，同时把引用挂在控件上防止被 GC 掉。
"""

from __future__ import annotations

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPropertyAnimation,
                            QTimer)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsOpacityEffect

from .theme import Motion

_EASINGS = {
    "OutCubic": QEasingCurve.OutCubic,
    "InOutCubic": QEasingCurve.InOutCubic,
    "OutQuint": QEasingCurve.OutQuint,
    "OutBack": QEasingCurve.OutBack,
    "InOutQuad": QEasingCurve.InOutQuad,
    "Linear": QEasingCurve.Linear,
}


def easing(name: str) -> QEasingCurve:
    return _EASINGS.get(name, QEasingCurve.OutCubic)


def _keep(widget, key: str, anim: QPropertyAnimation) -> QPropertyAnimation:
    setattr(widget, f"_anim_{key}", anim)
    return anim


def set_opacity(widget, value: float) -> None:
    """直接设定透明度（不走动画），用于把控件复位到可见状态。"""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(float(value))


def fade(widget, *, start: float = 0.0, end: float = 1.0,
         duration: int = Motion.BASE, curve: str = Motion.EASING,
         on_done=None) -> QPropertyAnimation:
    """透明度动画。会临时给控件挂 QGraphicsOpacityEffect。

    start 会被强制写进 effect，这样重复调用也能重新播放（否则 opacity 已是
    终值，动画看不到变化）。
    """
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(float(start))
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(float(start))
    anim.setEndValue(end)
    anim.setEasingCurve(easing(curve))
    if on_done:
        anim.finished.connect(on_done)
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return _keep(widget, "fade", anim)


def reveal(widget, *, duration: int = Motion.SLOW, curve: str = Motion.EASING_IN_OUT,
           on_done=None) -> QPropertyAnimation:
    """高度展开：从 0 到内容实际高度，用于"面板出现"这类过渡。"""
    widget.setVisible(True)
    target = widget.sizeHint().height()
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(duration)
    anim.setStartValue(0)
    anim.setEndValue(target)
    anim.setEasingCurve(easing(curve))
    anim.finished.connect(lambda: widget.setMaximumHeight(16777215))

    def _finish():
        if on_done:
            on_done()

    anim.finished.connect(_finish)
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    fade(widget, duration=max(120, duration - 60), curve=curve)
    return _keep(widget, "reveal", anim)


def collapse(widget, *, duration: int = Motion.BASE, on_done=None) -> QPropertyAnimation:
    """高度收拢到 0 后隐藏。"""
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(duration)
    anim.setStartValue(max(widget.height(), widget.sizeHint().height()))
    anim.setEndValue(0)
    anim.setEasingCurve(easing(Motion.EASING_IN_OUT))

    def _finish():
        widget.setVisible(False)
        widget.setMaximumHeight(16777215)
        if on_done:
            on_done()

    anim.finished.connect(_finish)
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return _keep(widget, "collapse", anim)


def animate_color(widget, key: str, start: QColor, end: QColor,
                  *, duration: int = Motion.FAST,
                  curve: str = Motion.EASING) -> QPropertyAnimation:
    """对带 bgColor 属性的自绘控件做颜色过渡。"""
    anim = QPropertyAnimation(widget, b"bgColor", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing(curve))
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return _keep(widget, key, anim)


def animate_value(obj, prop: bytes, end, *, duration: int = Motion.BASE,
                  curve: str = Motion.EASING) -> QPropertyAnimation:
    """数值平滑过渡（进度条、滑块指示器等）。"""
    start = obj.property(prop.decode())
    anim = QPropertyAnimation(obj, prop, obj)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing(curve))
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return _keep(obj, f"value_{prop.decode()}", anim)


def stagger(widgets, *, step: int = 45, duration: int = Motion.BASE,
            curve: str = Motion.EASING) -> None:
    """列表项依次淡入，避免整块内容同时出现造成的生硬感。"""
    for index, widget in enumerate(widgets):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        QTimer.singleShot(index * step, lambda w=widget: fade(w, duration=duration,
                                                             curve=curve))
