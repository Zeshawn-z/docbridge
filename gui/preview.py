"""界面离屏渲染，供开发期截图与打包后的自检共用。

要点：
- 不能用 `QT_QPA_PLATFORM=offscreen`——那个平台插件的字体库是空的
  （`QFontDatabase.families()` 返回 0），所有文字会渲染成豆腐块。
- 用 `WA_DontShowOnScreen` + `Root` 子控件的 `grab()`。直接 `window.grab()`
  在 Windows 上会被窗口系统重新摆放，`move()` 挪到屏幕外的动作根本不生效，
  窗口会在用户眼前闪一下。
- 抓图前必须把 `QGraphicsOpacityEffect` 临时摘掉。列表行的错峰淡入、日志区
  展开都会挂这个 effect，一旦挂着，`grab()` 就漏画这些控件自己的 `paintEvent`
  ——文件名与大小会"浮"到设置面板上，左栏的文件行状态点也会消失。摘掉之后
  所见即所得。
"""

from __future__ import annotations

import os

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QWidget


def settle(milliseconds: int = 700) -> None:
    """让动画跑完。错峰淡入、高度展开都靠定时器推进，必须走一轮事件循环。"""
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def prepare(window) -> None:
    """把窗口设成"渲染但不显示"。"""
    window.setAttribute(Qt.WA_DontShowOnScreen, True)
    window.show()
    settle(200)


def _neutralize_effects(window) -> list:
    """把所有透明度效果暂时换成"完全不透明"的等价物。

    不能 `setGraphicsEffect(None)`——Qt 会连带把这个 effect 对象删掉，
    截完想还原时拿到的是野指针。换成不透明度 1.0 的新 effect，
    渲染路径随之恢复正常（不再是 0 透明度那种需要离屏合成的状态），
    截完再把原来的 in-place 设回去。
    """
    restore: list[tuple[QWidget, QGraphicsOpacityEffect, float]] = []
    for child in window.findChildren(QWidget):
        effect = child.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            restore.append((child, effect, effect.opacity()))
            placeholder = QGraphicsOpacityEffect(child)
            placeholder.setOpacity(1.0)
            child.setGraphicsEffect(placeholder)
    return restore


def _restore_effects(restore: list) -> None:
    for child, effect, opacity in restore:
        try:
            effect.setOpacity(opacity)
            child.setGraphicsEffect(effect)
        except RuntimeError:
            # 控件在截图期间被销毁了（换栈、清空列表），跳过即可
            continue


def snapshot(window, path: str, background: str = "#E9EDF2") -> str:
    """把窗口抓成 PNG。透明边距上铺一层底色，方便看清投影。"""
    settle()
    restore = _neutralize_effects(window)
    settle(120)
    try:
        root = window.findChild(QFrame, "Root") or window
        pixmap = root.grab()
    finally:
        _restore_effects(restore)

    # 画布按"逻辑尺寸 × 设备像素比"建。系统缩放 125% 时 grab() 返回的是
    # 1360×1168 的物理像素，直接拿逻辑尺寸当画布会把图缩掉一圈。
    ratio = pixmap.devicePixelRatio() or 1.0
    canvas = QPixmap(int(window.width() * ratio), int(window.height() * ratio))
    canvas.setDevicePixelRatio(ratio)
    canvas.fill(QColor(background))
    painter = QPainter(canvas)
    offset = root.pos()
    painter.drawPixmap(offset.x(), offset.y(), pixmap)
    painter.end()

    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    if not canvas.save(path):
        raise RuntimeError(f"截图保存失败：{path}")
    return path
