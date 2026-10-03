"""Inline formatting shared by Word conversion and the desktop preview."""
import re
from markdown_it.rules_inline import emphasis

_FORMAT = {'strong': ('strong', 'strong'), 'b': ('strong', 'strong'),
           'em': ('em', 'em'), 'i': ('em', 'em'),
           'del': ('s', 's'), 's': ('s', 's')}
_TAG = re.compile(r'<(/?)(strong|b|em|i|del|s)>', re.I)


def _cjk(char):
    return bool(char) and ('\u3400' <= char <= '\u9fff' or '\uf900' <= char <= '\ufaff')


def install_text_rules(md):
    def cjk_emphasis(state, silent):
        start, offset = state.pos, len(state.delimiters)
        if not emphasis.tokenize(state, silent):
            return False
        # AI output often closes bold after Chinese punctuation without spaces.
        # Keep the normal delimiter pairing and code/escape handling intact.
        end = state.pos
        if state.src[start] == '*' and end - start >= 2:
            before = state.src[start - 1] if start else ''
            after = state.src[end] if end < state.posMax else ''
            for delimiter in state.delimiters[offset:]:
                if _cjk(before) and after and not after.isspace():
                    delimiter.open = True
                if _cjk(after) and before and not before.isspace():
                    delimiter.close = True
        return True

    def formatting_tag(state, silent):
        match = _TAG.match(state.src, state.pos)
        if not match:
            return False
        if not silent:
            closing, name = match.groups()
            kind, tag = _FORMAT[name.lower()]
            state.push(kind + ('_close' if closing else '_open'), tag, -1 if closing else 1)
        state.pos = match.end()
        return True

    md.inline.ruler.at('emphasis', cjk_emphasis)
    md.inline.ruler.before('html_inline', 'formatting_tag', formatting_tag)
