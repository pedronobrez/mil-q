#!/usr/bin/env python3
"""Shortcut: python run.py [file.wiff ...]"""
import sys

from milq.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
