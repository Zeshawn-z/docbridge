"""命令行入口。"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

from . import __version__, resources
from .config import load_config
from .renderer import MarkdownToDocx
from .units import ConfigValueError

BANNER = "md2docx · Markdown → 规范排版 docx"


def _collect_inputs(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pattern in patterns:
        if os.path.isdir(pattern):
            files.extend(sorted(glob.glob(os.path.join(pattern, "**", "*.md"),
                                          recursive=True)))
        elif any(ch in pattern for ch in "*?["):
            files.extend(sorted(glob.glob(pattern, recursive=True)))
        else:
            files.append(pattern)
    seen, out = set(), []
    for f in files:
        real = os.path.abspath(f)
        if real not in seen:
            seen.add(real)
            out.append(real)
    return out


def _parse_set(items: list[str] | None) -> dict:
    overrides: dict = {}
    for item in items or []:
        if "=" not in item:
            raise ConfigValueError(f"--set 需要 key=value 形式，收到：{item}")
        key, value = item.split("=", 1)
        overrides[key.strip()] = _coerce(value.strip())
    return overrides


def _coerce(text: str):
    low = text.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", ""):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md2docx",
        description=f"{BANNER}。默认排版：正文小四宋体+Times New Roman、"
                    "一级标题小三/二级四号/三级小四黑体、全篇 1.25 倍行距、"
                    "仅正文首行缩进 2 字符、mermaid 渲染为图片。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python md2docx.py examples/demo.md\n"
               "  python md2docx.py examples/demo.md -o out/demo.docx -c config/thesis.yaml\n"
               "  python md2docx.py docs/ -o out/ --set mermaid.scale=4\n"
               "  python md2docx.py examples/demo.md --show-config\n")
    parser.add_argument("inputs", nargs="*", help="Markdown 文件、目录或通配符")
    parser.add_argument("-o", "--output", help="输出 docx 路径；多个输入时视为输出目录")
    parser.add_argument("-c", "--config", help="配置模板（只写要改的项即可）")
    parser.add_argument("--set", dest="sets", action="append",
                        metavar="KEY=VALUE", help="临时覆盖配置，可重复，如 --set page.size=A4")
    parser.add_argument("--no-mermaid", action="store_true", help="不渲染 mermaid，原样输出代码块")
    parser.add_argument("--show-config", action="store_true", help="打印合并后的配置后退出")
    parser.add_argument("--show-paths", action="store_true",
                        help="打印资源路径与冻结状态后退出（排查打包问题用）")
    parser.add_argument("-q", "--quiet", action="store_true", help="只输出必要信息")
    parser.add_argument("-V", "--version", action="version",
                        version=f"md2docx {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.show_paths:
        print(f"md2docx {__version__}")
        print(resources.describe())
        return 0

    overrides = _parse_set(args.sets)
    if args.no_mermaid:
        overrides["mermaid.renderer"] = "off"
    try:
        config = load_config(args.config, overrides)
    except (ConfigValueError, OSError) as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return 2

    if args.show_config:
        import yaml
        print(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        return 0

    if not args.inputs:
        build_parser().print_help()
        return 1

    files = _collect_inputs(args.inputs)
    missing = [f for f in files if not os.path.exists(f)]
    for f in missing:
        print(f"[跳过] 文件不存在：{f}", file=sys.stderr)
    files = [f for f in files if os.path.exists(f)]
    if not files:
        print("没有可处理的 Markdown 文件。", file=sys.stderr)
        return 1

    multi = len(files) > 1
    out_dir_is_dir = bool(args.output and (multi or os.path.isdir(args.output)
                                          or not args.output.lower().endswith(".docx")))
    failures = 0
    t_all = time.time()

    for index, src in enumerate(files, 1):
        stem = os.path.splitext(os.path.basename(src))[0]
        if not args.output:
            out_path = os.path.join(os.path.dirname(src), stem + ".docx")
        elif out_dir_is_dir:
            out_path = os.path.join(args.output, stem + ".docx")
        else:
            out_path = args.output

        if not args.quiet:
            print(f"[{index}/{len(files)}] {os.path.basename(src)} → {out_path}")
        t0 = time.time()
        converter = None
        try:
            converter = MarkdownToDocx(config, src, out_path,
                                       log=(lambda *a: None) if args.quiet else print)
            with open(src, "r", encoding="utf-8") as fh:
                text = fh.read()
            converter.render(text)
            for warning in converter.warnings:
                print(f"  ! {warning}")
            converter.save()
            size_kb = os.path.getsize(out_path) / 1024
            c = converter.counters
            print(f"  完成 {size_kb:.0f} KB / {time.time() - t0:.1f}s ："
                  f"标题 {c['heading']}，段落 {c['paragraph']}，表格 {c['table']}，"
                  f"列表 {c['list']}，代码块 {c['code'] - c['mermaid']}，"
                  f"mermaid 图 {c['mermaid']}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  [失败] {type(exc).__name__}: {exc}", file=sys.stderr)
            import traceback
            if os.environ.get("MD2DOCX_DEBUG"):
                traceback.print_exc()
        finally:
            if converter is not None and converter._mermaid is not None:
                converter._mermaid.close()

    if len(files) > 1:
        print(f"共 {len(files)} 个文件，失败 {failures} 个，"
              f"耗时 {time.time() - t_all:.1f}s")
    return 1 if failures else 0
