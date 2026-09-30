"""Plan semantic versions and publish verified DocBridge releases via GitHub CLI."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / 'src/md2docx/__init__.py'
SEMVER = re.compile(r'^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
VERSION_LINE = re.compile(r'^__version__\s*=\s*([\"\'])([^\"\']+)\1\s*$', re.MULTILINE)


def run(*args, check=True):
    return subprocess.run(args, cwd=ROOT, check=check, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def version_tuple(value):
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f'Invalid release version: {value}')
    return tuple(map(int, match.groups()))


def source_version():
    match = VERSION_LINE.search(VERSION_FILE.read_text(encoding='utf-8'))
    if not match:
        raise ValueError('Source version is missing')
    version_tuple(match[2])
    return match[2]


def write_version(value):
    version_tuple(value)
    text = VERSION_FILE.read_text(encoding='utf-8')
    result, count = VERSION_LINE.subn(f'__version__ = "{value}"', text)
    if count != 1:
        raise ValueError('Expected one source version declaration')
    VERSION_FILE.write_text(result, encoding='utf-8')


def tag_records():
    records = []
    for tag in run('git', 'tag', '--list', 'v*').stdout.splitlines():
        if not SEMVER.fullmatch(tag):
            continue
        commit = run('git', 'rev-list', '-n', '1', tag).stdout.strip()
        annotation = run('git', 'for-each-ref', '--format=%(contents)', f'refs/tags/{tag}').stdout
        origin = re.search(r'^Source-Commit: ([0-9a-f]{40})$', annotation, re.MULTILINE)
        records.append((tag, origin[1] if origin else commit))
    return records


def choose_version(base, records, sha, release):
    base_tuple = version_tuple(base)
    if not release:
        return base
    matching = [tag for tag, origin in records if origin == sha]
    if matching:
        return max(matching, key=version_tuple).removeprefix('v')
    versions = [version_tuple(tag) for tag, _ in records]
    if not versions or base_tuple > max(versions):
        return base
    major, minor, patch = max(versions)
    return f'{major}.{minor}.{patch + 1}'


def plan():
    sha = os.environ.get('GITHUB_SHA') or run('git', 'rev-parse', 'HEAD').stdout.strip()
    event, ref = os.environ.get('GITHUB_EVENT_NAME'), os.environ.get('GITHUB_REF')
    release = event in ('push', 'workflow_dispatch') and ref == 'refs/heads/main'
    version = choose_version(source_version(), tag_records(), sha, release)
    write_version(version)
    values = {'version': version, 'tag': 'v' + version, 'release': str(release).lower()}
    if output := os.environ.get('GITHUB_OUTPUT'):
        with Path(output).open('a', encoding='utf-8') as stream:
            for key, value in values.items():
                stream.write(f'{key}={value}\n')
    print(f'Version: {version}; automatic release: {release}', flush=True)


def publish(version, sha, folder):
    version_tuple(version)
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Expected a full source commit SHA')
    folder = Path(folder).resolve()
    names = ['docbridge.exe', 'md2docx.exe', 'docx2md.exe', f'docbridge-{version}-win64.zip']
    files = [folder / name for name in names]
    if any(not path.is_file() or not path.stat().st_size for path in files):
        raise ValueError('Release artifacts are incomplete')
    manifest = folder / 'SHA256SUMS.txt'
    manifest.write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
                               for path in files), encoding='utf-8')
    files.append(manifest)
    tag = 'v' + version
    records = dict(tag_records())
    if tag in records:
        if records[tag] != sha:
            raise ValueError(f'{tag} already belongs to a different source commit')
    else:
        if run('git', 'rev-parse', 'HEAD').stdout.strip() != sha:
            raise ValueError('Release checkout does not match the built source')
        run('git', 'diff', '--quiet')
        run('git', 'diff', '--cached', '--quiet')
        run('git', 'checkout', '--detach', sha)
        write_version(version)
        run('git', 'config', 'user.name', 'github-actions[bot]')
        run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        run('git', 'add', '--', 'src/md2docx/__init__.py')
        if run('git', 'diff', '--cached', '--quiet', check=False).returncode:
            run('git', 'commit', '-m', f'chore: release {tag}')
        run('git', 'tag', '-a', tag, '-m', f'DocBridge {tag}\n\nSource-Commit: {sha}')
        run('git', 'push', 'origin', f'refs/tags/{tag}')
    existing = run('gh', 'release', 'view', tag, '--json', 'url', check=False)
    if existing.returncode:
        run('gh', 'release', 'create', tag, '--verify-tag', '--draft', '--latest=false',
            '--title', f'DocBridge {tag}', '--generate-notes')
    run('gh', 'release', 'upload', tag, *(str(path) for path in files), '--clobber')
    newest = max((version_tuple(name) for name, _ in tag_records()), default=version_tuple(tag))
    latest = '--latest' if version_tuple(tag) == newest else '--latest=false'
    run('gh', 'release', 'edit', tag, '--draft=false', latest)
    print(run('gh', 'release', 'view', tag, '--json', 'url', '--jq', '.url').stdout.strip(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('plan')
    release = subparsers.add_parser('publish')
    release.add_argument('--version', required=True)
    release.add_argument('--sha', required=True)
    release.add_argument('--artifacts', default='dist')
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            plan()
        else:
            publish(args.version, args.sha, args.artifacts)
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or '', exc.stderr or '', flush=True)
        raise


if __name__ == '__main__':
    main()
