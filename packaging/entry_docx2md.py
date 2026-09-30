"""Frozen Word to Markdown CLI entry, separate from the docx2md package name."""
import os
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from docx2md.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
