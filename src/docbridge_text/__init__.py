"""Text-only document IO shared by the GUI and CLI; no Markdown files or assets."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from md2docx.config import load_config
from md2docx.renderer import MarkdownToDocx
from docx2md.converter import DocxReader
from docx2md.legacy import convert_legacy_doc


@dataclass
class TextWriteResult:
    output: Path
    warnings: list[str] = field(default_factory=list)
    counters: dict = field(default_factory=dict)


@dataclass
class TextReadResult:
    source: Path
    markdown: str
    warnings: list[str] = field(default_factory=list)


def unwrap_markdown(text):
    """Accept AI responses wrapped in a single Markdown code fence."""
    from markdown_it import MarkdownIt
    tokens = MarkdownIt('commonmark').parse(text)
    if len(tokens) == 1 and tokens[0].type == 'fence' and tokens[0].info.strip().lower() in ('md', 'markdown'):
        return tokens[0].content
    return text


def write_docx(text, output, *, template=None, overrides=None, overwrite=False):
    text = unwrap_markdown(text.lstrip('\ufeff'))
    if not text.strip():
        raise ValueError('请先粘贴要转换的内容。')
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != '.docx':
        raise ValueError('输出文件必须使用 .docx 扩展名。')
    if output.exists() and not overwrite:
        raise FileExistsError(f'文件已存在：{output}')
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise ValueError(f'输出路径冲突：{output}')
    overrides = dict(overrides or {})
    overrides.setdefault('markdown.emphasis_as_bold', False)
    config = load_config(template, overrides)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f'.docbridge-text-{uuid4().hex}.docx'
    converter = MarkdownToDocx(config, str(output.with_suffix('.md')), str(temporary),
                               log=lambda *_: None, include_images=False)
    try:
        converter.render(text)
        converter.save()
        if output.exists() and not overwrite:
            raise FileExistsError(f'文件已存在：{output}')
        os.replace(temporary, output)
        return TextWriteResult(output, list(converter.warnings), dict(converter.counters))
    finally:
        if converter._mermaid is not None:
            converter._mermaid.close()
        temporary.unlink(missing_ok=True)


def read_docx(source):
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in ('.docx', '.doc'):
        raise ValueError(f'不是有效的 Word 文件：{source}')

    def read(actual):
        reader = DocxReader(actual, None, math_mode='latex')
        try:
            return TextReadResult(source, reader.render(), list(reader.warnings))
        finally:
            reader.archive.close()

    if source.suffix.lower() == '.doc':
        with tempfile.TemporaryDirectory(prefix='docbridge-read-') as folder:
            return read(convert_legacy_doc(source, Path(folder)))
    return read(source)
