"""Word → Markdown command-line entry point."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from docx2md.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
