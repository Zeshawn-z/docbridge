"""中文字号名与长度单位换算。

Word 里长度单位是 twip（1/20 磅）；中文排版习惯用「字号名」（小四、三号…）
和「字符」（首行缩进 2 字符）来表达。这里统一做一层解析。
"""

from __future__ import annotations

# 中文字号 → 磅值（pt）
FONT_SIZE_NAMES: dict[str, float] = {
    "初号": 42.0,
    "小初": 36.0,
    "一号": 26.0,
    "小一": 24.0,
    "二号": 22.0,
    "小二": 18.0,
    "三号": 16.0,
    "小三": 15.0,
    "四号": 14.0,
    "小四": 12.0,
    "五号": 10.5,
    "小五": 9.0,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5.0,
}

# 磅值 → 中文字号（用于回显/自检）
PT_TO_NAME = {v: k for k, v in FONT_SIZE_NAMES.items()}

_CM_PER_INCH = 2.54


class ConfigValueError(ValueError):
    """配置项取值非法。"""


def parse_size(value) -> float:
    """解析字号，返回磅值。支持 '小四' / 12 / '12pt' / '12磅'。"""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in FONT_SIZE_NAMES:
        return FONT_SIZE_NAMES[text]
    lowered = text.lower().replace("磅", "pt")
    for suffix in ("pt", "磅"):
        if lowered.endswith(suffix):
            try:
                return float(lowered[: -len(suffix)])
            except ValueError:
                break
    try:
        return float(text)
    except ValueError as exc:
        raise ConfigValueError(f"无法识别的字号：{value!r}") from exc


def size_name(pt: float) -> str:
    """磅值反向映射为中文字号名，没有对应名就返回 '12pt' 形式。"""
    return PT_TO_NAME.get(round(float(pt), 2), f"{pt}pt")


def pt_to_twip(pt: float) -> int:
    return int(round(float(pt) * 20))


def parse_length_pt(value) -> float:
    """解析长度并统一返回磅值。支持 pt/磅、cm、mm、in、px(96dpi)。"""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().replace("磅", "pt")
    units = (("cm", _CM_PER_INCH), ("厘米", _CM_PER_INCH),
             ("mm", _CM_PER_INCH * 10), ("毫米", _CM_PER_INCH * 10),
             ("in", 1.0), ("英寸", 1.0), ("px", 96.0), ("pt", 72.0))
    for suffix, per_inch in units:
        if text.endswith(suffix):
            raw = text[: -len(suffix)].strip()
            try:
                return float(raw) / per_inch * 72.0
            except ValueError:
                break
    try:
        return float(text)
    except ValueError as exc:
        raise ConfigValueError(f"无法识别的长度：{value!r}") from exc


def parse_chars(value):
    """解析 '2字符' / '2em' / 2 → 字符数；不是字符单位则返回 None。"""
    text = str(value).strip().lower()
    for suffix in ("字符", "个字", "em", "字"):
        if text.endswith(suffix):
            raw = text[: -len(suffix)].strip()
            try:
                return float(raw)
            except ValueError:
                return None
    return None


def chars_to_twip(chars: float, font_pt: float) -> int:
    """把字符数折算成 twip（1 字符 ≈ 1 个全角字宽 = 字号磅值）。"""
    return int(round(chars * font_pt * 20))


# --------------------------------------------------------------------------
# 标题里手写的编号前缀
# --------------------------------------------------------------------------
# 一旦开了标题自动编号，Markdown 里原本手写的"一、""1.""（一）"就会和自动
# 编号叠在一起变成"一、一、项目概述"。这里负责把这类前缀剥掉。
#
# 刻意写得保守：只认"常见编号样式 + 紧跟分隔符"的形状，且要求前缀后面还有
# 正文，避免把"2024年规划"里的年份、或者"1.5 倍行距"这类正常标题误伤。

import re as _re

_CN_DIGITS = "零〇一二三四五六七八九十百千两"

HEADING_PREFIX_PATTERNS: list[_re.Pattern] = [
    # 第一章 / 第 1 章 / 第一节
    _re.compile(rf"^第\s*[0-9{_CN_DIGITS}]+\s*[章节篇部分]\s*"),
    # 一、 / 十二、
    _re.compile(rf"^[{_CN_DIGITS}]+\s*[、．.,，]\s*"),
    # （一） / (一) / 【一】
    _re.compile(rf"^[（(【\[][0-9{_CN_DIGITS}]+\s*[)）】\]]\s*"),
    # 1. / 1、 / 1.1 / 1.1.1 （要求数字后跟分隔符，避免吃掉"1.5 倍"这种正文）
    _re.compile(r"^\d+(?:\.\d+)*\s*[、．.)）]\s*"),
    # 1.1 空格 这种无尾分隔符的多级编号
    _re.compile(r"^\d+(?:\.\d+)+[ \u3000]+"),
    # ① ② 之类
    _re.compile(r"^[\u2460-\u2473]\s*"),
]


def strip_heading_prefix(text: str) -> str:
    """剥掉标题开头的手写编号前缀；剥不出结果时原样返回。

    只剥一层，且要求剩余内容非空——"1." 这种纯编号的标题保持原样更安全。
    """
    raw = text or ""
    stripped = raw.lstrip()
    leading = raw[:len(raw) - len(stripped)]
    for pattern in HEADING_PREFIX_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        rest = stripped[match.end():].lstrip()
        if not rest:
            continue                   # 标题只剩一个编号，别剥成空
        if rest[0].isdigit() and _re.match(r"^\d+(?:\.\d+)*\s*[、．.)）]", stripped):
            continue                   # "2024 年"这类不像编号，保守放过
        return leading + rest
    return raw
