"""Editable Office Math conversion and the public formula rendering API."""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET
from .shared import FormulaError, FormulaImage, MAX_SOURCE


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


def render_png(source: str, display=False, size_pt=12) -> FormulaImage:
    """Render with bundled KaTeX in the system's headless Edge/Chrome."""
    from .katex import render_png as render_katex
    return render_katex(source, display, size_pt)
