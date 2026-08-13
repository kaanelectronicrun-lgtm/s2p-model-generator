"""PyInstaller entry point — frozen-friendly (no sys.path hacks).

When the exe is launched by double-click (its console has no parent shell), the
window would vanish the instant the program prints and exits. We detect that case
and pause so the output stays readable. The pause is additionally guarded by
isatty(), so piped/automated runs (CI, shells capturing output) never block.
"""
import sys

from s2p_tool.cli import main


def _double_clicked() -> bool:
    """True only when this process owns its console alone (Explorer double-click)."""
    try:
        import ctypes
        arr = (ctypes.c_uint * 2)()
        n = ctypes.windll.kernel32.GetConsoleProcessList(arr, 2)
        return n <= 1
    except Exception:
        return False


if __name__ == "__main__":
    rc = main()
    if _double_clicked() and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\n[Enter] to close...")
        except Exception:
            pass
    sys.exit(rc)
