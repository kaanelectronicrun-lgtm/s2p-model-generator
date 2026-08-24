#!/usr/bin/env python3
"""Build standalone .exe using PyInstaller.

    python build_exe.py

Creates releases/s2p-<version>-win64.exe

Dependencies: pip install -r requirements.txt
"""
import os
import re
import sys
import shutil
import subprocess
from pathlib import Path


def get_version():
    """Extract version from src/s2p_tool/__init__.py."""
    init_file = Path("src/s2p_tool/__init__.py")
    if not init_file.exists():
        raise FileNotFoundError(f"Cannot find {init_file}")
    
    txt = init_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', txt)
    if not match:
        raise ValueError("Cannot find __version__ in __init__.py")
    return match.group(1)


def run_command(cmd, description=""):
    """Run a shell command and report errors."""
    if description:
        print(f"\n{'='*60}")
        print(f"[*] {description}")
        print('='*60)
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"✗ Command failed with exit code {result.returncode}")
        sys.exit(1)
    print(f"✓ {description or 'Command'} completed")


def main():
    """Build the executable."""
    print("\n" + "="*60)
    print("S2P Tool - EXE Builder")
    print("="*60)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("✗ Python 3.8+ required")
        sys.exit(1)
    
    version = get_version()
    print(f"\nVersion: {version}")
    
    # Create releases directory
    releases_dir = Path("releases")
    releases_dir.mkdir(exist_ok=True)
    
    exe_name = f"s2p-{version}-win64"
    exe_path = releases_dir / f"{exe_name}.exe"
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("\n✗ PyInstaller not found. Installing dependencies...")
        run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            "Installing dependencies"
        )
    
    # PyInstaller command
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                           # Single exe file
        "--windowed",                          # No console window
        "--name", exe_name,                    # Output exe name
        "--distpath", str(releases_dir),       # Output directory
        "--workpath", "build",                 # Build directory
        "--specpath", ".",                     # Spec file location
        "--paths", "src",                      # Search path for s2p_tool package
        "--hidden-import=s2p_tool",            # Ensure package is bundled
        "--hidden-import=pypdf",               # PDF datasheet text extraction
        "--hidden-import=fitz",                # PyMuPDF: PDF vector-curve extraction
        "--collect-all=pymupdf",               # bundle PyMuPDF binaries/data
        "--hidden-import=openpyxl",            # Komponent Analizi Excel toplama
        "--collect-submodules=openpyxl",       # openpyxl lazy submodules
        "--hidden-import=numpy",
        "--hidden-import=PyQt5",
        "--hidden-import=PyQt5.QtCore",
        "--hidden-import=PyQt5.QtGui",
        "--hidden-import=PyQt5.QtWidgets",
        "--exclude-module=PyQt6",              # only one Qt binding may be frozen
        "--exclude-module=PySide6",            # (env has extra bindings installed)
        "--exclude-module=PySide2",
        # Heavy packages present in the dev env but NOT s2p dependencies — keep
        # the exe lean (torch alone is ~500 MB). cv2/pytesseract only feed the
        # optional raster-OCR path, which needs an external Tesseract binary
        # anyway, so excluding them costs nothing in the frozen app.
        "--exclude-module=torch",
        "--exclude-module=cv2",
        "--exclude-module=pytesseract",
        "--exclude-module=pandas",
        "--collect-all=pdfplumber",            # spec/pinout ruled-line tables
        "gui_main.py"                          # Entry point
    ]
    
    run_command(pyinstaller_cmd, "Building executable with PyInstaller")
    
    # Verify exe was created
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✓ SUCCESS: {exe_path.name} ({size_mb:.1f} MB)")
        print(f"\nYou can now run:")
        print(f"  {exe_path}")
        
        # Create a simple launcher batch script
        batch_file = releases_dir / "s2p-gui.bat"
        batch_file.write_text(f"""@echo off
cd /d "%~dp0"
start "" "{exe_name}.exe" %*
""")
        print(f"\nOr use the batch launcher:")
        print(f"  {batch_file}")
    else:
        print(f"\n✗ FAILED: {exe_path} was not created")
        sys.exit(1)
    
    # Cleanup build artifacts (optional)
    print("\nCleaning up temporary build files...")
    if Path("build").exists():
        shutil.rmtree("build", ignore_errors=True)
    spec_file = Path(f"{exe_name}.spec")
    if spec_file.exists():
        spec_file.unlink()
    
    print("\n" + "="*60)
    print("Build complete!")
    print("="*60)


if __name__ == "__main__":
    main()
