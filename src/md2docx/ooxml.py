"""OOXML 底层排版工具。

python-docx 只暴露了一部分属性（例如段落缩进不支持"2 字符"的东亚版本
`w:firstLineChars`，run 不支持 `w:shd` 底纹）。这里补齐这些能力，并且严格
按 CT_RPr / CT_PPr 的 schema 顺序插入子元素，避免生成 Word 打不开的文件。
"""

from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

RT_HYPERLINK = RT.HYPERLINK

from .units import chars_to_twip, pt_to_twip

# --------------------------------------------------------------------------
# schema 顺序表（截取自 ECMA-376 CT_RPr / CT_PPr）
# --------------------------------------------------------------------------

RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid",
    "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs",
    "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs",
    "em", "lang", "eastAsianLayout", "specVanish", "oMath",
]

PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
    "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
    "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE",
    "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind",
    "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
    "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
]

TBLPR_ORDER = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders",
    "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription",
    "tblPrChange",
]

TRPR_ORDER = ["cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
              "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden",
              "ins", "del", "trPrChange"]

TCPR_ORDER = ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
              "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
              "headers", "cellIns", "cellDel", "cellMerge", "tcPrChange"]

STYLE_ORDER = ["name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden",
               "uiPriority", "semiHidden", "unhideWhenUsed", "qFormat", "locked",
               "personal", "personalCompose", "personalReply", "rsid", "pPr", "rPr",
               "tblPr", "trPr", "tcPr", "tblStylePr"]

# 供自检工具按 schema 顺序校验
ORDER_MAP = {
    "rPr": RPR_ORDER,
    "pPr": PPR_ORDER,
    "tblPr": TBLPR_ORDER,
    "trPr": TRPR_ORDER,
    "tcPr": TCPR_ORDER,
    "style": STYLE_ORDER,
}

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

ALIGN_MAP = {
    "left": "left",
    "start": "left",
    "center": "center",
    "centre": "center",
    "right": "right",
    "end": "right",
    "both": "both",
    "justify": "both",
    "distribute": "distribute",
}

# 英文名（西文）Run 字体与东亚字体的 slot 对应
_THEME_ATTRS = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def insert_ordered(parent, child, order: list[str]):
    """按 schema 顺序把 child 插入 parent。"""
    index = order.index(local_name(child.tag))
    for existing in parent:
        name = local_name(existing.tag)
        if name in order and order.index(name) > index:
            existing.addprevious(child)
            return child
    parent.append(child)
    return child


def ensure(parent, tag: str, order: list[str]):
    """取到 parent 下 tag 的子元素，没有就按顺序新建。"""
    el = parent.find(qn(tag))
    if el is None:
        el = OxmlElement(tag)
        insert_ordered(parent, el, order)
    return el


def _set_onoff(rpr, tag: str, value: bool) -> None:
    """写 w:b / w:i 这类开关：显式写 val=0 才能压掉样式里的粗体。"""
    el = ensure(rpr, tag, RPR_ORDER)
    el.set(qn("w:val"), "1" if value else "0")


#: 字色取 auto 时落到哪个值。Word 的 `w:color val="auto"` 是"交给主题决定"，
#: 而 Word 内置样式（标题 1、标题 2、超链接…）各自带着主题色，一旦某个元素
#: 没被我们显式刷过色，就会透出蓝色系的主题色。写死纯黑才能保证
#: Word / WPS / 各种阅读器里都是黑的。
AUTO_COLOR = "000000"


def resolve_color(value) -> str:
    """把配置里的字色归一化成 OOXML 的 6 位十六进制。

    `auto`（以及空值）一律解析成纯黑，理由见 `AUTO_COLOR`。
    """
    text = str(value or "").strip().lstrip("#")
    if not text or text.lower() == "auto":
        return AUTO_COLOR
    return text


# --------------------------------------------------------------------------
# 字符格式
# --------------------------------------------------------------------------

def apply_run_format(rpr, *, font_zh=None, font_en=None, size_pt=None, bold=None,
                     italic=None, underline=None, strike=None, color=None,
                     spacing_pt=None, vert_align=None) -> None:
    """把排版参数写进一个 rPr 元素。None 表示"不动这项"。"""
    if font_zh or font_en:
        rfonts = ensure(rpr, "w:rFonts", RPR_ORDER)
        for attr in _THEME_ATTRS:
            if rfonts.get(qn(attr)) is not None:
                del rfonts.attrib[qn(attr)]
        if font_en:
            rfonts.set(qn("w:ascii"), font_en)
            rfonts.set(qn("w:hAnsi"), font_en)
            rfonts.set(qn("w:cs"), font_en)
        if font_zh:
            rfonts.set(qn("w:eastAsia"), font_zh)
        # hint=eastAsia 让中英混排时的标点走东亚字体
        rfonts.set(qn("w:hint"), "eastAsia")

    if size_pt is not None:
        half_points = str(int(round(float(size_pt) * 2)))
        ensure(rpr, "w:sz", RPR_ORDER).set(qn("w:val"), half_points)
        ensure(rpr, "w:szCs", RPR_ORDER).set(qn("w:val"), half_points)

    if bold is not None:
        _set_onoff(rpr, "w:b", bool(bold))
        _set_onoff(rpr, "w:bCs", bool(bold))
    if italic is not None:
        _set_onoff(rpr, "w:i", bool(italic))
        _set_onoff(rpr, "w:iCs", bool(italic))
    if strike is not None:
        _set_onoff(rpr, "w:strike", bool(strike))
    if underline is not None:
        u = ensure(rpr, "w:u", RPR_ORDER)
        u.set(qn("w:val"), "single" if underline else "none")
    if color:
        ensure(rpr, "w:color", RPR_ORDER).set(qn("w:val"), resolve_color(color))
    if spacing_pt is not None:
        ensure(rpr, "w:spacing", RPR_ORDER).set(qn("w:val"), str(pt_to_twip(spacing_pt)))
    if vert_align:
        ensure(rpr, "w:vertAlign", RPR_ORDER).set(qn("w:val"), vert_align)


def run_rpr(run):
    return run._element.get_or_add_rPr()


def style_rpr(style):
    return style.element.get_or_add_rPr()


def para_ppr(paragraph):
    return paragraph._p.get_or_add_pPr()


# --------------------------------------------------------------------------
# 段落格式
# --------------------------------------------------------------------------

def apply_para_format(ppr, *, line_spacing=None, space_before_pt=None, space_after_pt=None,
                      align=None, first_line=None, left=None, hanging=None,
                      right_pt=None, keep_next=None, keep_lines=None,
                      page_break_before=None, outline_level=None,
                      contextual_spacing=None, shading=None, borders=None,
                      font_pt_for_chars=12.0, num_id=None, num_level=None,
                      widow_control=None, snap_to_grid=None) -> None:
    """写段落属性。

    first_line / left / hanging 可以是 "2字符" 这类字符量（走东亚版式的
    `w:firstLineChars`），也可以是 "0.74cm"/12 这类长度。
    """
    if keep_next is not None:
        _set_onoff_p(ppr, "w:keepNext", keep_next)
    if keep_lines is not None:
        _set_onoff_p(ppr, "w:keepLines", keep_lines)
    if page_break_before is not None:
        _set_onoff_p(ppr, "w:pageBreakBefore", page_break_before)
    if widow_control is not None:
        _set_onoff_p(ppr, "w:widowControl", widow_control)
    if contextual_spacing is not None:
        _set_onoff_p(ppr, "w:contextualSpacing", contextual_spacing)
    if snap_to_grid is not None:
        _set_onoff_p(ppr, "w:snapToGrid", snap_to_grid)

    if num_id is not None:
        num_pr = ensure(ppr, "w:numPr", PPR_ORDER)
        ensure(num_pr, "w:ilvl", ["ilvl", "numId"]).set(
            qn("w:val"), str(num_level or 0))
        ensure(num_pr, "w:numId", ["ilvl", "numId"]).set(qn("w:val"), str(num_id))
    else:
        existing = ppr.find(qn("w:numPr"))
        if existing is not None:
            ppr.remove(existing)

    if borders:
        p_bdr = ensure(ppr, "w:pBdr", PPR_ORDER)
        for edge, spec in borders.items():
            tag = f"w:{edge}"
            el = p_bdr.find(qn(tag))
            if el is None:
                el = OxmlElement(tag)
                p_bdr.append(el)
            el.set(qn("w:val"), spec.get("style", "single"))
            el.set(qn("w:sz"), str(spec.get("size", 6)))
            el.set(qn("w:space"), str(spec.get("space", 1)))
            el.set(qn("w:color"), str(spec.get("color", "auto")).lstrip("#"))

    if shading:
        shd = ensure(ppr, "w:shd", PPR_ORDER)
        shd.set(qn("w:val"), shading.get("val", "clear"))
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), str(shading.get("fill", "FFFFFF")).lstrip("#"))

    if line_spacing is not None:
        spacing = ensure(ppr, "w:spacing", PPR_ORDER)
        spacing.set(qn("w:line"), str(int(round(float(line_spacing) * 240))))
        spacing.set(qn("w:lineRule"), "auto")

    if space_before_pt is not None or space_after_pt is not None:
        spacing = ensure(ppr, "w:spacing", PPR_ORDER)
        if space_before_pt is not None:
            spacing.set(qn("w:before"), str(pt_to_twip(space_before_pt)))
            spacing.set(qn("w:beforeLines"), "0")
        if space_after_pt is not None:
            spacing.set(qn("w:after"), str(pt_to_twip(space_after_pt)))
            spacing.set(qn("w:afterLines"), "0")

    _apply_indent(ppr, first_line=first_line, left=left, hanging=hanging,
                  right_pt=right_pt, font_pt=font_pt_for_chars)

    if align:
        jc = ensure(ppr, "w:jc", PPR_ORDER)
        jc.set(qn("w:val"), ALIGN_MAP.get(str(align).lower(), "left"))
    if outline_level is not None:
        ensure(ppr, "w:outlineLvl", PPR_ORDER).set(qn("w:val"), str(outline_level))


def _set_onoff_p(ppr, tag: str, value: bool) -> None:
    el = ensure(ppr, tag, PPR_ORDER)
    el.set(qn("w:val"), "1" if value else "0")


def _apply_indent(ppr, *, first_line, left, hanging, right_pt, font_pt) -> None:
    """写 w:ind。

    OOXML 里 w:firstLine 与 w:hanging 互斥，同段同时出现会让 Word 报错。
    规则：只要给了悬挂缩进，就完全不写 firstLine（悬挂本身就意味着首行不缩进）。
    """
    from .units import parse_chars, parse_length_pt

    if first_line is None and left is None and hanging is None and right_pt is None:
        return
    ind = ensure(ppr, "w:ind", PPR_ORDER)

    def _clear(*attrs):
        for attr in attrs:
            if ind.get(qn(attr)) is not None:
                del ind.attrib[qn(attr)]

    hanging_chars = parse_chars(hanging) if hanging is not None else None
    hanging_pt = None if hanging_chars is not None else (
        parse_length_pt(hanging) if hanging is not None else None)
    has_hanging = bool(hanging_chars) or bool(hanging_pt)

    if hanging is not None:
        if has_hanging:
            if hanging_chars is not None:
                ind.set(qn("w:hangingChars"), str(int(round(hanging_chars * 100))))
                ind.set(qn("w:hanging"), str(chars_to_twip(hanging_chars, font_pt)))
            else:
                ind.set(qn("w:hanging"), str(pt_to_twip(hanging_pt)))
        else:
            _clear("w:hanging", "w:hangingChars")

    if has_hanging:
        # 悬挂缩进在场时不能写 firstLine，否则 Word 认为缩进定义冲突
        _clear("w:firstLine", "w:firstLineChars")
    elif first_line is not None:
        chars = parse_chars(first_line)
        if chars is not None:
            ind.set(qn("w:firstLineChars"), str(int(round(chars * 100))))
            ind.set(qn("w:firstLine"), str(chars_to_twip(chars, font_pt)))
        else:
            pt = parse_length_pt(first_line)
            if pt:
                ind.set(qn("w:firstLine"), str(pt_to_twip(pt)))
                _clear("w:firstLineChars")
            else:
                _clear("w:firstLine", "w:firstLineChars")

    if left is not None:
        chars = parse_chars(left)
        if chars is not None:
            ind.set(qn("w:leftChars"), str(int(round(chars * 100))))
            ind.set(qn("w:left"), str(chars_to_twip(chars, font_pt)))
        else:
            pt = parse_length_pt(left)
            if pt or pt == 0:
                ind.set(qn("w:left"), str(pt_to_twip(pt)))
                _clear("w:leftChars")

    if right_pt is not None:
        ind.set(qn("w:right"), str(pt_to_twip(right_pt)))


# --------------------------------------------------------------------------
# 页面 / 文档级
# --------------------------------------------------------------------------

PAGE_SIZES = {
    "A4": (21.0, 29.7),
    "A3": (29.7, 42.0),
    "B5": (17.6, 25.0),
    "Letter": (21.59, 27.94),
}


def apply_page(section, page_cfg: dict) -> None:
    from docx.shared import Cm
    from .units import parse_length_pt

    name = str(page_cfg.get("size", "A4"))
    if name in PAGE_SIZES:
        w_cm, h_cm = PAGE_SIZES[name]
        section.page_width = Cm(w_cm)
        section.page_height = Cm(h_cm)

    orientation = str(page_cfg.get("orientation", "portrait")).lower()
    if orientation in ("landscape", "横向") and section.page_width < section.page_height:
        section.page_width, section.page_height = section.page_height, section.page_width

    margins = page_cfg.get("margin") or {}
    for key, attr in (("top", "top_margin"), ("bottom", "bottom_margin"),
                      ("left", "left_margin"), ("right", "right_margin")):
        if key in margins:
            setattr(section, attr, Cm(parse_length_pt(margins[key]) / 72.0 * 2.54))
    if "header" in margins:
        section.header_distance = Cm(parse_length_pt(margins["header"]) / 72.0 * 2.54)
    if "footer" in margins:
        section.footer_distance = Cm(parse_length_pt(margins["footer"]) / 72.0 * 2.54)

    grid = page_cfg.get("grid")
    if grid is not None:
        sect_pr = section._sectPr
        doc_grid = ensure(sect_pr, "w:docGrid", ["docGrid"])
        doc_grid.set(qn("w:type"), "lines" if grid else "default")


def apply_doc_defaults(document, style_cfg: dict) -> None:
    """写 styles.xml 的 docDefaults，兜住没被打过样式的文字。"""
    styles_el = document.styles.element
    doc_defaults = styles_el.find(qn("w:docDefaults"))
    if doc_defaults is None:
        doc_defaults = OxmlElement("w:docDefaults")
        styles_el.insert(0, doc_defaults)
    rpr_default = ensure(doc_defaults, "w:rPrDefault", ["rPrDefault", "pPrDefault"])
    rpr = ensure(rpr_default, "w:rPr", RPR_ORDER)
    apply_run_format(rpr,
                     font_zh=style_cfg.get("font_zh"),
                     font_en=style_cfg.get("font_en"),
                     size_pt=None,
                     # 这里必须显式写字色。docDefaults 不写的话，没被样式覆盖的
                     # 文字会走 Word 的主题文字色，而主题色不一定是纯黑。
                     color=style_cfg.get("color") or AUTO_COLOR)
    ppr_default = ensure(doc_defaults, "w:pPrDefault", ["rPrDefault", "pPrDefault"])
    ppr = ensure(ppr_default, "w:pPr", PPR_ORDER)
    apply_para_format(ppr, line_spacing=style_cfg.get("line_spacing"))


def add_page_number_field(paragraph, size_pt: float = 9.0,
                          font_zh: str = "宋体", font_en: str = "Times New Roman") -> None:
    """在页脚段落里插入 PAGE 域。"""
    run = paragraph.add_run()
    apply_run_format(run_rpr(run), font_zh=font_zh, font_en=font_en, size_pt=size_pt)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, end):
        run._element.append(el)


def add_toc_field(paragraph, levels: str = "1-3") -> None:
    """插入目录域（Word 打开后按 F9 更新）。"""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f' TOC \\o "{levels}" \\h \\z \\u '
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "右键此处选择“更新域”生成目录"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, separate, placeholder, end):
        run._element.append(el)


# --------------------------------------------------------------------------
# 表格
# --------------------------------------------------------------------------

_DEFAULT_TABLE_BORDER = {"style": "single", "size": 4, "space": 0, "color": "7F7F7F"}


def set_table_borders(table, border: dict | None = None, edges: tuple = (
        "top", "left", "bottom", "right", "insideH", "insideV")) -> None:
    spec = dict(_DEFAULT_TABLE_BORDER)
    spec.update(border or {})
    tbl_pr = table._tbl.tblPr
    borders = ensure(tbl_pr, "w:tblBorders", TBLPR_ORDER)
    for edge in edges:
        tag = f"w:{edge}"
        el = borders.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            borders.append(el)
        el.set(qn("w:val"), str(spec["style"]))
        el.set(qn("w:sz"), str(spec["size"]))
        el.set(qn("w:space"), str(spec["space"]))
        el.set(qn("w:color"), str(spec["color"]).lstrip("#"))


def set_table_width_pct(table, pct: int = 100) -> None:
    tbl_pr = table._tbl.tblPr
    width = ensure(tbl_pr, "w:tblW", TBLPR_ORDER)
    width.set(qn("w:type"), "pct")
    width.set(qn("w:w"), str(int(pct * 50)))  # 50 分之一百分点


def set_table_layout_fixed(table, fixed: bool = False) -> None:
    tbl_pr = table._tbl.tblPr
    layout = ensure(tbl_pr, "w:tblLayout", TBLPR_ORDER)
    layout.set(qn("w:type"), "fixed" if fixed else "autofit")


def set_table_cell_margins(table, top=0.05, bottom=0.05, left=0.1, right=0.1) -> None:
    tbl_pr = table._tbl.tblPr
    mar = ensure(tbl_pr, "w:tblCellMar", TBLPR_ORDER)
    for edge, cm_value in (("top", top), ("bottom", bottom),
                           ("left", left), ("right", right)):
        el = ensure(mar, f"w:{edge}", ["top", "start", "left", "bottom", "end", "right"])
        el.set(qn("w:type"), "dxa")
        el.set(qn("w:w"), str(int(round(cm_value * 567))))


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = ensure(tc_pr, "w:shd", TCPR_ORDER)
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), str(fill).lstrip("#"))


def set_cell_valign(cell, valign: str = "center") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    ensure(tc_pr, "w:vAlign", TCPR_ORDER).set(qn("w:val"), valign)


def repeat_header_row(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = ensure(tr_pr, "w:tblHeader", TRPR_ORDER)
    el.set(qn("w:val"), "1")


def set_row_cant_split(row, cant_split: bool = True) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = ensure(tr_pr, "w:cantSplit", TRPR_ORDER)
    el.set(qn("w:val"), "1" if cant_split else "0")


def set_cell_width(cell, twip: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    width = ensure(tc_pr, "w:tcW", TCPR_ORDER)
    width.set(qn("w:type"), "dxa")
    width.set(qn("w:w"), str(int(twip)))


def set_grid_cols(table, widths_twip: list[int]) -> None:
    """把列宽写进 tblGrid，配合 fixed 布局让列宽可控。"""
    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is None:
        return
    cols = grid.findall(qn("w:gridCol"))
    for col, width in zip(cols, widths_twip):
        col.set(qn("w:w"), str(int(width)))


def preserve_space(run) -> None:
    """让 run 里的首尾空格不被 Word 吃掉（代码块对齐要用）。"""
    for t in run._element.findall(qn("w:t")):
        t.set(XML_SPACE, "preserve")
