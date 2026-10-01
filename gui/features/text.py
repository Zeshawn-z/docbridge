"""Text workflows register their own pages without file queue adapters."""
class PasteToWord:
    key = 'paste2word'
    title = '粘贴转 Word'
    icon_name = 'paste'

    @staticmethod
    def create_page(parent):
        from ..text_pages import PasteToWordPage
        return PasteToWordPage(PasteToWord(), parent)


class WordToText:
    key = 'word2text'
    title = 'Word 转文本'
    icon_name = 'copy'

    @staticmethod
    def create_page(parent):
        from ..text_pages import WordToTextPage
        return WordToTextPage(WordToText(), parent)
