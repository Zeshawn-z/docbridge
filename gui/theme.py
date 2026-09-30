"""视觉规范：颜色、字号、间距、圆角、动效节奏。

所有界面代码只引用这里的常量，不写死颜色值；改配色只改这一处。
"""

from __future__ import annotations


class Color:
    """浅色主题配色。留白承担分隔职责，尽量不用线条。"""

    BG = "#FFFFFF"                # 窗口底
    RAISED = "#FFFFFF"            # 浮起元素（下拉弹层）
    SUNKEN = "#F7F8FA"            # 输入框 / 次级底色
    HOVER = "#EFF1F4"             # 悬停底色
    ACTIVE = "#E6E9EE"            # 按下底色

    TEXT = "#1F2329"              # 主文字
    TEXT_SECONDARY = "#7A828C"    # 次要文字
    TEXT_TERTIARY = "#A9AFB8"     # 弱提示、分组标签
    TEXT_ON_ACCENT = "#FFFFFF"

    ACCENT = "#2C6BED"
    ACCENT_HOVER = "#1F5BD8"
    ACCENT_PRESSED = "#1A4FBF"
    ACCENT_SOFT = "#EAF1FE"
    ACCENT_EDGE = "#B9D0FB"

    LINE = "#E8EAEE"              # 只用在窗口外沿
    LINE_STRONG = "#D8DCE3"

    SUCCESS = "#12A150"
    DANGER = "#DB4C4C"
    DANGER_SOFT = "#FCEBEB"
    WARNING = "#C7791A"


class Font:
    FAMILY = ('"Microsoft YaHei UI", "Segoe UI", "PingFang SC", '
              '"Hiragino Sans GB", sans-serif')
    MONO = '"Cascadia Mono", "Consolas", "Menlo", monospace'

    SIZE_HERO = 21
    SIZE_TITLE = 14
    SIZE_BODY = 13
    SIZE_SMALL = 12
    SIZE_LABEL = 11


class Radius:
    WINDOW = 12
    PANEL = 10
    CONTROL = 8
    SMALL = 6


class Space:
    WINDOW_PAD = 26
    #: 侧栏宽度。详细配置是两列并排，每列要塞下"中文字体/西文字体"这类较长
    #: 的标签与取值，296px 会让两列各自只剩 130 上下，字体名必然被裁；332px
    #: 是"两列都放得下 Times New Roman"的最小值。
    SIDEBAR = 332
    SECTION = 16
    ITEM = 12
    TIGHT = 6
    FIELD = 10          # 详细配置里相邻两行的间距


class Motion:
    """动画时长与缓动。统一在这里调，保证全界面节奏一致。"""

    FAST = 140
    BASE = 200
    SLOW = 280
    EASING = "OutCubic"
    EASING_IN_OUT = "InOutCubic"
    EASING_SOFT = "OutQuint"


def stylesheet() -> str:
    """全局 QSS。控件外观只在这里定义。"""
    c, f, r = Color, Font, Radius
    return f"""
    * {{
        font-family: {f.FAMILY};
        font-size: {f.SIZE_BODY}px;
        color: {c.TEXT};
        outline: none;
    }}

    #Root {{
        background: {c.BG};
        border: 1px solid {c.LINE};
        border-radius: {r.WINDOW}px;
    }}

    #TitleBar, #ContentArea, #Sidebar, #Footer {{ background: transparent; }}
    #TitleText {{ font-size: {f.SIZE_BODY}px; font-weight: 600; }}
    #TitleVersion {{ font-size: {f.SIZE_SMALL}px; color: {c.TEXT_TERTIARY}; }}

    #HeroTitle {{ font-size: {f.SIZE_HERO}px; font-weight: 600; }}
    #HeroSubtitle {{ font-size: {f.SIZE_SMALL}px; color: {c.TEXT_SECONDARY}; }}

    #SectionLabel {{
        font-size: {f.SIZE_LABEL}px; font-weight: 600;
        color: {c.TEXT_TERTIARY}; letter-spacing: 0.7px;
    }}
    #Hint {{ font-size: {f.SIZE_SMALL}px; color: {c.TEXT_TERTIARY}; }}
    #StatusText {{ font-size: {f.SIZE_SMALL}px; color: {c.TEXT_SECONDARY}; }}
    #StatusOk {{ font-size: {f.SIZE_SMALL}px; color: {c.SUCCESS}; }}
    #StatusWarn {{ font-size: {f.SIZE_SMALL}px; color: {c.WARNING}; }}
    #StatusError {{ font-size: {f.SIZE_SMALL}px; color: {c.DANGER}; }}

    /* ── 输入控件：无边框，靠底色区分 ─────────────────────────── */
    QComboBox, QLineEdit {{
        background: {c.SUNKEN};
        border: 1px solid transparent;
        border-radius: {r.CONTROL}px;
        /* 详细配置是两列并排，列宽只有 130 上下。左右各减 2px、字号降到 12px，
           "Times New Roman" 这类长值才不至于被裁成半截。 */
        padding: 5px 8px;
        min-height: 18px;
        font-size: {f.SIZE_SMALL}px;
        selection-background-color: {c.ACCENT_SOFT};
        selection-color: {c.TEXT};
    }}
    QComboBox:hover, QLineEdit:hover {{ background: {c.HOVER}; }}
    QComboBox:focus, QLineEdit:focus {{
        background: {c.BG};
        border: 1px solid {c.ACCENT_EDGE};
    }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox::down-arrow {{ image: none; width: 0px; height: 0px; }}
    QComboBox QAbstractItemView {{
        background: {c.RAISED};
        border: 1px solid {c.LINE};
        border-radius: {r.CONTROL}px;
        padding: 5px;
        outline: none;
        selection-background-color: {c.SUNKEN};
        selection-color: {c.TEXT};
    }}

    /* ── 滚动条：极细，悬停才明显 ───────────────────────────── */
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 0; }}
    QScrollBar::handle:vertical {{
        background: {c.LINE}; border-radius: 4px; min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c.TEXT_TERTIARY}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    #LogView {{
        background: {c.SUNKEN};
        border: none;
        border-radius: {r.PANEL}px;
        padding: 10px 12px;
        font-family: {f.MONO};
        font-size: {f.SIZE_LABEL}px;
        color: {c.TEXT_SECONDARY};
    }}

    QToolTip {{
        background: {c.TEXT};
        color: {c.BG};
        border: none;
        border-radius: {r.SMALL}px;
        padding: 5px 8px;
        font-size: {f.SIZE_SMALL}px;
    }}
    """
