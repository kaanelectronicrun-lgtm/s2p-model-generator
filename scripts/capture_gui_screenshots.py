"""Create reproducible GUI screenshots for the GitHub README."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QTabWidget

from s2p_tool.gui import S2PGui


def main() -> None:
    output = ROOT / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    app.setStyle("Fusion")
    window = S2PGui()
    window.resize(1180, 780)

    def capture() -> None:
        tabs = window.findChild(QTabWidget)
        for index, name in ((0, "01-model-generator.png"), (3, "02-datasheet-to-s2p.png"), (4, "03-component-analysis.png")):
            tabs.setCurrentIndex(index)
            if index == 4:
                window._an_widgets["auto"]["xlsx"].setText("outputs/component_analysis.xlsx")
            app.processEvents()
            window.grab().save(str(output / name), "PNG")
        window.close()
        app.quit()

    QTimer.singleShot(500, capture)
    app.exec_()


if __name__ == "__main__":
    main()
