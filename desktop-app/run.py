"""Launcher used for running from VS Code and for building the .exe with PyInstaller."""
import sys

from crkit_app.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
