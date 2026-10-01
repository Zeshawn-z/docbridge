"""Formula delimiters shared by conversion and any Markdown preview."""
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.dollarmath.index import math_inline_dollar
from mdit_py_plugins.texmath import texmath_plugin


def install_math_rules(md):
    md.use(dollarmath_plugin, allow_labels=False, allow_space=False,
           allow_digits=False, double_inline=True)
    md.use(texmath_plugin, delimiters='brackets')
    dollar = math_inline_dollar(allow_space=False, allow_digits=False, allow_double=True)

    def safe_dollar(state, silent):
        if state.src[state.pos] != '$':
            return False
        # An unmatched currency dollar must not consume a closing dollar
        # inside a later code span (e.g. '$30; `$x$`').
        end = state.src.find('$', state.pos + (2 if state.src.startswith('$$', state.pos) else 1))
        if end >= 0 and '`' in state.src[state.pos:end]:
            return False
        return dollar(state, silent)

    md.inline.ruler.at('math_inline', safe_dollar)
