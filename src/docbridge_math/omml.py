"""Read common Office Math structures without flattening fractions/scripts."""
from __future__ import annotations
import re
from .codec import FormulaError

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
NS = {'m': M}
SYMBOLS = {
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
    'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
    'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
    'ν': r'\nu', 'ξ': r'\xi', 'π': r'\pi', 'ρ': r'\rho',
    'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\phi',
    'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
    'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda',
    'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 'Υ': r'\Upsilon',
    'Φ': r'\Phi', 'Ψ': r'\Psi', 'Ω': r'\Omega',
    '∑': r'\sum', '∏': r'\prod', '∫': r'\int', '∬': r'\iint',
    '∭': r'\iiint', '∮': r'\oint', '⋃': r'\bigcup', '⋂': r'\bigcap',
    '∞': r'\infty', '∂': r'\partial', '∇': r'\nabla',
    '±': r'\pm', '∓': r'\mp', '×': r'\times', '÷': r'\div',
    '·': r'\cdot', '⋅': r'\cdot', '≤': r'\leq', '≥': r'\geq',
    '≠': r'\neq', '≈': r'\approx', '≡': r'\equiv', '∈': r'\in',
    '∉': r'\notin', '⊂': r'\subset', '⊆': r'\subseteq',
    '→': r'\to', '⇒': r'\Rightarrow', '↔': r'\leftrightarrow',
    '…': r'\ldots', '⋯': r'\cdots', '⋮': r'\vdots', '⋱': r'\ddots',
    '−': '-', 'ℝ': r'\mathbb{R}', 'ℂ': r'\mathbb{C}',
    'ℕ': r'\mathbb{N}', 'ℤ': r'\mathbb{Z}',
}
ACCENTS = {'̂': 'hat', '̅': 'bar', '̃': 'tilde', '⃗': 'vec',
           '̇': 'dot', '̈': 'ddot', '^': 'hat', '~': 'tilde', '→': 'vec',
           '̌': 'check', '̆': 'breve', '́': 'acute', '̀': 'grave'}
FUNCTIONS = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos',
             'arctan', 'sinh', 'cosh', 'tanh', 'log', 'ln', 'exp', 'lim',
             'max', 'min', 'sup', 'inf', 'det', 'gcd'}


def _text(text):
    special = {'{': r'\{', '}': r'\}', '_': r'\_', '^': r'\hat{}',
               '$': r'\$', '&': r'\&', '#': r'\#', '%': r'\%', '\\': r'\backslash '}
    return ''.join((SYMBOLS[c] + ' ') if c in SYMBOLS else special.get(c, c) for c in text)


def _value(node, path, default=''):
    child = node.find(path, NS)
    return child.get(f'{{{M}}}val', default) if child is not None else default


def _delimiter(char):
    return {'': '.', '{': r'\{', '}': r'\}', '⟨': r'\langle ',
            '⟩': r'\rangle ', '‖': r'\Vert '}.get(char, char)


def omml_to_latex(node) -> str:
    def visit(el):
        if el is None:
            return ''
        name = el.tag.rsplit('}', 1)[-1]
        if name.endswith('Pr'):
            return ''
        if name in ('oMath', 'oMathPara', 'e', 'num', 'den', 'sub', 'sup',
                    'deg', 'lim', 'fName', 'box'):
            return ''.join(visit(c) for c in el)
        if name == 'r':
            text = ''.join(t.text or '' for t in el.findall('m:t', NS))
            if el.find('m:rPr/m:nor', NS) is not None and _value(el, 'm:rPr/m:nor', '1') not in ('0', 'false', 'off'):
                return r'\text{' + re.sub(r'([{}%#$&_])', r'\\\1', text) + '}'
            if text in FUNCTIONS:
                return '\\' + text + ' '
            result = _text(text)
            style = _value(el, 'm:rPr/m:sty')
            script = _value(el, 'm:rPr/m:scr')
            commands = {'script': 'mathcal', 'fraktur': 'mathfrak',
                        'double-struck': 'mathbb', 'sans-serif': 'mathsf',
                        'monospace': 'mathtt'}
            if script in commands:
                result = '\\' + commands[script] + '{' + result + '}'
            if style in ('b', 'bi'):
                return r'\mathbf{' + result + '}'
            if style == 'p' and not script and re.fullmatch('[A-Za-z]{2,}', text):
                return r'\mathrm{' + result + '}'
            return result
        if name == 't':
            return _text(el.text or '')
        arg = lambda key: visit(el.find('m:' + key, NS))
        if name == 'f':
            kind = _value(el, 'm:fPr/m:type')
            if kind == 'noBar':
                return r'{'+arg('num')+r'\atop '+arg('den')+'}'
            if kind in ('', 'bar', 'skw', 'lin'):
                return r'\frac{' + arg('num') + '}{' + arg('den') + '}'
            raise FormulaError(f'暂不支持分式布局 {kind}。')
        if name in ('sSub', 'sSup', 'sSubSup', 'sPre'):
            sub = '_{' + arg('sub') + '}' if name in ('sSub', 'sSubSup', 'sPre') else ''
            sup = '^{' + arg('sup') + '}' if name in ('sSup', 'sSubSup', 'sPre') else ''
            return ('{}' + sub + sup + '{' + arg('e') + '}') if name == 'sPre' else '{' + arg('e') + '}' + sub + sup
        if name == 'rad':
            degree = arg('deg')
            return r'\sqrt' + ('[' + degree + ']' if degree else '') + '{' + arg('e') + '}'
        if name == 'nary':
            symbol = _value(el, 'm:naryPr/m:chr', '∫')
            out = _text(symbol)
            for key in ('sub', 'sup'):
                value = arg(key)
                hidden = _value(el, 'm:naryPr/m:' + key + 'Hide', '0')
                if value and hidden not in ('1', 'true', 'on'):
                    out += ('_' if key == 'sub' else '^') + '{' + value + '}'
            return out + '{' + arg('e') + '}'
        if name == 'd':
            left = _delimiter(_value(el, 'm:dPr/m:begChr', '('))
            right = _delimiter(_value(el, 'm:dPr/m:endChr', ')'))
            separator = _text(_value(el, 'm:dPr/m:sepChr', '|'))
            return r'\left' + left + separator.join(visit(c) for c in el.findall('m:e', NS)) + r'\right' + right
        if name == 'm':
            rows = [' & '.join(visit(c) for c in row.findall('m:e', NS)) for row in el.findall('m:mr', NS)]
            return r'\begin{matrix}' + r' \\ '.join(rows) + r'\end{matrix}'
        if name == 'eqArr':
            return r'\begin{aligned}' + r' \\ '.join(visit(c) for c in el.findall('m:e', NS)) + r'\end{aligned}'
        if name in ('limLow', 'limUpp'):
            return ('\\underset' if name == 'limLow' else '\\overset') + '{' + arg('lim') + '}{' + arg('e') + '}'
        if name == 'func':
            return arg('fName') + '{' + arg('e') + '}'
        if name == 'acc':
            accent = _value(el, 'm:accPr/m:chr', '̂')
            if accent not in ACCENTS:
                raise FormulaError(f'暂不支持重音符号 {accent}。')
            return '\\' + ACCENTS[accent] + '{' + arg('e') + '}'
        if name == 'bar':
            return ('\\underline' if _value(el, 'm:barPr/m:pos') == 'bot' else '\\overline') + '{' + arg('e') + '}'
        if name == 'groupChr':
            symbol = _value(el, 'm:groupChrPr/m:chr', '⏟')
            commands = {'⏟': 'underbrace', '⏞': 'overbrace', '→': 'overrightarrow', '←': 'overleftarrow'}
            if symbol not in commands:
                raise FormulaError(f'暂不支持组合符号 {symbol}。')
            return '\\' + commands[symbol] + '{' + arg('e') + '}'
        if name in ('aln', 'brk'):
            return ''
        raise FormulaError(f'暂不支持 Word 公式结构 {name}。')
    result = visit(node).strip()
    if not result:
        raise FormulaError('Word 公式没有内容。')
    return result
