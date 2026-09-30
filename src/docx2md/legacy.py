"""Legacy Word adapter. Resolve local engines without downloading or launching."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .runtime import runtime_dir


def find_libreoffice():
    explicit = os.environ.get('DOCX2MD_LIBREOFFICE')
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ValueError(f'DOCX2MD_LIBREOFFICE 指定的程序不存在：{path}')
        return path.resolve()
    roots = []
    if getattr(sys, 'frozen', False):
        folder = Path(sys.executable).resolve().parent
        roots.extend([folder, folder.parent])
    roots.append(Path(__file__).resolve().parents[2])
    names = ('soffice.com', 'soffice.exe') if os.name == 'nt' else ('soffice',)
    for name in names:
        optional = runtime_dir() / 'program' / name
        if optional.is_file():
            return optional
    for root in roots:
        for name in names:
            bundled = root / 'runtime/libreoffice/program' / name
            if bundled.is_file():
                return bundled
    for name in ('soffice', 'libreoffice'):
        found = shutil.which(name)
        if found:
            return Path(found)
    if os.name == 'nt':
        for folder in (os.environ.get('PROGRAMFILES', 'C:/Program Files'), 'C:/Program Files (x86)'):
            for name in names:
                installed = Path(folder) / 'LibreOffice/program' / name
                if installed.is_file():
                    return installed
    raise ValueError('未启用 .doc 转换引擎。请在“.doc 支持”页点击“下载并启用”，或运行 docx2md.py --download-engine。')


def convert_legacy_doc(source, temp):
    executable = find_libreoffice()
    profile = (temp / 'lo-profile').resolve().as_uri()
    command = [str(executable), f'-env:UserInstallation={profile}', '--headless', '--norestore',
               '--nodefault', '--nofirststartwizard', '--convert-to', 'docx:Office Open XML Text',
               '--outdir', str(temp), str(source)]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=flags, start_new_session=os.name != 'nt')
    try:
        stdout, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, creationflags=flags, timeout=15)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise ValueError('.doc 转换超时，请检查文档是否损坏或需要密码。') from None
    converted = temp / (source.stem + '.docx')
    if process.returncode or not converted.is_file():
        detail = (stderr or stdout).decode('utf-8', errors='replace').strip()[-1000:]
        raise ValueError('无法把 .doc 转换为 .docx。' + ('\n' + detail if detail else ''))
    return converted
