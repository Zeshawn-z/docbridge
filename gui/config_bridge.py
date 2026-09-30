"""界面与配置系统之间的桥。

界面上的选项不直接改 default.yaml，而是翻译成 `--set` 覆盖项，交给
md2docx.config.load_config 做深度合并——这样 GUI 和命令行走的是同一条路径，
改默认规范只需要动 default.yaml。

详细配置（逐级标题 / 页面 / 表格 / 逐级编号）也一样：界面只负责收集用户
**显式填过**的项，其余一律留空不覆盖。这样模板里写好的规范不会被界面
悄悄改掉，也不会出现"打开界面转一遍，模板就失效了"。
"""

from __future__ import annotations

import os

from md2docx import resources
from md2docx.config import element_style
from md2docx.numbering import HEADING_PRESETS
from md2docx.units import parse_size

# 预设模板的中文说明。没有登记的模板走通用描述。
TEMPLATE_DESC = {
    "default.yaml": "通用规范 · 正文小四宋体、标题黑体、1.25 倍行距",
    "thesis.yaml": "论文与正式报告 · 1.5 倍行距、一级标题另起页、带目录与页码",
    "compact.yaml": "紧凑汇报 · 整篇五号、1.15 倍行距、不缩进",
    "gongwen.yaml": "公文式 · 标题自动编号（一、/（一）/ 1.）、1.5 倍行距、带目录",
}

FONT_SIZE_CHOICES = ["小五", "五号", "小四", "四号", "小三", "三号", "二号", "小一"]

#: 详细配置里的字号下拉（比首屏多两档，覆盖到封面标题）
DETAIL_SIZE_CHOICES = ["六号", "小五", "五号", "小四", "四号", "小三", "三号",
                       "小二", "二号", "小一", "一号", "小初", "初号"]

LINE_SPACING_CHOICES: list[tuple[str, float]] = [
    ("1.0", 1.0), ("1.15", 1.15), ("1.25", 1.25), ("1.5", 1.5), ("2.0", 2.0),
]

#: 详细配置里的行距下拉
DETAIL_LINE_SPACING_CHOICES = ["1.0", "1.15", "1.25", "1.3", "1.5", "1.75", "2.0", "2.5"]

#: 编号方案下拉：预设名 → 展示文案
NUMBERING_CHOICES: list[tuple[str, str]] = [
    (name, item["label"]) for name, item in HEADING_PRESETS.items()
]

NUMBERING_LEVEL_CHOICES: list[tuple[str, int]] = [
    ("前 2 级", 2), ("前 3 级", 3), ("前 4 级", 4), ("全部 6 级", 6),
]

#: 参与逐级配置的标题层级（1~6）
HEADING_LEVELS = (1, 2, 3, 4, 5, 6)

#: 中文字体候选项。做的是"常用值随手可选"，不是字体枚举——用户照样能自己填。
FONT_ZH_CHOICES = ["宋体", "黑体", "仿宋", "楷体", "微软雅黑", "等线", "方正书宋",
                   "华文中宋", "华文楷体"]
FONT_EN_CHOICES = ["Times New Roman", "Arial", "Calibri", "Cambria", "Georgia",
                   "Segoe UI", "Consolas"]

#: 对齐方式：下拉文案 → 配置取值（下拉是 (label, data) 的列表）
ALIGN_CHOICES: list[tuple[str, str]] = [
    ("左对齐", "left"), ("居中", "center"), ("右对齐", "right"), ("两端对齐", "both"),
]

#: 页面。分段控件收的是 (展示文案, 取值) 二元组，别搞反了。
PAGE_SIZE_CHOICES = ["A4", "A3", "B5", "Letter", "16开"]
ORIENTATION_CHOICES: list[tuple[str, str]] = [("纵向", "portrait"), ("横向", "landscape")]

#: 表格单元格垂直对齐
VALIGN_CHOICES: list[tuple[str, str]] = [("顶对齐", "top"), ("居中", "center"),
                                         ("底对齐", "bottom")]

#: 编号的 num_fmt 取值（配置值 → 展示文案）
NUM_FMT_CHOICES: list[tuple[str, str]] = [
    ("decimal", "1 2 3"),
    ("chineseCounting", "一 二 三"),
    ("chineseCountingThousand", "一千二百"),
    ("lowerLetter", "a b c"),
    ("upperLetter", "A B C"),
    ("lowerRoman", "i ii iii"),
    ("upperRoman", "I II III"),
    ("decimalEnclosedParen", "(1) (2)"),
    ("decimalFullWidth", "１ ２ ３"),
]

#: 编号与标题文字的分隔
SUFF_CHOICES: list[tuple[str, str]] = [
    ("space", "空格"), ("nothing", "紧接"), ("tab", "制表位"),
]

#: 编号逐级覆盖里可选的层级
NUMBERING_FORMAT_LEVELS = (1, 2, 3, 4)

OUTPUT_ALONGSIDE = "alongside"
OUTPUT_FOLDER = "folder"

#: 兼容旧的模块级常量
CONFIG_DIR = resources.bundled_config_dir()


def template_choices() -> list[dict]:
    """列出可用模板，默认规范排第一。

    同时扫描打包内的 config/ 与 exe 同级（源码运行时是项目根）的 config/，
    同名的以用户目录为准，所以用户可以直接把自己写的模板丢进去。
    """
    files = resources.config_files()
    choices = [{
        "label": "默认规范",
        "path": None,
        "desc": TEMPLATE_DESC["default.yaml"],
    }]

    for name in sorted(files):
        if name == "default.yaml":
            continue
        choices.append({
            "label": os.path.splitext(name)[0],
            "path": files[name],
            "desc": TEMPLATE_DESC.get(name, "自定义模板"),
        })
    return choices


#: 详细配置里"留空 = 沿用模板"的哨兵。
#:
#: 界面上所有详细配置项默认就是这个值：控件里显示模板当前的取值方便用户参照，
#: 但只要用户没亲手改过，就不会生成覆盖项。这一条是硬要求——首屏那个
#: 「行距」旋钮和模板里的 `defaults.line_spacing` 必须继续有效，不能被详细
#: 配置里回填出来的同名数值按元素钉死。
INHERIT = ""

#: 想覆盖成"没有值"（例如字色回到随主题）时用这个占位符。
#: 空串已经被"沿用模板"占了，两者必须能分开表达。
UNSET = "auto"


def _param(value):
    """把界面上的一个参数收敛成三态：沿用模板 / 显式清空 / 一个具体值。"""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.lower() == UNSET:
            return UNSET
        return text
    if isinstance(value, bool):
        return value
    return value


def build_overrides(*, line_spacing: float | None = None,
                    body_size: str | None = None,
                    heading_size: str | None = None,
                    first_line_indent: bool | None = None,
                    mermaid: bool | None = None,
                    toc: bool | None = None,
                    page_number: bool | None = None,
                    heading_numbering: str | None = None,
                    numbering_levels: int | None = None,
                    strip_prefix: bool | None = None,
                    numbering_restart: bool | None = None,
                    skip_first_level: bool | None = None,
                    body: dict | None = None,
                    headings: dict | None = None,
                    page: dict | None = None,
                    table: dict | None = None,
                    numbering_format: dict | None = None) -> dict:
    """把界面选项翻译成 config 覆盖项。

    前 10 个参数是首屏的快捷项（已经长期稳定）；后面几个是详细配置分组，
    以字典传入，值为 None / 空串的项自动跳过（见 `_param`）。
    """
    overrides: dict = {}
    if line_spacing is not None:
        overrides["defaults.line_spacing"] = float(line_spacing)
    if body_size:
        overrides["elements.body.size"] = body_size
    if heading_size:
        overrides["elements.heading1.size"] = heading_size
    if first_line_indent is not None:
        overrides["elements.body.first_line_indent"] = ("2字符" if first_line_indent
                                                       else "0字符")
    if mermaid is not None:
        overrides["mermaid.renderer"] = "auto" if mermaid else "off"
    if toc is not None:
        overrides["output.toc"] = bool(toc)
    if page_number is not None:
        overrides["page.footer_page_number"] = bool(page_number)
    # heading_numbering 为 None 表示界面上没开；"off" 显式关闭，其余是预设名
    if heading_numbering is not None:
        overrides["numbering.headings"] = heading_numbering or "off"
    if numbering_levels is not None:
        overrides["numbering.levels"] = int(numbering_levels)
    if strip_prefix is not None:
        overrides["numbering.strip_text_prefix"] = bool(strip_prefix)
    if numbering_restart is not None:
        overrides["numbering.restart"] = bool(numbering_restart)
    if skip_first_level is not None:
        overrides["numbering.skip_first_level"] = bool(skip_first_level)

    overrides.update(_element_overrides("body", body))
    for level, spec in (headings or {}).items():
        overrides.update(_element_overrides(f"heading{level}", spec))
    overrides.update(_page_overrides(page))
    overrides.update(_table_overrides(table))
    overrides.update(_numbering_format_overrides(numbering_format))
    return overrides


#: 界面上的取值 → 配置键。没列进来的项（如 shading/borders）不开放给界面。
_ELEMENT_FIELDS = {
    "size": "size",
    "font_zh": "font_zh",
    "font_en": "font_en",
    "bold": "bold",
    "italic": "italic",
    "color": "color",
    "align": "align",
    "line_spacing": "line_spacing",
    "space_before": "space_before",
    "space_after": "space_after",
    "first_line_indent": "first_line_indent",
    "left_indent": "left_indent",
    "keep_with_next": "keep_with_next",
    "page_break_before": "page_break_before",
}

_NUMERIC_FIELDS = {"size", "line_spacing", "space_before", "space_after"}
_BOOL_FIELDS = {"bold", "italic", "keep_with_next", "page_break_before"}


def _as_bool(value):
    """界面上的三态：真 / 假 / 不管（留空）。

    复选框本身只给真假，但"这一级的加粗沿用模板"必须有第三种表达，
    所以 None、空串、以及 Python 的 False 一律视为"不覆盖"——想让某一级
    显式关掉加粗，那是在模板里写 bold: false 的事，界面不承担这个职责。
    """
    if value is None or value == "" or value is False:
        return None
    if value is True:
        return True
    text = str(value).strip().lower()
    if text in ("true", "yes", "on", "1", "开", "是"):
        return True
    return None


def _element_overrides(key: str, spec: dict | None) -> dict:
    """把某一级（正文或某个标题层级）的详细设置翻译成覆盖项。

    只有用户真的动过的项才会产出覆盖项——回填进控件的模板取值在界面上显示着
    好看，但不等于"用户要改"，两条路径在这里分开。
    """
    out: dict = {}
    for field, value in (spec or {}).items():
        config_key = _ELEMENT_FIELDS.get(field)
        if config_key is None:
            continue
        if field in _BOOL_FIELDS:
            flag = _as_bool(value)
            if flag is not None:
                out[f"elements.{key}.{config_key}"] = flag
            continue
        if field in _NUMERIC_FIELDS:
            number = _as_number(value)
            if number is not None:
                out[f"elements.{key}.{config_key}"] = number
            continue
        param = _param(value)
        if param is None:
            continue
        if field == "color":
            out[f"elements.{key}.{config_key}"] = ("auto" if param == UNSET
                                                   else str(param).lstrip("#"))
            continue
        # 字体名里出现空格在 Word 里是合法的，但前后空白必须是干净的
        out[f"elements.{key}.{config_key}"] = param
    return out


def _as_number(value):
    """数值参数：空 → 沿用模板；UNSET → 清空（写 0）。"""
    param = _param(value)
    if param is None:
        return None
    if param == UNSET:
        return 0
    if isinstance(param, bool):
        return None
    if isinstance(param, (int, float)):
        return param
    try:
        text = str(param)
        return float(text) if "." in text else int(text)
    except ValueError:
        return None


_PAGE_FIELDS = ("size", "orientation", "margin_top", "margin_bottom",
                "margin_left", "margin_right", "footer_page_number")


def _page_overrides(spec: dict | None) -> dict:
    out: dict = {}
    page = spec or {}
    for field in _PAGE_FIELDS:
        if field not in page:
            continue
        value = page[field]
        if field == "footer_page_number":
            if isinstance(value, bool):
                out["page.footer_page_number"] = value
            continue
        if field == "orientation":
            param = _param(value)
            if param is not None and param != UNSET:
                out["page.orientation"] = param
            continue
        param = _param(value)
        if param is None:
            continue
        out[f"page.{field.replace('margin_', 'margin.')}"] = (
            "2.54cm" if param == UNSET else param)
    return out


_TABLE_FIELDS = ("width_pct", "header_fill", "valign", "fixed_layout",
                 "border_color", "border_size")


def _table_overrides(spec: dict | None) -> dict:
    out: dict = {}
    table = spec or {}
    for field in _TABLE_FIELDS:
        if field not in table:
            continue
        value = table[field]
        if field == "fixed_layout":
            if isinstance(value, bool):
                out["table.fixed_layout"] = value
            continue
        if field == "valign":
            param = _param(value)
            if param is not None and param != UNSET:
                out["table.valign"] = param
            continue
        if field in ("width_pct", "border_size"):
            number = _as_number(value)
            if number is None or number == 0:
                continue
            out["table.border.size" if field == "border_size"
                else "table.width_pct"] = int(number)
            continue
        param = _param(value)
        if param is None:
            continue
        text = str(param).lstrip("#")
        if param == UNSET:
            text = ""
        if field == "border_color":
            out["table.border.color"] = text or "auto"
        else:
            out["table.header_fill"] = text
    return out


def _numbering_format_overrides(spec: dict | None) -> dict:
    """逐级编号覆盖。

    `numbering.format` 是嵌套映射，`--set` 的点号写法表达不了，所以这里
    展开成 `numbering.format.1.num_fmt` 这种路径，由 _expand_dotted 还原。
    只写用户真的填过的字段——留空表示"沿用预设这一级的写法"。
    """
    out: dict = {}
    for level, item in (spec or {}).items():
        for field in ("num_fmt", "text", "suff"):
            param = _param((item or {}).get(field))
            if param is None or param == UNSET:
                continue
            out[f"numbering.format.{level}.{field}"] = str(param)
    return out


#: 给日志用的中文显示名
_OVERLIDE_PRETTY = {
    "defaults.line_spacing": "行距",
    "elements.body.size": "正文字号",
    "elements.heading1.size": "一级标题字号",
    "elements.body.first_line_indent": "首行缩进",
    "mermaid.renderer": "mermaid",
    "output.toc": "目录",
    "page.footer_page_number": "页码",
    "numbering.headings": "标题编号",
    "numbering.levels": "编号层级",
    "numbering.skip_first_level": "跳过第 1 级",
    "numbering.strip_text_prefix": "剥离手写编号",
    "numbering.restart": "子级重新计数",
}

_FIELD_LABELS = {
    "size": "字号", "font_zh": "中文字体", "font_en": "西文字体", "bold": "加粗",
    "italic": "斜体", "color": "字色", "align": "对齐", "line_spacing": "行距",
    "space_before": "段前", "space_after": "段后",
    "first_line_indent": "首行缩进", "left_indent": "左缩进",
    "keep_with_next": "与下段同页", "page_break_before": "段前分页",
}

_ELEMENT_LABELS = {"body": "正文", **{f"heading{i}": f"{i} 级标题"
                                     for i in HEADING_LEVELS}}


_NUMBERING_FIELD_LABELS = {"num_fmt": "格式", "text": "编号写法", "suff": "分隔符"}


def _pretty_key(key: str) -> str:
    """把配置路径翻译成中文，日志里能读得懂。"""
    direct = _OVERLIDE_PRETTY.get(key)
    if direct:
        return direct
    if key.startswith("elements."):
        _, element, field = key.split(".", 2)
        label = _ELEMENT_LABELS.get(element, element)
        return f"{label}{_FIELD_LABELS.get(field, field)}"
    if key.startswith("page.margin."):
        side = {"top": "上", "bottom": "下", "left": "左", "right": "右"}
        return f"页边距·{side.get(key.rsplit('.', 1)[-1], key)}"
    if key.startswith("numbering.format."):
        parts = key.split(".")          # numbering.format.<级>.<字段>
        if len(parts) == 4:
            field = _NUMBERING_FIELD_LABELS.get(parts[3], parts[3])
            return f"{parts[2]} 级编号{field}"
        return "编号逐级覆盖"
    page_labels = {"size": "纸张", "orientation": "纸张方向"}
    if key.startswith("page."):
        field = key.split(".", 1)[1]
        return f"页面·{page_labels.get(field, field)}"
    if key == "table.width_pct":
        return "表格宽度"
    if key == "table.header_fill":
        return "表头底纹"
    if key == "table.valign":
        return "单元格对齐"
    if key == "table.fixed_layout":
        return "固定列宽"
    if key.startswith("table.border."):
        return "表格边框" + ("颜色" if key.endswith("color") else "粗细")
    return key


def describe_overrides(overrides: dict) -> str:
    """给日志用的一句话摘要。"""
    if not overrides:
        return "模板参数未做额外覆盖"
    parts = []
    for key, value in overrides.items():
        shown = value
        if key == "numbering.headings" and value != "off":
            shown = HEADING_PRESETS.get(str(value), {}).get("label", value)
        elif key == "mermaid.renderer":
            shown = "开启" if value != "off" else "关闭"
        elif key.endswith(".align"):
            shown = dict(ALIGN_CHOICES).get(str(value), value)
        elif key == "page.orientation":
            shown = dict(ORIENTATION_CHOICES).get(str(value), value)
        elif key == "table.valign":
            shown = dict(VALIGN_CHOICES).get(str(value), value)
        elif key == "numbering.levels":
            shown = f"前 {value} 级"
        elif isinstance(value, bool):
            shown = "开" if value else "关"
        parts.append(f"{_pretty_key(key)}={shown}")
    return "覆盖项：" + "，".join(parts)


def element_snapshot(config: dict, key: str) -> dict:
    """取某元素合并后的排版参数，用于把当前模板的数值回填到详细配置里。

    界面打开详细分组时要显示"模板现在是什么样"，而不是一片空白——否则用户
    根本不知道自己在改什么。
    """
    s = element_style(config, key)
    snapshot = {
        "size": s.get("size", "小四"),
        "font_zh": s.get("font_zh") or "",
        "font_en": s.get("font_en") or "",
        "bold": bool(s.get("bold")),
        "italic": bool(s.get("italic")),
        "color": "auto" if str(s.get("color", "auto")).lower() in ("", "auto", "none")
        else str(s.get("color")).lstrip("#"),
        "align": s.get("align") or "left",
        "line_spacing": s.get("line_spacing", 1.25),
        "space_before": s.get("space_before", 0),
        "space_after": s.get("space_after", 0),
        "first_line_indent": s.get("first_line_indent", "0字符"),
        "left_indent": s.get("left_indent", "0字符"),
        "keep_with_next": bool(s.get("keep_with_next")),
        "page_break_before": bool(s.get("page_break_before")),
    }
    # 行距统一成字符串，界面上是下拉 + 可输入
    try:
        snapshot["line_spacing"] = f"{float(snapshot['line_spacing']):g}"
    except (TypeError, ValueError):
        snapshot["line_spacing"] = "1.25"
    snapshot["size_pt"] = parse_size(snapshot["size"])
    return snapshot


def page_snapshot(config: dict) -> dict:
    page = config.get("page") or {}
    margins = page.get("margin") or {}
    return {
        "size": page.get("size", "A4"),
        "orientation": page.get("orientation", "portrait"),
        "margin_top": margins.get("top", "2.54cm"),
        "margin_bottom": margins.get("bottom", "2.54cm"),
        "margin_left": margins.get("left", "3.0cm"),
        "margin_right": margins.get("right", "3.0cm"),
        "footer_page_number": bool(page.get("footer_page_number")),
    }


def table_snapshot(config: dict) -> dict:
    table = config.get("table") or {}
    border = table.get("border") or {}
    return {
        "width_pct": table.get("width_pct", 100),
        "header_fill": str(table.get("header_fill") or "").lstrip("#"),
        "valign": table.get("valign", "center"),
        "fixed_layout": bool(table.get("fixed_layout")),
        "border_color": str(border.get("color") or "").lstrip("#"),
        "border_size": border.get("size", 4),
    }


def numbering_snapshot(config: dict) -> dict:
    numbering = config.get("numbering") or {}
    fmt = numbering.get("format") or {}
    return {
        "preset": numbering.get("preset", "cn-decimal"),
        "levels": int(numbering.get("levels", 3) or 3),
        "restart": bool(numbering.get("restart", True)),
        "strip_text_prefix": bool(numbering.get("strip_text_prefix", True)),
        "skip_first_level": bool(numbering.get("skip_first_level", False)),
        "format": {int(k): dict(v) for k, v in fmt.items()
                   if str(k).isdigit() and isinstance(v, dict)},
    }


def default_output_dir() -> str:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        return desktop
    return os.path.expanduser("~")
