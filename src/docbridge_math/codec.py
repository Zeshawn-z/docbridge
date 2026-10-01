"""LaTeX → MathML → editable Office Math or a self-contained PNG."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from threading import RLock
from xml.etree import ElementTree as ET


class FormulaError(ValueError):
    """A formula cannot be converted faithfully by the local backend."""


_render_lock = RLock()
MAX_SOURCE = 16000


def latex_to_mathml(source: str, display=False) -> str:
    from latex2mathml.converter import convert
    if not source.strip() or len(source) > MAX_SOURCE:
        raise FormulaError('公式为空或超过 16000 字符。')
    try:
        result = convert(source, display='block' if display else 'inline')
        tree = ET.fromstring(result)
        # latex2mathml keeps unknown commands as identifier text. Rendering
        # that text would appear successful while changing the formula.
        for node in tree.iter():
            if node.tag.rsplit('}', 1)[-1] in ('mi', 'mo'):
                unknown = re.search(r'\\[A-Za-z]+', node.text or '')
                if unknown:
                    raise FormulaError(f'暂不支持命令 {unknown.group()}。')
        return result
    except FormulaError:
        raise
    except Exception as exc:
        raise FormulaError(f'LaTeX 解析失败：{exc}') from exc


def latex_to_omml(source: str, display=False, size_pt=12):
    import mathml2omml
    from lxml import etree
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    try:
        xml = mathml2omml.convert(latex_to_mathml(source, display))
        namespace = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
        wrapper = etree.fromstring(f'<root xmlns:m="{namespace}">{xml}</root>')
        equation = wrapper[0]
        # mathml2omml represents non-stretch accents as generic upper/lower
        # limits. Repair those nodes to Office Math accents/bars.
        accents = {'^': '̂', '~': '̃', '˜': '̃', '˙': '̇', '¨': '̈',
                   'ˇ': '̌', '˘': '̆', '´': '́', '`': '̀'}
        for limit in list(equation.iter()):
            if limit.tag not in (qn('m:limUpp'), qn('m:limLow')):
                continue
            marker = limit.find(qn('m:lim'))
            if marker is None:
                continue
            text = ''.join(t.text or '' for t in marker.iter(qn('m:t')))
            upper = limit.tag == qn('m:limUpp')
            if text in accents and upper:
                replacement = OxmlElement('m:acc')
                props = OxmlElement('m:accPr')
                symbol = OxmlElement('m:chr')
                symbol.set(qn('m:val'), accents[text])
            elif text in ('―', '¯', '‾', '_'):
                replacement = OxmlElement('m:bar')
                props = OxmlElement('m:barPr')
                symbol = OxmlElement('m:pos')
                symbol.set(qn('m:val'), 'top' if upper else 'bot')
            else:
                continue
            props.append(symbol)
            replacement.append(props)
            base = limit.find(qn('m:e'))
            if base is not None:
                replacement.append(base)
            limit.getparent().replace(limit, replacement)
        for run in equation.iter(qn('m:r')):
            props = OxmlElement('w:rPr')
            fonts = OxmlElement('w:rFonts')
            for attr in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
                fonts.set(qn('w:' + attr), 'Cambria Math')
            props.append(fonts)
            size = OxmlElement('w:sz')
            size.set(qn('w:val'), str(round(float(size_pt) * 2)))
            props.append(size)
            # Office Math runs use m:rPr followed by w:rPr then m:t.
            insert = 1 if len(run) and run[0].tag == qn('m:rPr') else 0
            run.insert(insert, props)
        if display:
            paragraph = OxmlElement('m:oMathPara')
            props = OxmlElement('m:oMathParaPr')
            alignment = OxmlElement('m:jc')
            alignment.set(qn('m:val'), 'center')
            props.append(alignment)
            paragraph.append(props)
            paragraph.append(equation)
            return paragraph
        return equation
    except FormulaError:
        raise
    except Exception as exc:
        raise FormulaError(f'Word 公式转换失败：{exc}') from exc


@dataclass(frozen=True)
class FormulaImage:
    data: bytes
    width_pt: float
    height_pt: float
    depth_pt: float


def render_png(source: str, display=False, size_pt=12) -> FormulaImage:
    """Render at 288 dpi. All SVG glyphs are paths; no system fonts or GUI."""
    import ziamath
    import resvg_py
    try:
        mathml = latex_to_mathml(source, display)
        with _render_lock:
            expression = ziamath.Math(mathml, size=float(size_pt) * 96 / 72)
            for node in ET.fromstring(mathml).iter():
                for char in node.text or '':
                    if (not char.isspace() and char not in '\u2061\u2062\u2063\u2064\u200b\u200c\u200d'
                            and not expression.font.glyphindex(char)):
                        raise FormulaError(f'内置数学字体没有字符 {char}，请使用可编辑公式。')
            svg = expression.svgxml()
            width, height = float(svg.get('width')), float(svg.get('height'))
            if (not all(math.isfinite(v) and v > 0 for v in (width, height))
                    or width > 8000 or height > 4000 or width * height > 2_000_000):
                raise FormulaError('公式图片尺寸过大。')
            data = resvg_py.svg_to_bytes(svg_string=ET.tostring(svg, encoding='unicode'),
                                         zoom=3, background='#ffffff', skip_system_fonts=True)
        top = float(svg.get('viewBox').split()[1])
        return FormulaImage(data, width * 72 / 96, height * 72 / 96,
                            max(0.0, top + height) * 72 / 96)
    except FormulaError:
        raise
    except Exception as exc:
        raise FormulaError(f'公式图片渲染失败：{exc}') from exc
