"""Markdown report feature; no knowledge of other pages or their state."""
from ..conversion_service import convert_markdown


class MarkdownToWord:
    key = 'md2word'
    title = 'Markdown 转 Word'
    icon_name = 'file'
    extensions = ('.md', '.markdown')
    file_filter = 'Markdown 文件 (*.md *.markdown)'
    select_label = '选择 Markdown 文件'
    preview_label = '内容预览'
    open_label = '打开 Word'
    output_hint = '文档名.docx'
    settings_label = '排版'

    def create_options(self, parent):
        from ..report_options import ReportOptions
        return ReportOptions(parent)

    def read_options(self, widget):
        return {'template': widget.template_path(), 'overrides': widget.overrides()}

    @staticmethod
    def create_output_options(parent):
        from ..formula_options import FormulaOptions
        return FormulaOptions('word', parent)

    def convert(self, source, output, overwrite, settings, log):
        return convert_markdown(source, output, overwrite=overwrite, log=log, **settings)

    @staticmethod
    def preview_path(result):
        return result.source

    @staticmethod
    def result_path(result):
        return result.output
