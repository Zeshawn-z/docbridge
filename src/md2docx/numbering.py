"""为 docx 注入真实的多级列表编号定义。

python-docx 自带的空模板没有 numbering 部件，所以 `List Bullet` 之类的样式
落到 Word 里会变成"看起来像列表但没有项目符号"的普通段落。这里自己生成
`word/numbering.xml` 并挂到 document 部件上。

本模块同时承担两件事：
1. **列表编号**：无序 / 有序列表的多级符号与编号格式（固定两套 id）。
2. **标题自动编号**：把 1~6 级标题接进 Word 的多级列表体系，产物是真正的
   `w:numPr`（列表编号），而不是正文里手写的"一、"文本。

设计要点：
- 所有定义最终都会**合并注入**到已有的 numbering 部件里（python-docx 的默认
  模板自带 abstractNumId 0~8 / numId 1~9，直接覆盖会撞车）。
- `w:lvl` 的子元素必须严格按 schema 顺序写，顺序错了 Word 会弹"需要修复"。
- 标题编号用 `multiLevelType=multilevel`，这样"回到上一级时子级重新计数"
  才是 Word 的原生行为，不需要我们手工维护计数器。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .units import chars_to_twip, parse_chars

NUMBERING_PARTNAME = "/word/numbering.xml"
BULLET_NUM_ID = 100
ORDERED_NUM_ID = 101
HEADING_NUM_ID = 110
MAX_LEVEL = 9

# `w:lvl` 的子元素必须按这个顺序写，否则 Word 会提示文档需要修复。
LVL_ORDER = [
    "start", "numFmt", "lvlRestart", "pStyle", "isLgl", "suff", "lvlText",
    "lvlPicBulletId", "legacy", "lvlJc", "pPr", "rPr",
]

# 每级项目符号：字符 + 承载字体（用 Arial 避免 Symbol 字体在 WPS 下缺字形）
BULLET_CHARS = [("\u2022", "Arial"), ("\u25cb", "Arial"), ("\u25aa", "Arial"),
                ("\u2022", "Arial"), ("\u25cb", "Arial"), ("\u25aa", "Arial"),
                ("\u2022", "Arial"), ("\u25cb", "Arial"), ("\u25aa", "Arial")]

# 有序列表各级编号格式（numFmt, lvlText）
ORDERED_FORMATS = [("decimal", "%1."), ("lowerLetter", "%2)"), ("lowerRoman", "%3."),
                   ("decimal", "%4)"), ("lowerLetter", "%5)"),
                   ("lowerRoman", "%6."), ("decimal", "%7)"),
                   ("lowerLetter", "%8)"), ("lowerRoman", "%9.")]


# --------------------------------------------------------------------------
# 标题编号预设
# --------------------------------------------------------------------------
# 每个预设给出每一级（最多 6 级）的 (numFmt, lvlText)。
#   numFmt  Word 的编号格式：decimal / chineseCounting / lowerLetter / ...
#   lvlText 编号模板，%1 %2 表示"第 1/2 级"的序号
#   suff    编号与标题文字之间的分隔：space / nothing / tab
#
# 写"一、"这类自带尾缀的中文编号时用 suff=nothing，把分隔符并进 lvlText；
# 不同阅读器对自动 tab 的处理不一致，交给 Word 补制表符容易把标题顶得太远。


def _lvls(rows: list[tuple[str, str]], suff: str = "space") -> list[dict]:
    """把 (numFmt, lvlText) 列表补齐成 6 级完整定义。"""
    out: list[dict] = []
    for index in range(6):
        if index < len(rows):
            num_fmt, text = rows[index]
        elif rows:
            num_fmt, text = rows[-1]          # 超出的层级沿用最后一级的写法
        else:
            num_fmt, text = ("decimal", f"%{index + 1}.")
        out.append({"num_fmt": num_fmt, "text": text, "suff": suff, "start": 1})
    return out


#: 内置预设：名称 → 逐级编号定义
HEADING_PRESETS: dict[str, dict] = {
    # 1. / 1.1 / 1.1.1 —— 最通用的技术文档写法
    "decimal": {
        "label": "1 / 1.1 / 1.1.1",
        "levels": _lvls([("decimal", "%1."), ("decimal", "%1.%2"),
                         ("decimal", "%1.%2.%3"), ("decimal", "%1.%2.%3.%4"),
                         ("decimal", "%1.%2.%3.%4.%5"),
                         ("decimal", "%1.%2.%3.%4.%5.%6")], suff="space"),
    },
    # 一、/ 1.1 / 1.1.1 —— 中文公文与论文最常用的一档
    "cn-decimal": {
        "label": "一、/ 1.1 / 1.1.1",
        "levels": _lvls([("chineseCounting", "%1、"), ("decimal", "%1.%2"),
                         ("decimal", "%1.%2.%3"), ("decimal", "%1.%2.%3.%4"),
                         ("decimal", "%1.%2.%3.%4.%5"),
                         ("decimal", "%1.%2.%3.%4.%5.%6")], suff="space"),
    },
    # （一）/ 1.1 / 1.1.1 —— 章用中文括号序号，节回到阿拉伯数字
    "mixed-cn": {
        "label": "（一）/ 1.1 / 1.1.1",
        "levels": _lvls([("chineseCounting", "（%1）"), ("decimal", "%1.%2"),
                         ("decimal", "%1.%2.%3"), ("decimal", "%1.%2.%3.%4"),
                         ("decimal", "%1.%2.%3.%4.%5"),
                         ("decimal", "%1.%2.%3.%4.%5.%6")], suff="space"),
    },
    # 一、/ （一）/ 1. —— 完全中式的层级递进，适合公文
    "cn-nested": {
        "label": "一、/ （一）/ 1.",
        "levels": _lvls([("chineseCounting", "%1、"),
                         ("chineseCounting", "（%1）"),
                         ("decimal", "%1."), ("decimal", "%1)"),
                         ("lowerLetter", "%1)"), ("lowerRoman", "%1.")],
                        suff="nothing"),
    },
    # 第一章 / 1.1 / 1.1.1
    "cn-chapter": {
        "label": "第一章 / 1.1 / 1.1.1",
        "levels": _lvls([("chineseCounting", "第%1章"), ("decimal", "%1.%2"),
                         ("decimal", "%1.%2.%3"), ("decimal", "%1.%2.%3.%4"),
                         ("decimal", "%1.%2.%3.%4.%5"),
                         ("decimal", "%1.%2.%3.%4.%5.%6")], suff="space"),
    },
    # 一、/ （一）/ 1. / (1) —— 教材与标准文件里的经典四级
    "cn-standard": {
        "label": "一、/ （一）/ 1. / (1)",
        "levels": _lvls([("chineseCounting", "%1、"),
                         ("chineseCounting", "（%1）"),
                         ("decimal", "%1."), ("decimal", "(%1)"),
                         ("lowerLetter", "%1)"), ("lowerRoman", "%1.")],
                        suff="nothing"),
    },
    # 1) / a) / i)
    "paren": {
        "label": "1) / a) / i)",
        "levels": _lvls([("decimal", "%1)"), ("lowerLetter", "%1)"),
                         ("lowerRoman", "%1)"), ("decimal", "%1)"),
                         ("lowerLetter", "%1)"), ("lowerRoman", "%1)")],
                        suff="space"),
    },
    # 罗马数字，适合附录、序言部分
    "roman": {
        "label": "I. / I.1 / I.1.1",
        "levels": _lvls([("upperRoman", "%1."), ("decimal", "%1.%2"),
                         ("decimal", "%1.%2.%3"), ("decimal", "%1.%2.%3.%4"),
                         ("decimal", "%1.%2.%3.%4.%5"),
                         ("decimal", "%1.%2.%3.%4.%5.%6")], suff="space"),
    },
}


def preset_names() -> list[str]:
    """所有内置预设名，按展示顺序排列。"""
    return list(HEADING_PRESETS)


def preset_desc(name: str) -> str:
    """预设的中文说明（GUI 下拉与报错信息共用）。"""
    item = HEADING_PRESETS.get(name)
    return item["label"] if item else "未知预设"


@dataclass
class NumberingPlan:
    """一份编号定义：一个 abstractNum + 它的 lvl 列表。"""

    abstract_id: int
    num_id: int
    levels: list[dict] = field(default_factory=list)
    multi_level_type: str = "hybridMultilevel"

    def level(self, ilvl: int) -> dict:
        if not self.levels:
            return {"num_fmt": "decimal", "text": f"%{ilvl + 1}.", "suff": "space",
                    "start": 1}
        return self.levels[min(ilvl, len(self.levels) - 1)]


def _sub(parent, tag: str, **attrs):
    el = OxmlElement(tag)
    for key, value in attrs.items():
        el.set(qn(f"w:{key}"), str(value))
    parent.append(el)
    return el


def _sub_ordered(parent, tag: str, **attrs):
    """按 LVL_ORDER 插入子元素——`w:lvl` 的顺序错了 Word 会报修复。"""
    el = _sub(parent, tag, **attrs)
    parent.remove(el)
    local = tag.rsplit("}", 1)[-1].split(":")[-1]
    my = LVL_ORDER.index(local)
    for existing in parent:
        name = existing.tag.rsplit("}", 1)[-1]
        if name in LVL_ORDER and LVL_ORDER.index(name) > my:
            existing.addprevious(el)
            return el
    parent.append(el)
    return el


def _lvl_wrapper(abstract, ilvl: int, *, text: str, num_fmt: str, font: str = "",
                 left_chars: float = 0.0, hanging_chars: float = 0.0,
                 font_pt: float = 12.0, start: int = 1, suff: str = "space",
                 align: str = "left", lvl_restart: int | None = None, run_format=None):
    """写一个 `w:lvl`。

    `suff` 控制编号与正文之间的分隔符。写中文顿号这类自带尾缀的方案时用
    "nothing"，避免 Word 再补一个制表符把标题文字推远。
    """
    lvl = _sub(abstract, "w:lvl", ilvl=ilvl)
    _sub_ordered(lvl, "w:start", val=start)
    _sub_ordered(lvl, "w:numFmt", val=num_fmt)
    if lvl_restart is not None:
        _sub_ordered(lvl, "w:lvlRestart", val=lvl_restart)
    if suff and suff != "space":
        _sub_ordered(lvl, "w:suff", val=suff)
    _sub_ordered(lvl, "w:lvlText", val=text)
    _sub_ordered(lvl, "w:lvlJc", val=align)
    ppr = OxmlElement("w:pPr")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:leftChars"), str(int(round(left_chars * 100))))
    ind.set(qn("w:left"), str(chars_to_twip(left_chars, font_pt)))
    ind.set(qn("w:hangingChars"), str(int(round(hanging_chars * 100))))
    ind.set(qn("w:hanging"), str(chars_to_twip(hanging_chars, font_pt)))
    ppr.append(ind)
    lvl.append(ppr)
    if font or run_format:
        rpr = OxmlElement("w:rPr")
        if font:
            rfonts = OxmlElement("w:rFonts")
            rfonts.set(qn("w:ascii"), font)
            rfonts.set(qn("w:hAnsi"), font)
            rfonts.set(qn("w:hint"), "default")
            rpr.append(rfonts)
        if run_format:
            from .ooxml import apply_run_format
            apply_run_format(rpr, **run_format)
        lvl.append(rpr)
    return lvl


# --------------------------------------------------------------------------
# 构建
# --------------------------------------------------------------------------

def list_plans(list_cfg: dict, ordered_cfg: dict | None = None) -> list[NumberingPlan]:
    """构建无序列表与有序列表的编号定义。"""
    bullet = _plan_from_list_cfg(list_cfg, BULLET_NUM_ID, bullet_mode=True)
    ordered = _plan_from_list_cfg(ordered_cfg or list_cfg, ORDERED_NUM_ID,
                                  bullet_mode=False)
    return [bullet, ordered]


def _plan_from_list_cfg(cfg: dict, num_id: int, *, bullet_mode: bool) -> NumberingPlan:
    raw_left = cfg.get("left_indent", "2字符")
    parsed = parse_chars(raw_left)
    base_left = parsed if parsed is not None else 2.0
    step = float(cfg.get("level_step_chars", 2))
    hanging = float(cfg.get("hanging_indent_chars", 2))
    levels = []
    for ilvl in range(MAX_LEVEL):
        if bullet_mode:
            ch, font = BULLET_CHARS[ilvl]
            levels.append({"num_fmt": "bullet", "text": ch, "suff": "space",
                           "start": 1, "font": font,
                           "left": base_left + step * ilvl, "hanging": hanging})
        else:
            num_fmt, text = ORDERED_FORMATS[ilvl]
            levels.append({"num_fmt": num_fmt, "text": text, "suff": "space",
                           "start": 1, "font": "",
                           "left": base_left + step * ilvl, "hanging": hanging})
    return NumberingPlan(abstract_id=num_id, num_id=num_id, levels=levels,
                         multi_level_type="hybridMultilevel")


def heading_plan(cfg: dict, font_pt: float = 15.0) -> NumberingPlan:
    """按配置构建标题自动编号定义。

    配置项（来自 `config/default.yaml` 的 `numbering`）：
        preset     预设名，见 HEADING_PRESETS
        levels     参与编号的最大层级（1~6）
        skip_first_level  第 1 级标题不编号，第 2 级起接第 1 级编号
        starts     每级起始编号，如 [1, 1, 1]
        left_indent_chars    编号相对标题缩进的字符数
        hanging_indent_chars 悬挂缩进字符数
        format     逐级覆盖：{1: {num_fmt: ..., text: ..., suff: ..., start: ...}}

    关于 `skip_first_level`：Markdown 里的 `#` 常被当作整篇的主标题（章名），
    它自己不参与编号，`##` 才是"第一章"。注意**编号定义本身不随这个开关移动**
    ——预设第 1 项永远落在 ilvl=0 上，代表"编号里的第 1 级"。至于让哪一级标题
    去用它（跳过时是 Markdown 第 2 级），是 renderer 的职责，见
    `Renderer._numbering_level`。两边各管一头，层级对应关系只有一处真相。
    所以本函数不需要针对跳级动 `src`，`format` 的键也始终按预设级数算。
    """
    preset = str(cfg.get("preset") or "decimal")
    base = HEADING_PRESETS.get(preset) or HEADING_PRESETS["decimal"]
    src = [dict(item) for item in base["levels"]]

    override = cfg.get("format") or {}
    for key, spec in (override or {}).items():
        try:
            ilvl = int(key) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= ilvl < len(src) and isinstance(spec, dict):
            src[ilvl].update({k: v for k, v in spec.items() if v is not None})

    try:
        max_level = int(cfg.get("levels", 6) or 6)
    except (TypeError, ValueError):
        max_level = 6
    max_level = max(1, min(6, max_level))
    starts = cfg.get("starts") or []
    try:
        left = float(cfg.get("left_indent_chars", 0) or 0)
    except (TypeError, ValueError):
        left = 0.0
    try:
        hanging = float(cfg.get("hanging_indent_chars", 0) or 0)
    except (TypeError, ValueError):
        hanging = 0.0

    # 编号定义本身**不因为跳级而移动**：预设第 1 项永远落在 ilvl=0 上，
    # 它代表的就是"编号里的第 1 级"。跳级只影响"哪一级标题去用它"——
    # 那是 renderer 的 `_numbering_level` 负责的事（Markdown 第 2 级标题
    # 接 ilvl=0）。两边各管一头，层级对应关系才不会有第二处真相。

    levels = []
    for ilvl in range(6):
        item = src[ilvl]
        enabled = ilvl < max_level
        start = 1
        if ilvl < len(starts):
            try:
                start = int(starts[ilvl])
            except (TypeError, ValueError):
                start = 1
        levels.append({
            "num_fmt": str(item.get("num_fmt", "decimal")),
            "text": str(item.get("text", f"%{ilvl + 1}.")),
            "suff": str(item.get("suff", "space")),
            "start": start,
            "font": "",
            "left": left,
            "hanging": hanging,
            "enabled": enabled,
            # multilevel 语义下，编号回到上一级时子级自动重新计数
            "lvl_restart": 0 if ilvl == 0 else None,
        })
    return NumberingPlan(abstract_id=HEADING_NUM_ID, num_id=HEADING_NUM_ID,
                         levels=levels, multi_level_type="multilevel")


def build_numbering_xml(plans: list[NumberingPlan] | dict) -> bytes:
    """按配置生成一份独立的 numbering.xml（文档本来没有该部件时用）。"""
    root = _build_numbering_root(plans)
    from lxml import etree
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                          standalone=True)


def _write_plan(root, plan: NumberingPlan, font_pt: float) -> None:
    abstract = _sub(root, "w:abstractNum", abstractNumId=plan.abstract_id)
    _sub(abstract, "w:multiLevelType", val=plan.multi_level_type)
    for ilvl in range(MAX_LEVEL):
        spec = plan.level(ilvl)
        _lvl_wrapper(
            abstract, ilvl,
            text=spec.get("text", f"%{ilvl + 1}."),
            num_fmt=spec.get("num_fmt", "decimal"),
            font=spec.get("font", ""),
            left_chars=float(spec.get("left", 0.0)),
            hanging_chars=float(spec.get("hanging", 0.0)),
            font_pt=float(spec.get('_font_pt', font_pt)),
            start=int(spec.get("start", 1)),
            suff=str(spec.get("suff", "space")),
            lvl_restart=spec.get("lvl_restart"),
            run_format=spec.get('run_format'),
        )
    num = _sub(root, "w:num", numId=plan.num_id)
    _sub(num, "w:abstractNumId", val=plan.abstract_id)


def _build_numbering_root(plans: list[NumberingPlan] | dict):
    """生成 w:numbering 根元素及全部子元素（不序列化）。

    兼容旧的调用方式：传 dict 时按"无序 + 有序"两套列表定义处理，
    保证老调用点不会因为签名变化而挂掉。
    """
    if isinstance(plans, dict):
        plans = list_plans(plans)
    font_pt = 12.0
    for plan in plans:
        for spec in plan.levels:
            font_pt = float(spec.get("_font_pt", font_pt))
    root = OxmlElement("w:numbering")
    for plan in plans:
        _write_plan(root, plan, font_pt)
    return root


def _inject_into(existing_root, fresh_root) -> None:
    """把我的编号定义合并进已有 numbering.xml。

    注意 schema 顺序：w:abstractNum 必须全部排在 w:num 之前，所以抽象编号
    插到最后一个 abstractNum 之后，num 追加到末尾。
    """
    from lxml import etree

    def _local(el):
        return etree.QName(el).localname

    mine_abstract = {str(el.get(qn("w:abstractNumId"))) for el in fresh_root
                     if _local(el) == "abstractNum"}
    mine_num = {str(el.get(qn("w:numId"))) for el in fresh_root
                if _local(el) == "num"}

    for el in list(existing_root):
        tag = _local(el)
        if tag == "abstractNum" and str(el.get(qn("w:abstractNumId"))) in mine_abstract:
            existing_root.remove(el)
        elif tag == "num" and str(el.get(qn("w:numId"))) in mine_num:
            existing_root.remove(el)

    abstract_anchor = None
    for el in existing_root:
        if _local(el) == "abstractNum":
            abstract_anchor = el
        elif _local(el) == "num":
            break
    for el in list(fresh_root):
        if _local(el) == "abstractNum":
            if abstract_anchor is None:
                existing_root.insert(0, el)
            else:
                abstract_anchor.addnext(el)
            abstract_anchor = el
    for el in list(fresh_root):
        if _local(el) == "num":
            existing_root.append(el)


def ensure_numbering_part(document, plans: list[NumberingPlan] | dict):
    """确保文档里有我们定义的多级列表编号（已有部件则就地合并）。

    python-docx 把 numbering.xml 当作 XmlPart 加载，序列化时以 `_element`
    为准，所以必须改元素树本身，改 `_blob` 是无效的。
    """
    from lxml import etree

    fresh = _build_numbering_root(plans)
    package = document.part.package
    for part in package.iter_parts():
        if str(part.partname) != NUMBERING_PARTNAME:
            continue
        element = getattr(part, "_element", None)
        if element is not None:
            _inject_into(element, fresh)
            return part
        root = etree.fromstring(part.blob)
        _inject_into(root, fresh)
        part._blob = etree.tostring(root, xml_declaration=True,
                                    encoding="UTF-8", standalone=True)
        return part

    blob = etree.tostring(fresh, xml_declaration=True, encoding="UTF-8",
                          standalone=True)
    part = Part(PackURI(NUMBERING_PARTNAME), CT.WML_NUMBERING, blob, package)
    document.part.relate_to(part, RT.NUMBERING)
    return part
