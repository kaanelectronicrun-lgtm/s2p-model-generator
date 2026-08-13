#!/usr/bin/env python3
"""GUI launcher for S2P Tool.

    python gui_main.py
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from s2p_tool.gui import main

if __name__ == "__main__":
    main()
