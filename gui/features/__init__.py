"""Feature registration; each adapter owns only its own conversion behavior."""
def available_features():
    from .markdown_to_word import MarkdownToWord
    from .word_to_markdown import WordToMarkdown
    from .text import PasteToWord, WordToText
    return (MarkdownToWord(), WordToMarkdown(), PasteToWord(), WordToText())
