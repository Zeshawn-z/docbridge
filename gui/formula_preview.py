"""Render formulas in Qt previews while keeping Markdown source untouched."""
import hashlib
import html
import re
from markdown_it import MarkdownIt
from docbridge_markdown import install_text_rules
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument
from docbridge_math import FormulaError, render_png
from docbridge_math.markdown import install_math_rules


def show_markdown(browser, text):
    parser = MarkdownIt('commonmark', {'html': False})
    parser.enable(['table', 'strikethrough'])
    install_text_rules(parser)
    install_math_rules(parser)
    clean = re.sub(r'^\s*<a id="[^"]+"></a>\s*$', '', text, flags=re.M)
    tokens = parser.parse(clean)
    types = {'math_inline', 'math_inline_double', 'math_block'}
    cache = {}

    def formula(tokens, index, options, env):
        token = tokens[index]
        display = token.type != 'math_inline'
        key = (token.content, display)
        if key not in cache:
            try:
                rendered = render_png(token.content.strip(), display, 12)
                name = 'docbridge-math:' + hashlib.sha256(repr(key).encode()).hexdigest()
                browser.document().addResource(QTextDocument.ResourceType.ImageResource,
                    QUrl(name), QImage.fromData(rendered.data))
                cache[key] = (f'<img src="{name}" width="{rendered.width_pt * 96 / 72:.1f}" '
                              f'height="{rendered.height_pt * 96 / 72:.1f}" alt="公式">')
            except FormulaError:
                cache[key] = '<code>' + html.escape(('$$' if display else '$') + token.content +
                                                   ('$$' if display else '$')) + '</code>'
        image = cache[key]
        return '<p align="center">' + image + '</p>' if token.type == 'math_block' else image

    for token_type in types:
        parser.renderer.rules[token_type] = formula
    browser.setHtml(parser.renderer.render(tokens, parser.options, {}))
