"""File discovery independent of any converter or UI toolkit."""
from pathlib import Path
import glob


def collect_files(inputs, recursive=False, extensions=()):
    files = []
    for item in inputs:
        path = Path(item)
        matches = [path] if path.exists() else [Path(p) for p in glob.glob(str(item), recursive=recursive)]
        if not matches:
            raise ValueError(f'找不到输入文件：{item}')
        for path in matches:
            candidates = (path.rglob('*') if recursive else path.iterdir()) if path.is_dir() else [path]
            files.extend(sorted(p.resolve() for p in candidates if p.is_file()
                                and p.suffix.lower() in extensions and not p.name.startswith('~$')))
    return list(dict.fromkeys(files))
