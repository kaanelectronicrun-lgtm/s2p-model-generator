#!/usr/bin/env python3
"""Root launcher so you can run without installing the package.

    python run.py components/example_cap.json
    python run.py components/*.json -o outputs
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from s2p_tool.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
