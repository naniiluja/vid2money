"""Cho phép chạy: python -m videopipe "<topic>"."""

import sys

from videopipe.cli import main

if __name__ == "__main__":
    sys.exit(main())
