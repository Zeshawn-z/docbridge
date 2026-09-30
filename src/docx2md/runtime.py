"""Optional LibreOffice runtime. Network access happens only in install_runtime."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

VERSION = '26.8.0'
MSI_NAME = f'LibreOffice_{VERSION}_Win_x86-64.msi'
SHA256 = '4aa6c6e1895f4055104effcb556bd3362d20c6ad707c149543304f395ef9db95'
DOWNLOAD = f'https://download.documentfoundation.org/libreoffice/stable/{VERSION}/win/x86_64/{MSI_NAME}'
SOURCE = 'https://download.documentfoundation.org/libreoffice/src/26.8.0/libreoffice-26.8.0.3.tar.xz'
DOWNLOAD_SIZE = 374906880


class DownloadCancelled(Exception):
    pass


def runtime_dir():
    override = os.environ.get('DOCX2MD_RUNTIME_DIR')
    if override:
        return Path(override).expanduser().resolve()
    local = os.environ.get('LOCALAPPDATA')
    base = Path(local) if local else Path.home() / '.local/share'
    # Preserve the existing engine cache when upgrading to the DocBridge name.
    return base / 'md2stdreport/runtime/libreoffice'


def _check_cancel(cancelled):
    if cancelled():
        raise DownloadCancelled('下载已取消')


def _verify(path, cancelled):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            _check_cancel(cancelled)
            digest.update(block)
    return digest.hexdigest() == SHA256


@contextmanager
def _installation_lock(folder):
    with (folder / 'download.lock').open('a+b') as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError('另一个窗口正在准备引擎，请等待它完成。') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _extract(msi, image):
    process = subprocess.Popen(['msiexec.exe', '/a', str(msi), '/qn',
                                f'TARGETDIR={image}'], creationflags=subprocess.CREATE_NO_WINDOW)
    code = process.wait(timeout=600)
    if code not in (0, 3010):
        raise ValueError(f'引擎准备失败（Windows Installer 错误 {code}），可重新下载后重试。')


def _assemble(image, destination):
    if not (image / 'program/soffice.com').is_file() or not (image / 'license.txt').is_file():
        raise ValueError('引擎文件不完整，请重试。')
    shutil.copytree(image, destination, ignore=shutil.ignore_patterns('*.msi'))
    for dll in (image / 'System64').glob('*.dll'):
        shutil.copy2(dll, destination / 'program' / dll.name)
    (destination / 'RUNTIME-SOURCE.txt').write_text(
        f'LibreOffice {VERSION}, The Document Foundation.\nOfficial MSI: {DOWNLOAD}\n'
        f'SHA-256: {SHA256}\nCorresponding source: {SOURCE}\n'
        'License and notices: license.txt, LICENSE.html, NOTICE, CREDITS.fodt.\n', encoding='utf-8')


def install_runtime(progress=lambda phase, current, total: None, cancelled=lambda: False,
                    destination=None):
    """Download, verify and prepare an engine following an explicit user action.

    Administrative extraction creates an application-local file image; it does
    not install LibreOffice system-wide. Cancellation during extraction is
    applied after Windows Installer exits, before publishing the runtime.
    """
    if os.name != 'nt':
        raise ValueError('自动下载引擎目前支持 Windows x64。其他系统可使用已安装的 LibreOffice。')
    destination = Path(destination or runtime_dir()).resolve()
    cache = destination.parent
    cache.mkdir(parents=True, exist_ok=True)
    with _installation_lock(cache):
        if (destination / 'program/soffice.com').is_file():
            return destination
        if destination.exists():
            raise ValueError(f'引擎目录不完整，请移走该目录后重试：{destination}')
        _check_cancel(cancelled)
        msi = cache / MSI_NAME
        progress('校验下载文件', 0, 0)
        if not msi.is_file() or not _verify(msi, cancelled):
            with tempfile.TemporaryDirectory(prefix='download-', dir=cache) as folder:
                partial = Path(folder) / 'engine.part'
                request = urllib.request.Request(DOWNLOAD, headers={'User-Agent': 'DocBridge/1.1'})
                with urllib.request.urlopen(request, timeout=30) as response, partial.open('wb') as stream:
                    total = int(response.headers.get('Content-Length', DOWNLOAD_SIZE))
                    count = 0
                    progress('正在下载', count, total)
                    while block := response.read(1024 * 1024):
                        _check_cancel(cancelled)
                        stream.write(block)
                        count += len(block)
                        progress('正在下载', count, total)
                _check_cancel(cancelled)
                progress('校验下载文件', 0, 0)
                if not _verify(partial, cancelled):
                    raise ValueError('下载文件校验失败，请重试。')
                partial.replace(msi)
        _check_cancel(cancelled)
        with tempfile.TemporaryDirectory(prefix='prepare-', dir=cache) as folder:
            image, ready = Path(folder) / 'image', Path(folder) / 'ready'
            progress('正在准备引擎', 0, 0)
            _extract(msi, image)
            _check_cancel(cancelled)
            _assemble(image, ready)
            _check_cancel(cancelled)
            ready.rename(destination)
        # The engine now owns its files; the large installer is no longer needed.
        try:
            msi.unlink()
        except OSError:
            pass
        progress('已启用', 1, 1)
        return destination
