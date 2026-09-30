"""配置加载与合并。

设计：一份 `config/default.yaml` 是唯一的默认来源，用户模板只写"想改的项"，
按层级深度合并覆盖默认值。这样模板可以很短，升级默认配置也不会冲突。
"""

from __future__ import annotations

import copy
import os

import yaml

from . import resources
from .units import ConfigValueError

#: 默认规范的路径。冻结成 exe 后指向解包目录里的内置模板，
#: 除非用户把 default.yaml 放在 exe 同级的 config/ 下。
DEFAULT_CONFIG_PATH = resources.default_config_path()

# 元素 → 配置键名，渲染器按此顺序查表
ELEMENT_KEYS = (
    "body", "heading1", "heading2", "heading3", "heading4", "heading5", "heading6",
    "list", "list_ordered", "quote", "code", "table_text", "table_header",
    "caption", "hr", "image", "footnote",
)

#: 所有元素通用、且在模板里最常被逐项覆盖的排版参数。
#: 校验用——写错键名时报错，比默默忽略强。
STYLE_KEYS = (
    "size", "font_zh", "font_en", "bold", "italic", "color",
    "align", "line_spacing", "space_before", "space_after",
    "first_line_indent", "left_indent", "hanging_indent",
    "keep_with_next", "keep_lines", "page_break_before",
    "contextual_spacing", "outline_level", "shading", "borders",
)

#: 仅列表元素认识的结构化参数
LIST_KEYS = ("level_step_chars", "hanging_indent_chars")

#: 标题编号的合法取值
NUMBERING_BOOL_KEYS = ("enabled", "restart", "strip_text_prefix", "skip_first_level")


def deep_merge(base: dict, override: dict) -> dict:
    """把 override 深度合并进 base 的副本并返回。"""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: str | None = None, overrides: dict | None = None) -> dict:
    """加载默认配置，叠加用户模板与命令行覆盖项。"""
    with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    if path:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise ConfigValueError(f"模板文件不存在：{path}")
        with open(path, "r", encoding="utf-8") as fh:
            user = yaml.safe_load(fh) or {}
        if not isinstance(user, dict):
            raise ConfigValueError(f"模板根节点必须是映射：{path}")
        config = deep_merge(config, user)

    if overrides:
        config = deep_merge(config, _expand_dotted(overrides))

    config.setdefault("defaults", {})
    config.setdefault("elements", {})
    config.setdefault("_meta", {})["template"] = os.path.basename(path) if path else "default.yaml"
    _normalize(config)
    _validate(config)
    return config


def _expand_dotted(pairs: dict) -> dict:
    """把 {'elements.body.size': '五号'} 展开成嵌套字典。"""
    out: dict = {}
    for raw_key, value in pairs.items():
        node = out
        parts = raw_key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


def element_style(config: dict, key: str) -> dict:
    """取某个元素的"全局默认 + 该元素覆盖"合并后的排版参数。"""
    style = dict(config.get("defaults") or {})
    style.update(config.get("elements", {}).get(key, {}) or {})
    return style


def heading_numbering(config: dict) -> dict | None:
    """取标题自动编号配置，未开启时返回 None。

    返回的字典已经归一化：`levels` 是整数、`format` 的键是层级字符串。
    渲染器只需要读它，不用关心模板里写的是 `on` 还是 `true`。
    """
    from . import numbering as _numbering

    cfg = config.get("numbering") or {}
    raw = cfg.get("headings", False)
    if isinstance(raw, str):
        # `headings: 一、` 这种写法也认，直接当预设名用
        text = raw.strip()
        if text.lower() in ("", "off", "false", "no", "none", "关闭"):
            return None
        if text.lower() in ("on", "true", "yes", "自动"):
            cfg = dict(cfg)
            cfg.setdefault("preset", "decimal")
        else:
            cfg = dict(cfg)
            cfg["preset"] = text
    elif not raw:
        return None

    preset = str(cfg.get("preset") or "decimal")
    if preset not in _numbering.HEADING_PRESETS:
        raise ConfigValueError(
            f"编号预设 {preset!r} 不存在，可用：" +
            "、".join(_numbering.preset_names()))

    out = dict(cfg)
    out["preset"] = preset
    try:
        out["levels"] = max(1, min(6, int(cfg.get("levels", 6) or 6)))
    except (TypeError, ValueError):
        out["levels"] = 6
    out.setdefault("restart", True)
    out.setdefault("strip_text_prefix", True)
    out.setdefault("indent", "0字符")
    out.setdefault("hanging", "0字符")
    out["skip_first_level"] = bool(cfg.get("skip_first_level", False))
    fmt = cfg.get("format") or {}
    out["format"] = {str(k): v for k, v in fmt.items()}
    return out


def _normalize(config: dict) -> None:
    """补全元素继承链，让 renderer 拿到的一定是完整参数。"""
    defaults = config["defaults"]
    if "line_spacing" not in defaults:
        defaults["line_spacing"] = 1.25
    for key, style in list(config["elements"].items()):
        if style is None:
            config["elements"][key] = {}
            style = config["elements"][key]
        # 标题系默认不继承正文字号/缩进，只继承行距等公共项
        if key.startswith("heading") and "first_line_indent" not in style:
            style["first_line_indent"] = "0字符"
        # 标题一旦参与自动编号，编号本身占位，不能再叠加首行缩进
        if key.startswith("heading") and config.get("numbering", {}).get("headings"):
            style.setdefault("first_line_indent", "0字符")


def _validate_elements(config: dict) -> None:
    """把拼错的配置键当场报出来。

    以前写错一个键（比如 `space_befor`）会被静默忽略，产物看着"没生效"，
    得回头猜半天。宁可这里直接失败。
    """
    elements = config.get("elements") or {}
    for key, style in elements.items():
        if not isinstance(style, dict):
            raise ConfigValueError(f"elements.{key} 必须是映射")
        allowed = set(STYLE_KEYS)
        if key in ("list", "list_ordered"):
            allowed |= set(LIST_KEYS)
        if key == "image":
            allowed |= {"max_width_ratio", "max_height"}
        if key == "footnote":
            allowed |= {"reference_size"}
        unknown = [k for k in style
                   if k not in allowed and not k.startswith("_")]
        if unknown:
            raise ConfigValueError(
                f"elements.{key} 里有不支持的参数：{'、'.join(sorted(unknown))}"
                f"（可用：{'、'.join(sorted(allowed))}）")


def _validate_numbering(config: dict) -> None:
    """校验 numbering 段，顺便把 `headings` 的简写形式固化。"""
    numbering = config.setdefault("numbering", {})
    if not isinstance(numbering, dict):
        raise ConfigValueError("numbering 必须是映射")
    raw = numbering.get("headings", False)
    if isinstance(raw, bool):
        pass
    elif isinstance(raw, str):
        text = raw.strip().lower()
        if text not in ("on", "true", "yes", "off", "false", "no", "none", "关闭",
                        "自动") and text:
            # 当预设名处理，交给 heading_numbering 做存在性校验
            pass
    else:
        raise ConfigValueError(
            "numbering.headings 只能是 true/false 或预设名（如 一、/ decimal）")

    fmt = numbering.get("format")
    if fmt is not None:
        if not isinstance(fmt, dict):
            raise ConfigValueError("numbering.format 必须是映射，键是标题层级")
        for key, spec in fmt.items():
            try:
                level = int(key)
            except (TypeError, ValueError):
                raise ConfigValueError(
                    f"numbering.format 的键必须是 1~6 的层级，收到 {key!r}") from None
            if not 1 <= level <= 6:
                raise ConfigValueError(f"numbering.format 的层级 {level} 超出 1~6")
            if not isinstance(spec, dict):
                raise ConfigValueError(f"numbering.format.{key} 必须是映射")
            unknown = [k for k in spec
                       if k not in ("num_fmt", "text", "suff", "start")]
            if unknown:
                raise ConfigValueError(
                    f"numbering.format.{key} 里有不支持的参数："
                    f"{'、'.join(sorted(unknown))}"
                    "（可用：num_fmt、text、suff、start）")

    # 预设名拼错时当场报错，而不是等渲染到一半才炸
    if numbering.get("headings"):
        heading_numbering(config)


def _validate(config: dict) -> None:
    md = config.setdefault("markdown", {})
    md.setdefault("emphasis_as_bold", True)
    md.setdefault("strong_as_bold", True)
    md.setdefault("delete", "strikethrough")
    md.setdefault("link", "text")
    md.setdefault("inline_code", "mono")
    md.setdefault("softbreak", "space")
    md.setdefault("strip_front_matter", True)
    if md["delete"] not in ("strikethrough", "text"):
        raise ConfigValueError("markdown.delete 只能是 strikethrough 或 text")
    if md["link"] not in ("text", "hyperlink", "text_with_url"):
        raise ConfigValueError("markdown.link 只能是 text / hyperlink / text_with_url")
    if md["softbreak"] not in ("auto", "space", "newline", "none"):
        raise ConfigValueError("markdown.softbreak 只能是 auto / space / newline / none")

    mmd = config.setdefault("mermaid", {})
    mmd.setdefault("renderer", "auto")
    mmd.setdefault("scale", 3)
    mmd.setdefault("theme", "default")
    mmd.setdefault("background", "#FFFFFF")
    mmd.setdefault("font_family", '"Microsoft YaHei","微软雅黑",SimHei,sans-serif')
    mmd.setdefault("font_size", 14)
    mmd.setdefault("max_width_ratio", 1.0)
    mmd.setdefault("cache_dir", "md2docx-assets")
    mmd.setdefault("chrome_path", "")
    mmd.setdefault("mmdc_path", "")
    mmd.setdefault("keep_source_on_fail", True)

    out = config.setdefault("output", {})
    out.setdefault("toc", False)
    out.setdefault("overwrite", True)

    page = config.setdefault("page", {})
    page.setdefault("size", "A4")
    page.setdefault("footer_page_number", False)

    _validate_elements(config)
    _validate_numbering(config)
