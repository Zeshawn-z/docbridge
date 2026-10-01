"""Read Word OOXML, using the independent formula backend for Office Math."""
from __future__ import annotations

from .legacy import convert_legacy_doc

import hashlib
import json
from copy import deepcopy
import html
import os
import posixpath
import re
import shutil
import uuid
from contextlib import contextmanager
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree as ET
from docbridge_math import FormulaError, omml_to_latex, render_png

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'v': 'urn:schemas-microsoft-com:vml'}


def tag(name):
    prefix, local = name.split(':')
    return f'{{{NS[prefix]}}}{local}'


def value(element, name='w:val', default=None):
    return element.get(tag(name), default) if element is not None else default


def escape(text):
    return re.sub(r'([\\`*_{}\[\]<>#|])', r'\\\1', text)


@dataclass
class ConversionResult:
    source: Path
    markdown: Path
    image_count: int
    warnings: list[str] = field(default_factory=list)


class DocxReader:
    def __init__(self, source, destination, output_stem=None, math_mode='latex'):
        self.archive = zipfile.ZipFile(source)
        self.destination = destination
        self.output_stem = output_stem or Path(source).stem
        self.image_folder = self.output_stem + '_images'
        self.heading_anchors = {}
        self.toc_paragraphs = set()
        self.warnings = []
        self.images = {}
        self.counters = {}
        self.math_mode = math_mode
        try:
            if sum(i.file_size for i in self.archive.infolist()) > 512 * 1024 * 1024:
                raise ValueError('文档解压后超过 512 MB，无法转换。')
            self.document = self.xml('word/document.xml')
            styles = self.xml('word/styles.xml', True)
            self.styles = {value(s, 'w:styleId'): s for s in styles}
            self.defaults = styles.find('w:docDefaults/w:rPrDefault/w:rPr', NS)
            self.default_style = next((sid for sid, s in self.styles.items()
                                       if value(s, 'w:type') == 'paragraph' and value(s, 'w:default') == '1'), None)
            self.relationships = {r.get('Id'): (r.get('Target', ''), r.get('TargetMode'))
                                  for r in self.xml('word/_rels/document.xml.rels', True)}
            numbering = self.xml('word/numbering.xml', True)
            self.abstract = {value(n, 'w:abstractNumId'): n for n in numbering.findall('w:abstractNum', NS)}
            self.numbering = {value(n, 'w:numId'): n for n in numbering.findall('w:num', NS)}
        except Exception:
            self.archive.close()
            raise

    def xml(self, path, optional=False):
        try:
            return ET.fromstring(self.archive.read(path))
        except KeyError:
            if optional:
                return ET.Element('empty')
            raise ValueError(f'Word 文件缺少必要内容：{path}') from None

    def warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def style_chain(self, sid):
        result, seen = [], set()
        while sid in self.styles and sid not in seen:
            seen.add(sid)
            style = self.styles[sid]
            result.insert(0, style)
            sid = value(style.find('w:basedOn', NS))
        return result

    def paragraph_properties(self, paragraph):
        props = paragraph.find('w:pPr', NS)
        sid = value(props.find('w:pStyle', NS)) if props is not None else None
        chain = self.style_chain(sid or self.default_style)
        return chain, [p for p in [*(s.find('w:pPr', NS) for s in chain), props] if p is not None]

    def run_properties(self, run, chain):
        props = run.find('w:rPr', NS)
        result = {}
        layers = [self.defaults, *(s.find('w:rPr', NS) for s in chain)]
        if props is not None:
            layers.extend(s.find('w:rPr', NS) for s in self.style_chain(value(props.find('w:rStyle', NS))))
        layers.append(props)
        for layer in layers:
            if layer is not None:
                for key in ('b', 'i', 'strike', 'vanish'):
                    item = layer.find(f'w:{key}', NS)
                    if item is not None:
                        result[key] = value(item, default='1') not in ('0', 'false', 'off')
        return result

    def image(self, rid, alt='图片', as_html=False):
        target, mode = self.relationships.get(rid, ('', None))
        if not target or mode == 'External':
            self.warn('有外链或缺失图片未导出。')
            return '[图片未导出]'
        path = posixpath.normpath(posixpath.join('word', target)) if not target.startswith('/') else target.lstrip('/')
        if not path.startswith('word/media/'):
            self.warn('图片关系指向非媒体文件，已跳过。')
            return '[图片未导出]'
        try:
            data = self.archive.read(path)
        except KeyError:
            self.warn('文档内有缺失的图片文件。')
            return '[图片缺失]'
        digest = hashlib.sha256(data).hexdigest()
        if digest not in self.images:
            ext = Path(path).suffix.lower()
            if not re.fullmatch(r'\.[a-z0-9]{1,8}', ext):
                ext = '.bin'
            filename = f'{self.output_stem}_{len(self.images) + 1:03d}_{digest[:8]}{ext}'
            folder = self.destination / self.image_folder
            folder.mkdir(exist_ok=True)
            (folder / filename).write_bytes(data)
            self.images[digest] = f'{self.image_folder}/{filename}'
            if ext in ('.emf', '.wmf', '.tif', '.tiff', '.bin'):
                self.warn(f'{ext} 图片已导出，但部分 Markdown 阅读器不能直接显示。')
        url = quote(self.images[digest], safe='/')
        return f'<img src="{url}" alt="{html.escape(alt, quote=True)}">' if as_html else f'![{escape(alt)}]({url})'

    def run(self, run, chain, as_html=False):
        properties = self.run_properties(run, chain)
        if properties.get('vanish'):
            return ''
        pieces = []
        for child in run:
            if child.tag == tag('w:t'):
                pieces.append(html.escape(child.text or '') if as_html else escape(child.text or ''))
            elif child.tag == tag('w:tab'):
                pieces.append('    ')
            elif child.tag in (tag('w:br'), tag('w:cr')):
                pieces.append('<br>' if as_html else '  \n')
            elif child.tag in (tag('w:drawing'), tag('w:pict')):
                desc = next((e.get('descr') or e.get('title') for e in child.iter()
                             if e.tag.endswith('}docPr') and (e.get('descr') or e.get('title'))), '图片')
                if self.math_mode == 'latex' and desc.startswith('DocBridgeFormula:'):
                    try:
                        formula = json.loads(desc[len('DocBridgeFormula:'):])
                        if isinstance(formula.get('latex'), str) and formula['latex'].strip():
                            pieces.append(self.formula_text(formula['latex'], bool(formula.get('display')), as_html))
                            continue
                    except (ValueError, TypeError, AttributeError):
                        pass
                if desc.startswith('DocBridgeFormula:'):
                    desc = '公式'
                for blip in child.findall('.//a:blip', NS):
                    pieces.append(self.image(value(blip, 'r:embed') or value(blip, 'r:link'), desc, as_html))
                for im in child.findall('.//v:imagedata', NS):
                    pieces.append(self.image(value(im, 'r:id'), desc, as_html))
            elif child.tag == tag('w:footnoteReference'):
                self.warn('脚注引用已保留为标记，脚注正文未转换。')
                pieces.append(f"[脚注 {value(child, 'w:id', '?')}]")
        text = ''.join(pieces)
        if not text.strip():
            return text
        lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
        core = text.strip()
        for prop, md, ht in (('strike', '~~', 'del'), ('i', '*', 'em'), ('b', '**', 'strong')):
            if properties.get(prop):
                core = f'<{ht}>{core}</{ht}>' if as_html else f'{md}{core}{md}'
        return lead + core + trail

    def inline(self, parent, chain, as_html=False):
        parts = []
        children, index = list(parent), 0
        while index < len(children):
            child = children[index]
            index += 1
            if child.tag == tag('w:r'):
                # Word often splits a single word into several runs (spellchecking,
                # editing history). Format the whole span to avoid **a****b**.
                if all(c.tag in (tag('w:rPr'), tag('w:t')) for c in child):
                    child = deepcopy(child)
                    properties = self.run_properties(child, chain)
                    while index < len(children):
                        following = children[index]
                        if (following.tag != tag('w:r') or
                            not all(c.tag in (tag('w:rPr'), tag('w:t')) for c in following) or
                            self.run_properties(following, chain) != properties):
                            break
                        for item in following.findall('w:t', NS):
                            child.append(deepcopy(item))
                        index += 1
                parts.append(self.run(child, chain, as_html))
            elif child.tag == tag('w:hyperlink'):
                text = self.inline(child, chain, as_html)
                target, _ = self.relationships.get(value(child, 'r:id'), ('', None))
                anchor = value(child, 'w:anchor')
                target = target or (f'#{anchor}' if anchor else '')
                if target and urlsplit(target).scheme.lower() in ('', 'https', 'http', 'mailto', 'ftp'):
                    url = quote(target, safe='/:#?&=%@+~!$,;-')
                    parts.append(f'<a href="{html.escape(url, quote=True)}">{text}</a>' if as_html else f'[{text}]({url})')
                else:
                    parts.append(text)
            elif child.tag in (tag('w:ins'), tag('w:smartTag'), tag('w:sdt'), tag('w:sdtContent'), tag('w:fldSimple')):
                parts.append(self.inline(child, chain, as_html))
            elif child.tag.endswith('}oMath') or child.tag.endswith('}oMathPara'):
                parts.append(self.formula(child, as_html))
        return ''.join(parts)

    @staticmethod
    def formula_text(latex, display, as_html=False):
        text = ('$$\n' + latex + '\n$$') if display else ('$' + latex + '$')
        return html.escape(text) if as_html else text

    def formula(self, element, as_html=False):
        display = element.tag.endswith('}oMathPara')
        try:
            latex = omml_to_latex(element)
        except FormulaError as exc:
            # Keep the original structure as a sidecar when the backend cannot
            # express it, so unsupported equations are never silently discarded.
            data = ET.tostring(element, encoding='utf-8', xml_declaration=True)
            digest = hashlib.sha256(data).hexdigest()[:12]
            folder = self.destination / self.image_folder
            folder.mkdir(exist_ok=True)
            filename = f'{self.output_stem}_formula_{digest}.omml.xml'
            (folder / filename).write_bytes(data)
            url = quote(f'{self.image_folder}/{filename}', safe='/')
            self.warn(f'公式未能转换，原始 OMML 已保存到 {filename}：{exc}')
            text = escape(''.join(element.itertext())) or '未转换的公式'
            return (f'<a href="{url}">原始公式</a>' if as_html else
                    f'{text}（[原始公式]({url})）')
        if self.math_mode == 'image':
            try:
                image = render_png(latex, display)
                digest = hashlib.sha256(image.data).hexdigest()
                if digest not in self.images:
                    folder = self.destination / self.image_folder
                    folder.mkdir(exist_ok=True)
                    filename = f'{self.output_stem}_formula_{len(self.images)+1:03d}_{digest[:8]}.png'
                    (folder / filename).write_bytes(image.data)
                    self.images[digest] = f'{self.image_folder}/{filename}'
                url = quote(self.images[digest], safe='/')
                return f'<img src="{url}" alt="公式">' if as_html else f'![公式]({url})'
            except FormulaError as exc:
                self.warn(f'公式图片生成失败，已保留 LaTeX：{exc}')
        return self.formula_text(latex, display, as_html)

    def list_prefix(self, props):
        numprops = {}
        for prop in props:
            np = prop.find('w:numPr', NS)
            if np is not None:
                for key in ('ilvl', 'numId'):
                    if np.find(f'w:{key}', NS) is not None:
                        numprops[key] = value(np.find(f'w:{key}', NS))
        nid = numprops.get('numId')
        if not nid or nid == '0':
            return ''
        level = min(max(int(numprops.get('ilvl', 0)), 0), 8)
        num = self.numbering.get(nid)
        abstract = self.abstract.get(value(num.find('w:abstractNumId', NS))) if num is not None else None
        lvl = abstract.find(f"w:lvl[@w:ilvl='{level}']", NS) if abstract is not None else None
        override = num.find(f"w:lvlOverride[@w:ilvl='{level}']", NS) if num is not None else None
        if override is not None and override.find('w:lvl', NS) is not None:
            lvl = override.find('w:lvl', NS)
        fmt = value(lvl.find('w:numFmt', NS), default='bullet') if lvl is not None else 'bullet'
        if fmt in ('bullet', 'none'):
            return '    ' * level + '- '
        start = int(value(lvl.find('w:start', NS), default='1')) if lvl is not None else 1
        if override is not None:
            start = int(value(override.find('w:startOverride', NS), default=str(start)))
        counts = self.counters.setdefault(nid, {})
        counts[level] = counts.get(level, start - 1) + 1
        for deeper in list(counts):
            if deeper > level:
                del counts[deeper]
        return '    ' * level + f'{counts[level]}. '

    def paragraph(self, paragraph, as_html=False):
        chain, props = self.paragraph_properties(paragraph)
        text = self.inline(paragraph, chain, as_html).strip()
        if not text:
            return ''
        outline = self.heading_level(paragraph)
        anchors = []
        for bookmark in paragraph.findall('.//w:bookmarkStart', NS):
            name = value(bookmark, 'w:name')
            if name and name != '_GoBack':
                anchors.append(f'<a id="{html.escape(name, quote=True)}"></a>')
        if paragraph in self.heading_anchors:
            anchors.append(f'<a id="{self.heading_anchors[paragraph]}"></a>')
        anchor_text = '\n'.join(anchors) + ('\n\n' if anchors else '')
        if outline is not None and outline < 9:
            level = max(1, min(outline + 1, 6))
            if outline >= 6:
                self.warn('Word 的 7–9 级标题已映射为 Markdown 的 6 级标题。')
            return anchor_text + (f'<h{level}>{text}</h{level}>' if as_html else '#' * level + ' ' + text)
        prefix = self.list_prefix(props)
        if as_html:
            return anchor_text + f'<p>{html.escape(prefix)}{text}</p>'
        if prefix:
            text = text.replace('\n', '\n' + ' ' * len(prefix))
        else:
            text = re.sub(r'^(\d+)([.)])(?=\s)', r'\1\\\2', text)
            text = re.sub(r'^([-+])(?=\s)', r'\\\1', text)
        return anchor_text + prefix + text

    def heading_level(self, paragraph):
        chain, props = self.paragraph_properties(paragraph)
        outline = None
        for prop in props:
            level = prop.find('w:outlineLvl', NS)
            if level is not None:
                outline = int(value(level, default='9'))
        if outline is None:
            for style in chain:
                name = value(style.find('w:name', NS), default='')
                match = re.fullmatch(r'(?:heading\s*|标题\s*)([1-9])', name, re.I)
                if match:
                    outline = int(match[1]) - 1
        return outline

    def prepare_toc(self, body):
        def rendered_paragraphs(parent):
            for child in parent:
                if child.tag == tag('w:p'):
                    yield child
                elif child.tag in {tag(t) for t in ('w:tbl', 'w:tr', 'w:tc', 'w:sdt', 'w:sdtContent', 'w:ins')}:
                    yield from rendered_paragraphs(child)
        paragraphs = list(rendered_paragraphs(body))
        stack = []
        self.toc_starts = {}
        for p in paragraphs:
            chain, _ = self.paragraph_properties(p)
            style_names = [value(s, 'w:styleId', '') for s in chain]
            style_names += [value(s.find('w:name', NS), default='') for s in chain]
            if any(re.fullmatch(r'(?:TOC|目录)\s*[1-9]', name, re.I) for name in style_names):
                self.toc_paragraphs.add(p)
            for field in stack:
                field['paragraphs'].add(p)
            for node in p.iter():
                if node.tag == tag('w:fldChar'):
                    kind = value(node, 'w:fldCharType')
                    if kind == 'begin':
                        stack.append({'start': p, 'paragraphs': {p}, 'code': '', 'result': False})
                    elif kind == 'separate' and stack:
                        stack[-1]['result'] = True
                    elif kind == 'end' and stack:
                        self.register_toc_field(stack.pop())
                elif node.tag == tag('w:instrText') and stack and not stack[-1]['result']:
                    stack[-1]['code'] += node.text or ''
                elif node.tag == tag('w:fldSimple'):
                    self.register_toc_field({'start': p, 'paragraphs': {p}, 'code': value(node, 'w:instr', '')})
        for field in stack:
            self.register_toc_field(field)
        # A content control may contain an empty TOC whose field has no cached result.
        for sdt in body.iter(tag('w:sdt')):
            gallery = sdt.find('w:sdtPr/w:docPartObj/w:docPartGallery', NS)
            if value(gallery, default='').lower() in ('table of contents', '目录'):
                contents = sdt.find('w:sdtContent', NS)
                entries = list(contents.iter(tag('w:p'))) if contents is not None else []
                if entries and not any(p in self.toc_paragraphs for p in entries):
                    self.toc_paragraphs.add(entries[-1])
        headings = [p for p in paragraphs if p not in self.toc_paragraphs and
                    self.heading_level(p) is not None and self.heading_level(p) < 9 and
                    ''.join(t.text or '' for t in p.iter(tag('w:t'))).strip()]
        if self.toc_paragraphs:
            reserved = {value(b, 'w:name') for b in body.iter(tag('w:bookmarkStart'))}
            for i, p in enumerate(headings, 1):
                anchor = f'word2md-heading-{i}'
                while anchor in reserved:
                    anchor += '-'
                self.heading_anchors[p] = anchor
                reserved.add(anchor)
        self.toc_headings = headings

    def register_toc_field(self, field):
        code = field['code'].strip()
        if re.match(r'^TOC(?:\s|$)', code, re.I):
            self.toc_paragraphs.update(field['paragraphs'])
            self.toc_starts[field['start']] = code
            if re.search(r'\\[tabfc]\b', code, re.I):
                self.warn('自定义目录已按正文标题重建，未保留 Word 的自定义目录筛选规则。')

    def toc(self, code=''):
        limits = re.search(r'\\o\s+"?(\d+)-(\d+)"?', code)
        lower, upper = (int(limits[1]), int(limits[2])) if limits else (1, 6)
        items = [(p, self.heading_level(p) + 1) for p in self.toc_headings
                 if lower <= self.heading_level(p) + 1 <= upper]
        if not items:
            self.warn('发现 Word 目录，但没有可用于重建目录的正文标题。')
            return '> 目录未生成：未找到标题样式或大纲级别。'
        base = min(level for _, level in items)
        return '\n'.join('    ' * (min(level - base, 5)) +
                         f"- [{escape(''.join(t.text or '' for t in p.iter(tag('w:t'))).strip())}](#{self.heading_anchors[p]})"
                         for p, level in items)

    def table(self, table):
        rows = table.findall('w:tr', NS)
        merged = any(c.find('w:tcPr/w:gridSpan', NS) is not None or
                     c.find('w:tcPr/w:vMerge', NS) is not None for r in rows for c in r.findall('w:tc', NS))
        if merged or table.find('.//w:tc/w:tbl', NS) is not None:
            return self.html_table(table)
        data = []
        for row in rows:
            cells = []
            for cell in row.findall('w:tc', NS):
                texts = [self.paragraph(p) for p in cell.findall('w:p', NS)]
                cells.append('<br>'.join(t.replace('  \n', '<br>') for t in texts if t))
            data.append(cells)
        if not data:
            return ''
        width = max(map(len, data))
        if not width:
            return ''
        lines = ['| ' + ' | '.join(row + [''] * (width - len(row))) + ' |' for row in data]
        lines.insert(1, '| ' + ' | '.join(['---'] * width) + ' |')
        return '\n'.join(lines)

    def html_table(self, table):
        rendered, active = [], {}
        for row in table.findall('w:tr', NS):
            current, col, next_active = [], int(value(row.find('w:trPr/w:gridBefore', NS), default='0')), {}
            for cell in row.findall('w:tc', NS):
                span = int(value(cell.find('w:tcPr/w:gridSpan', NS), default='1'))
                vm = cell.find('w:tcPr/w:vMerge', NS)
                if vm is not None and value(vm, default='continue') == 'continue' and col in active:
                    existing = active[col]
                    existing['rowspan'] += 1
                    next_active[col] = existing
                else:
                    body = []
                    for child in cell:
                        if child.tag == tag('w:p'):
                            body.append(self.paragraph(child, True))
                        elif child.tag == tag('w:tbl'):
                            body.append(self.html_table(child))
                    entry = {'colspan': span, 'rowspan': 1, 'text': ''.join(body)}
                    current.append(entry)
                    if vm is not None:
                        next_active[col] = entry
                col += span
            active = next_active
            rendered.append(current)
        lines = ['<table>']
        for row in rendered:
            lines.append('  <tr>')
            for cell in row:
                attrs = ''.join(f' {key}="{cell[key]}"' for key in ('colspan', 'rowspan') if cell[key] > 1)
                lines.append(f"    <td{attrs}>{cell['text']}</td>")
            lines.append('  </tr>')
        return '\n'.join([*lines, '</table>'])

    def render(self):
        blocks = []
        body = self.document.find('w:body', NS)
        if body is None:
            raise ValueError('Word 文件没有正文。')
        self.prepare_toc(body)
        in_toc = False
        def walk(parent):
            nonlocal in_toc
            for child in parent:
                if child.tag == tag('w:p'):
                    if child in self.toc_paragraphs:
                        if not in_toc or child in self.toc_starts:
                            blocks.append(self.toc(self.toc_starts.get(child, '')))
                        in_toc = True
                        continue
                    in_toc = False
                    blocks.append(self.paragraph(child))
                elif child.tag == tag('w:tbl'):
                    in_toc = False
                    blocks.append(self.table(child))
                elif child.tag in (tag('w:sdt'), tag('w:sdtContent'), tag('w:ins')):
                    walk(child)
        walk(body)
        if self.document.find('.//w:txbxContent', NS) is not None:
            self.warn('文本框内容未转换。')
        return '\n\n'.join(b for b in blocks if b) + '\n'


@contextmanager
def staging_directory(output):
    # TemporaryDirectory uses mode 0700. On Windows, renaming a child out of
    # that directory retains its restricted ACL. Inherit the output ACL instead.
    stage = output / ('.word2md-' + uuid.uuid4().hex)
    stage.mkdir(mode=0o777)
    try:
        yield stage
    finally:
        resolved = stage.resolve()
        if resolved.parent != output.resolve() or not resolved.name.startswith('.word2md-'):
            raise ValueError('临时目录路径异常，已停止清理。')
        shutil.rmtree(resolved)


def convert_file(source: str | Path, output_dir: str | Path | None = None, *, overwrite=False, math_mode='latex') -> ConversionResult:
    if math_mode not in ('latex', 'image'):
        raise ValueError('公式输出方式必须是 latex 或 image。')
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f'文件不存在：{source}')
    if source.suffix.lower() not in ('.docx', '.doc'):
        raise ValueError('仅支持 .docx 和 .doc 文件。')
    output = Path(output_dir).expanduser().resolve() if output_dir else source.parent
    output.mkdir(parents=True, exist_ok=True)
    stem, number = source.stem, 2
    output_stem = stem
    while not overwrite and ((output / f'{output_stem}.md').exists() or
                             (output / f'{output_stem}_images').exists()):
        output_stem = f'{stem}_{number}'
        number += 1
    markdown_path = output / f'{output_stem}.md'
    image_path = output / f'{output_stem}_images'
    if markdown_path.is_symlink() or (markdown_path.exists() and not markdown_path.is_file()):
        raise ValueError(f'输出 Markdown 路径冲突：{markdown_path}')
    if image_path.is_symlink() or (image_path.exists() and not image_path.is_dir()):
        raise ValueError(f'输出图片目录冲突：{image_path}')
    with staging_directory(output) as stage:
        actual = convert_legacy_doc(source, stage) if source.suffix.lower() == '.doc' else source
        export = stage / 'export'
        export.mkdir()
        reader = DocxReader(actual, export, output_stem, math_mode)
        try:
            markdown = reader.render()
            (export / markdown_path.name).write_text(markdown, encoding='utf-8')
            image_count, warnings = len(reader.images), reader.warnings.copy()
        finally:
            reader.archive.close()
        assets = list((export / image_path.name).iterdir()) if (export / image_path.name).exists() else []
        plan = [(asset, image_path / asset.name) for asset in assets]
        plan.append((export / markdown_path.name, markdown_path))
        for _, target in plan:
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError(f'输出路径冲突：{target}')
        backups, published = [], []
        new_image_dir = bool(assets) and not image_path.exists()
        try:
            if assets:
                image_path.mkdir(exist_ok=True)
            for index, (item, target) in enumerate(plan):
                if target.exists():
                    backup = stage / f'backup-{index}'
                    os.replace(target, backup)
                    backups.append((backup, target))
                os.replace(item, target)
                published.append(target)
        except Exception:
            for target in reversed(published):
                target.unlink()
            for backup, target in reversed(backups):
                os.replace(backup, target)
            if new_image_dir and image_path.exists() and not any(image_path.iterdir()):
                image_path.rmdir()
            raise
    return ConversionResult(source, markdown_path, image_count, warnings)
