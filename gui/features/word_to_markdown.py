"""Word export feature; independent of Markdown report styling."""
from docx2md.converter import convert_file


class WordToMarkdown:
    key = 'word2md'
    title = 'Word 转 Markdown'
    icon_name = 'convert'
    extensions = ('.docx', '.doc')
    file_filter = 'Word 文档 (*.docx *.doc)'
    select_label = '选择 Word 文件'
    preview_label = '结果预览'
    open_label = '打开 Markdown'
    output_hint = '文档名.md\n文档名_images/'
    settings_label = '.doc 支持'
    default_settings_tab = 1

    @staticmethod
    def create_options(parent):
        from ..doc_options import DocSupportOptions
        return DocSupportOptions(parent)

    @staticmethod
    def read_options(widget):
        return {}

    @staticmethod
    def convert(source, output, overwrite, settings, log):
        return convert_file(source, output, overwrite=overwrite)

    @staticmethod
    def preview_path(result):
        return result.markdown

    @staticmethod
    def result_path(result):
        return result.markdown
