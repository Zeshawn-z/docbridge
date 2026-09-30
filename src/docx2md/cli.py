import argparse
import glob
from pathlib import Path

from .converter import convert_file


def collect_files(inputs, recursive=False, extensions=('.docx', '.doc')):
    files = []
    for item in inputs:
        matches = [Path(item)] if Path(item).exists() else [Path(p) for p in glob.glob(item, recursive=recursive)]
        if not matches:
            raise ValueError(f'找不到输入文件：{item}')
        for path in matches:
            candidates = (path.rglob('*') if recursive else path.iterdir()) if path.is_dir() else [path]
            files.extend(sorted(p.resolve() for p in candidates if p.is_file()
                                and p.suffix.lower() in extensions and not p.name.startswith('~$')))
    return list(dict.fromkeys(files))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Word → Markdown：标题、目录、图片与表格')
    parser.add_argument('inputs', nargs='*', help='Word 文件、目录或通配符')
    parser.add_argument('--download-engine', action='store_true', help='主动下载并启用可选的 .doc 引擎')
    parser.add_argument('-o', '--output', help='输出目录，默认保存到每份原文件所在目录')
    parser.add_argument('-r', '--recursive', action='store_true', help='包含子目录')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已有结果；默认同步添加编号')
    args = parser.parse_args(argv)
    if args.download_engine:
        from .runtime import install_runtime
        try:
            last_phase = None
            def progress(phase, current, total):
                nonlocal last_phase
                if phase != last_phase:
                    print(phase, flush=True)
                    last_phase = phase
            print(f'引擎已启用：{install_runtime(progress)}')
        except Exception as exc:
            print(f'启用失败：{exc}')
            return 1
        if not args.inputs:
            return 0
    if not args.inputs:
        parser.error('请选择 Word 文件，或使用 --download-engine 启用 .doc 引擎。')
    try:
        files = collect_files(args.inputs, args.recursive)
        if not files:
            parser.error('没有可转换的 Word 文件。')
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    failed = 0
    for path in files:
        try:
            result = convert_file(path, args.output, overwrite=args.overwrite)
            print(f'完成：{result.markdown}（{result.image_count} 张图片）')
            for warning in result.warnings:
                print('  提示：' + warning)
        except Exception as exc:
            failed += 1
            print(f'失败：{path}：{exc}')
    print(f'成功 {len(files) - failed}，失败 {failed}')
    return 1 if failed else 0
