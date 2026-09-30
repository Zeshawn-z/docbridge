"""Stable desktop entry point; navigation and conversions are separate modules."""
from .shell import MainWindow, main

if __name__ == "__main__":
    raise SystemExit(main())
