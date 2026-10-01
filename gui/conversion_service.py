"""Wrap the existing report engine with safe output naming and a common result."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from md2docx.config import load_config
from md2docx.renderer import MarkdownToDocx


@dataclass
class ReportResult:
    source: Path
    output: Path
    image_count: int
    warnings: list[str] = field(default_factory=list)
    counters: dict = field(default_factory=dict)


def convert_markdown(source, output_dir=None, *, overwrite=False, template=None, overrides=None, log=None, math_mode=None):
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in ('.md', '.markdown'):
        raise ValueError(f'不是有效的 Markdown 文件：{source}')
    directory = Path(output_dir).expanduser().resolve() if output_dir else source.parent
    directory.mkdir(parents=True, exist_ok=True)
    output, index = directory / (source.stem + '.docx'), 2
    while output.exists() and not overwrite:
        output = directory / f'{source.stem}_{index}.docx'
        index += 1
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise ValueError(f'输出路径冲突：{output}')
    temporary = directory / f'.report-{uuid4().hex}.docx'
    converter = None
    try:
        overrides = dict(overrides or {})
        if math_mode is not None:
            overrides['math.mode'] = math_mode
        config = load_config(template, overrides)
        converter = MarkdownToDocx(config, str(source), str(temporary), log=log or (lambda *_: None))
        converter.render(source.read_text(encoding='utf-8-sig'))
        converter.save()
        os.replace(temporary, output)
        return ReportResult(source, output, converter.counters['image'],
                            list(converter.warnings), dict(converter.counters))
    finally:
        if converter is not None and converter._mermaid is not None:
            converter._mermaid.close()
        temporary.unlink(missing_ok=True)
