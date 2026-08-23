"""PyQt5 GUI for s2p tool - Capacitor/Inductor SPICE Model Generator."""

import sys
import os
import json
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QComboBox,
    QSpinBox, QDoubleSpinBox, QTextEdit, QTabWidget, QTableWidget,
    QTableWidgetItem, QProgressBar, QMessageBox, QListWidget, QListWidgetItem,
    QListWidgetItem, QGroupBox, QFormLayout, QFrame, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QTextCursor, QIcon


class ProcessWorker(QThread):
    """Background worker thread for processing components."""
    progress = pyqtSignal(str)  # Log message
    finished = pyqtSignal(bool, str)  # Success flag, message
    
    def __init__(self, input_paths, output_dir, z0, f_start, f_stop,
                 topology="series", dc_bias_v=None, temp_c=None, ac_vrms=None,
                 dc_bias_curve=None, tcc_curve=None):
        super().__init__()
        self.input_paths = input_paths
        self.output_dir = output_dir
        self.z0 = z0
        self.f_start = f_start
        self.f_stop = f_stop
        self.topology = topology
        self.dc_bias_v = dc_bias_v
        self.temp_c = temp_c
        self.ac_vrms = ac_vrms
        self.dc_bias_curve = dc_bias_curve
        self.tcc_curve = tcc_curve
    
    def run(self):
        """Execute processing in background thread."""
        try:
            # Import here to avoid circular imports
            from .pipeline import process
            
            os.makedirs(self.output_dir, exist_ok=True)
            
            for path in self.input_paths:
                try:
                    self.progress.emit(f"Processing: {Path(path).name}")
                    s2p_path, cir_path, rep_path = process(
                        path, self.output_dir, self.z0, self.f_start,
                        self.f_stop, self.topology,
                        self.dc_bias_v, self.temp_c, self.ac_vrms,
                        self.dc_bias_curve, self.tcc_curve
                    )
                    self.progress.emit(f"✓ {Path(path).name}\n  → {Path(s2p_path).name}")
                except Exception as e:
                    self.progress.emit(f"✗ {Path(path).name}: {str(e)}")
            
            self.progress.emit("\n" + "="*60)
            self.progress.emit(f"Tüm dosyalar '{self.output_dir}' klasörüne kaydedildi.")
            self.finished.emit(True, "İşlem başarıyla tamamlandı!")
            
        except Exception as e:
            self.finished.emit(False, f"Hata: {str(e)}")


class AutoWorker(QThread):
    """Background worker: datasheet PDF -> s2p in one step (may take ~30 s)."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, pdf, kind, out_dir, z0, f_start, f_stop, topology,
                 dc_bias_v, temp_c, ac_vrms, extract_curves):
        super().__init__()
        self.args = (pdf, kind, out_dir, z0, f_start, f_stop, topology,
                     dc_bias_v, temp_c, ac_vrms, extract_curves)

    def run(self):
        try:
            from .pipeline import process_pdf
            (pdf, kind, out_dir, z0, fs, fe, topo, dc, tc, ac, ec) = self.args
            self.progress.emit(f"Datasheet okunuyor: {Path(pdf).name}")
            self.progress.emit("Metin + vektör grafik çıkarımı (birkaç saniye)...")
            s2p, cir, rep = process_pdf(pdf, kind, out_dir, z0, fs, fe, topo,
                                        dc, tc, ac, ec)
            self.progress.emit(f"✓ {Path(s2p).name}\n  → {Path(cir).name}\n  "
                               f"→ {Path(rep).name}")
            self.finished.emit(True, "Datasheet → S2P tamamlandı!")
        except Exception as e:
            self.finished.emit(False, f"Hata: {str(e)}")


class AnalysisWorker(QThread):
    """Background worker: datasheet PDF -> structured component analysis."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, object)  # ok, result dict (or error string)

    def __init__(self, pdf, type_hint, out_dir, lang="tr"):
        super().__init__()
        self.pdf = pdf
        self.type_hint = type_hint
        self.out_dir = out_dir
        self.lang = lang

    def run(self):
        try:
            from .component_analysis import analyze_pdf
            self.progress.emit(f"Datasheet okunuyor: {Path(self.pdf).name}")
            self.progress.emit("Tür tespiti + spec + vektör eğri çıkarımı...")
            res = analyze_pdf(self.pdf, self.type_hint, self.out_dir, self.lang)
            self.finished.emit(True, res)
        except Exception as e:
            self.finished.emit(False, f"Hata: {str(e)}")


class S2PGui(QMainWindow):
    """Main GUI window for s2p tool."""
    
    def __init__(self):
        super().__init__()
        self.input_files = []
        self.worker = None
        self.init_ui()
        self.setWindowTitle("S2P Tool - SPICE Model Generator")
        self.resize(1000, 700)
        self.show()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tabs
        tabs = QTabWidget()
        tabs.addTab(self.create_process_tab(), "Model Üret")
        tabs.addTab(self.create_import_tab(), "S2P İçeri Aktar")
        tabs.addTab(self.create_pdf_tab(), "PDF'ten Model")
        tabs.addTab(self.create_auto_tab(), "Datasheet → S2P")
        tabs.addTab(self.create_analysis_tab(), "Komponent Analizi")
        tabs.addTab(self.create_settings_tab(), "Ayarlar")
        tabs.addTab(self.create_help_tab(), "Yardım")
        
        main_layout.addWidget(tabs)
        central_widget.setLayout(main_layout)
    
    def create_process_tab(self):
        """Create the main processing tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Input section
        input_group = self.create_input_group()
        layout.addWidget(input_group)
        
        # Parameters section
        params_group = self.create_params_group()
        layout.addWidget(params_group)
        
        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Çıktı Klasörü:"))
        self.output_dir_edit = QLineEdit("outputs")
        output_layout.addWidget(self.output_dir_edit)
        self.output_browse_btn = QPushButton("Gözat...")
        self.output_browse_btn.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(self.output_browse_btn)
        layout.addLayout(output_layout)
        
        # Process button
        self.process_btn = QPushButton("Model Üret")
        self.process_btn.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; background-color: #4CAF50; color: white; }")
        self.process_btn.clicked.connect(self.start_processing)
        layout.addWidget(self.process_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Output log
        log_label = QLabel("İşlem Günlüğü:")
        layout.addWidget(log_label)
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setMaximumHeight(200)
        layout.addWidget(self.output_log)
        
        layout.addStretch()
        tab.setLayout(layout)
        return tab
    
    def create_input_group(self):
        """Create input files selection group."""
        group = QGroupBox("Giriş Dosyaları")
        layout = QVBoxLayout()
        
        # File list
        list_layout = QHBoxLayout()
        self.file_list = QListWidget()
        list_layout.addWidget(self.file_list)
        
        # File buttons
        btn_layout = QVBoxLayout()
        add_btn = QPushButton("Dosya Ekle")
        add_btn.clicked.connect(self.add_input_files)
        btn_layout.addWidget(add_btn)
        
        add_dir_btn = QPushButton("Klasör Ekle")
        add_dir_btn.clicked.connect(self.add_input_directory)
        btn_layout.addWidget(add_dir_btn)
        
        remove_btn = QPushButton("Sil")
        remove_btn.clicked.connect(self.remove_input_file)
        btn_layout.addWidget(remove_btn)
        
        clear_btn = QPushButton("Tümünü Temizle")
        clear_btn.clicked.connect(self.clear_input_files)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        list_layout.addLayout(btn_layout)
        
        layout.addLayout(list_layout)
        group.setLayout(layout)
        return group
    
    def create_params_group(self):
        """Create parameters group."""
        group = QGroupBox("Parametre Ayarları")
        layout = QFormLayout()
        
        # Z0
        self.z0_spin = QDoubleSpinBox()
        self.z0_spin.setValue(50.0)
        self.z0_spin.setRange(1.0, 1000.0)
        self.z0_spin.setSuffix(" Ω")
        layout.addRow("Referans İmpedans (Z0):", self.z0_spin)
        
        # Frequency start
        self.f_start_spin = QDoubleSpinBox()
        self.f_start_spin.setDecimals(0)
        self.f_start_spin.setRange(1, 1e15)
        self.f_start_spin.setValue(1e4)
        self.f_start_spin.setSuffix(" Hz")
        layout.addRow("Başlangıç Frekansı:", self.f_start_spin)
        
        # Frequency stop
        self.f_stop_spin = QDoubleSpinBox()
        self.f_stop_spin.setDecimals(0)
        self.f_stop_spin.setRange(1, 1e15)
        self.f_stop_spin.setValue(1e10)
        self.f_stop_spin.setSuffix(" Hz")
        layout.addRow("Bitiş Frekansı:", self.f_stop_spin)

        # Topology: series-through vs shunt-to-ground
        self.topology_combo = QComboBox()
        self.topology_combo.addItems(["Series (seri / hat üzeri)",
                                      "Shunt (şönt / şaseye)"])
        layout.addRow("Topoloji:", self.topology_combo)

        # Operating conditions (Murata SimSurfing style) -> capacitance derating
        self.dc_bias_spin = QDoubleSpinBox()
        self.dc_bias_spin.setRange(0.0, 2000.0)
        self.dc_bias_spin.setValue(0.0)
        self.dc_bias_spin.setSuffix(" V")
        layout.addRow("DC Bias (0 = yok):", self.dc_bias_spin)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(-273.0, 400.0)
        self.temp_spin.setValue(25.0)
        self.temp_spin.setSuffix(" °C")
        layout.addRow("Sıcaklık:", self.temp_spin)

        self.ac_vrms_spin = QDoubleSpinBox()
        self.ac_vrms_spin.setRange(0.0, 100.0)
        self.ac_vrms_spin.setDecimals(2)
        self.ac_vrms_spin.setValue(0.0)
        self.ac_vrms_spin.setSuffix(" Vrms")
        layout.addRow("AC Sürüş (0 = yok):", self.ac_vrms_spin)

        # Optional vendor derating curves (SimSurfing CSV) -> exact derating
        dc_curve_row = QHBoxLayout()
        self.dc_curve_edit = QLineEdit()
        self.dc_curve_edit.setPlaceholderText("DC-bias CSV (opsiyonel)")
        dc_curve_row.addWidget(self.dc_curve_edit)
        dc_curve_btn = QPushButton("Gözat...")
        dc_curve_btn.clicked.connect(lambda: self.browse_csv_curve(self.dc_curve_edit))
        dc_curve_row.addWidget(dc_curve_btn)
        layout.addRow("DC-bias eğrisi:", dc_curve_row)

        tcc_curve_row = QHBoxLayout()
        self.tcc_curve_edit = QLineEdit()
        self.tcc_curve_edit.setPlaceholderText("Sıcaklık (TCC) CSV (opsiyonel)")
        tcc_curve_row.addWidget(self.tcc_curve_edit)
        tcc_curve_btn = QPushButton("Gözat...")
        tcc_curve_btn.clicked.connect(lambda: self.browse_csv_curve(self.tcc_curve_edit))
        tcc_curve_row.addWidget(tcc_curve_btn)
        layout.addRow("TCC eğrisi:", tcc_curve_row)
        group.setLayout(layout)
        return group
    
    def create_import_tab(self):
        """Create S2P import tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Select S2P file
        s2p_layout = QHBoxLayout()
        s2p_layout.addWidget(QLabel("S2P Dosyası:"))
        self.import_s2p_edit = QLineEdit()
        s2p_layout.addWidget(self.import_s2p_edit)
        browse_btn = QPushButton("Gözat...")
        browse_btn.clicked.connect(self.browse_s2p_file)
        s2p_layout.addWidget(browse_btn)
        layout.addLayout(s2p_layout)
        
        # Component kind
        kind_layout = QHBoxLayout()
        kind_layout.addWidget(QLabel("Bileşen Türü:"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["capacitor", "inductor"])
        kind_layout.addWidget(self.kind_combo)
        self.import_topology_combo = QComboBox()
        self.import_topology_combo.addItems(["Series (seri)", "Shunt (şönt)"])
        kind_layout.addWidget(QLabel("Topoloji:"))
        kind_layout.addWidget(self.import_topology_combo)
        kind_layout.addStretch()
        layout.addLayout(kind_layout)
        
        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Çıktı Klasörü:"))
        self.import_out_edit = QLineEdit("outputs")
        output_layout.addWidget(self.import_out_edit)
        browse_out_btn = QPushButton("Gözat...")
        browse_out_btn.clicked.connect(lambda: self.browse_output_dir(self.import_out_edit))
        output_layout.addWidget(browse_out_btn)
        layout.addLayout(output_layout)
        
        # Import button
        import_btn = QPushButton("İçeri Aktar")
        import_btn.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; background-color: #2196F3; color: white; }")
        import_btn.clicked.connect(self.start_import)
        layout.addWidget(import_btn)
        
        # Import log
        log_label = QLabel("İşlem Günlüğü:")
        layout.addWidget(log_label)
        self.import_log = QTextEdit()
        self.import_log.setReadOnly(True)
        layout.addWidget(self.import_log)
        
        layout.addStretch()
        tab.setLayout(layout)
        return tab
    
    def create_pdf_tab(self):
        """Create the PDF -> template -> model tab."""
        tab = QWidget()
        layout = QVBoxLayout()

        info = QLabel(
            "PDF datasheet'ten model üretimi 2 aşamalıdır:\n"
            "1) PDF'ten değerler çıkarılır (kapasitans, voltaj, dielektrik, kılıf...).\n"
            "2) Çıkan JSON'u GÖZDEN GEÇİRİN — SRF/ESR/ESL genelde PDF metninde yoktur,\n"
            "   gerekiyorsa elle ekleyin — sonra 'Model Üret'e basın."
        )
        info.setStyleSheet("QLabel { background:#FFF3CD; padding:8px; border:1px solid #FFE69C; }")
        layout.addWidget(info)

        # PDF file selector
        pdf_layout = QHBoxLayout()
        pdf_layout.addWidget(QLabel("PDF Dosyası:"))
        self.pdf_path_edit = QLineEdit()
        pdf_layout.addWidget(self.pdf_path_edit)
        browse_btn = QPushButton("Gözat...")
        browse_btn.clicked.connect(self.browse_pdf_file)
        pdf_layout.addWidget(browse_btn)
        layout.addLayout(pdf_layout)

        # Component kind
        kind_layout = QHBoxLayout()
        kind_layout.addWidget(QLabel("Bileşen Türü:"))
        self.pdf_kind_combo = QComboBox()
        self.pdf_kind_combo.addItems(["capacitor", "inductor"])
        kind_layout.addWidget(self.pdf_kind_combo)
        kind_layout.addStretch()
        self.pdf_extract_btn = QPushButton("PDF'ten Çıkar")
        self.pdf_extract_btn.setStyleSheet(
            "QPushButton { padding:6px; background-color:#FF9800; color:white; }")
        self.pdf_extract_btn.clicked.connect(self.extract_pdf)
        kind_layout.addWidget(self.pdf_extract_btn)
        layout.addLayout(kind_layout)

        # Editable extracted JSON
        layout.addWidget(QLabel("Çıkarılan JSON (gözden geçirin / düzenleyin):"))
        self.pdf_json_edit = QTextEdit()
        self.pdf_json_edit.setPlaceholderText(
            "PDF'i çıkardıktan sonra JSON burada görünür ve düzenlenebilir.")
        layout.addWidget(self.pdf_json_edit)

        # Output directory
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Çıktı Klasörü:"))
        self.pdf_out_edit = QLineEdit("outputs")
        out_layout.addWidget(self.pdf_out_edit)
        out_browse_btn = QPushButton("Gözat...")
        out_browse_btn.clicked.connect(lambda: self.browse_output_dir(self.pdf_out_edit))
        out_layout.addWidget(out_browse_btn)
        layout.addLayout(out_layout)

        # Topology
        pdf_topo_layout = QHBoxLayout()
        pdf_topo_layout.addWidget(QLabel("Topoloji:"))
        self.pdf_topology_combo = QComboBox()
        self.pdf_topology_combo.addItems(["Series (seri / hat üzeri)",
                                          "Shunt (şönt / şaseye)"])
        pdf_topo_layout.addWidget(self.pdf_topology_combo)
        pdf_topo_layout.addStretch()
        layout.addLayout(pdf_topo_layout)

        # Operating conditions -> capacitance derating
        pdf_cond_layout = QHBoxLayout()
        pdf_cond_layout.addWidget(QLabel("DC Bias:"))
        self.pdf_dc_bias_spin = QDoubleSpinBox()
        self.pdf_dc_bias_spin.setRange(0.0, 2000.0)
        self.pdf_dc_bias_spin.setSuffix(" V")
        pdf_cond_layout.addWidget(self.pdf_dc_bias_spin)
        pdf_cond_layout.addWidget(QLabel("Sıcaklık:"))
        self.pdf_temp_spin = QDoubleSpinBox()
        self.pdf_temp_spin.setRange(-273.0, 400.0)
        self.pdf_temp_spin.setValue(25.0)
        self.pdf_temp_spin.setSuffix(" °C")
        pdf_cond_layout.addWidget(self.pdf_temp_spin)
        pdf_cond_layout.addWidget(QLabel("AC:"))
        self.pdf_ac_vrms_spin = QDoubleSpinBox()
        self.pdf_ac_vrms_spin.setRange(0.0, 100.0)
        self.pdf_ac_vrms_spin.setDecimals(2)
        self.pdf_ac_vrms_spin.setSuffix(" Vrms")
        pdf_cond_layout.addWidget(self.pdf_ac_vrms_spin)
        pdf_cond_layout.addStretch()
        layout.addLayout(pdf_cond_layout)

        # Optional vendor derating curves (SimSurfing CSV) -> exact derating
        pdf_curve_layout = QHBoxLayout()
        pdf_curve_layout.addWidget(QLabel("DC-bias CSV:"))
        self.pdf_dc_curve_edit = QLineEdit()
        self.pdf_dc_curve_edit.setPlaceholderText("opsiyonel")
        pdf_curve_layout.addWidget(self.pdf_dc_curve_edit)
        pdf_dc_curve_btn = QPushButton("Gözat...")
        pdf_dc_curve_btn.clicked.connect(
            lambda: self.browse_csv_curve(self.pdf_dc_curve_edit))
        pdf_curve_layout.addWidget(pdf_dc_curve_btn)
        pdf_curve_layout.addWidget(QLabel("TCC CSV:"))
        self.pdf_tcc_curve_edit = QLineEdit()
        self.pdf_tcc_curve_edit.setPlaceholderText("opsiyonel")
        pdf_curve_layout.addWidget(self.pdf_tcc_curve_edit)
        pdf_tcc_curve_btn = QPushButton("Gözat...")
        pdf_tcc_curve_btn.clicked.connect(
            lambda: self.browse_csv_curve(self.pdf_tcc_curve_edit))
        pdf_curve_layout.addWidget(pdf_tcc_curve_btn)
        layout.addLayout(pdf_curve_layout)

        # Generate button
        self.pdf_gen_btn = QPushButton("Model Üret")
        self.pdf_gen_btn.setStyleSheet(
            "QPushButton { font-size:14px; padding:10px; background-color:#4CAF50; color:white; }")
        self.pdf_gen_btn.clicked.connect(self.generate_from_pdf)
        layout.addWidget(self.pdf_gen_btn)

        # Log
        layout.addWidget(QLabel("İşlem Günlüğü:"))
        self.pdf_log = QTextEdit()
        self.pdf_log.setReadOnly(True)
        self.pdf_log.setMaximumHeight(120)
        layout.addWidget(self.pdf_log)

        tab.setLayout(layout)
        return tab

    def browse_pdf_file(self):
        """Browse for a datasheet PDF."""
        file, _ = QFileDialog.getOpenFileName(
            self, "PDF Datasheet Seç", "", "PDF Files (*.pdf);;Tüm Dosyalar (*)")
        if file:
            self.pdf_path_edit.setText(file)

    def extract_pdf(self):
        """Extract a datasheet PDF into an editable JSON template."""
        pdf_file = self.pdf_path_edit.text()
        if not pdf_file or not os.path.isfile(pdf_file):
            QMessageBox.warning(self, "Uyarı", "Lütfen geçerli bir PDF dosyası seçin!")
            return
        try:
            from .pdfreader import extract_text, extract_capacitor, extract_inductor, _part_number
            import re
            kind = self.pdf_kind_combo.currentText()
            self.pdf_log.clear()
            self.pdf_log.insertPlainText(f"PDF okunuyor: {Path(pdf_file).name}\n")
            text = extract_text(pdf_file)
            stem = os.path.splitext(os.path.basename(pdf_file))[0]
            part = _part_number(text, re.sub(r"[^A-Za-z0-9_.-]", "_", stem))
            found = extract_capacitor(text) if kind == "capacitor" else extract_inductor(text)
            data = {"kind": kind, "part_number": part}
            data.update({k: v for k, v in found.items() if v is not None})
            data["source"] = 5
            missing = [k for k, v in found.items() if v is None]
            self.pdf_json_edit.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
            self.pdf_log.insertPlainText("✓ Çıkarma tamam. Bulunan alanlar yüklendi.\n")
            if missing:
                self.pdf_log.insertPlainText(
                    "⚠ Bulunamayan alanlar: " + ", ".join(missing)
                    + "\n  SRF/ESR/ESL genelde PDF metninde olmaz — elle ekleyin.\n")
        except Exception as e:
            self.pdf_log.insertPlainText(f"✗ Hata: {str(e)}\n")
            QMessageBox.critical(self, "Hata", f"PDF çıkarma hatası:\n{str(e)}")

    def generate_from_pdf(self):
        """Generate a model from the edited JSON in the PDF tab."""
        raw = self.pdf_json_edit.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Uyarı", "Önce PDF'ten çıkarma yapın veya JSON girin!")
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Hata", f"Geçersiz JSON:\n{str(e)}")
            return
        try:
            from .pipeline import process
            out_dir = self.pdf_out_edit.text()
            os.makedirs(out_dir, exist_ok=True)
            part = data.get("part_number", "part")
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in part)
            tmp_json = os.path.join(out_dir, f"{safe}_from_pdf.json")
            with open(tmp_json, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            self.pdf_log.insertPlainText(f"\nModel üretiliyor: {part}\n")
            topo = "shunt" if self.pdf_topology_combo.currentIndex() == 1 else "series"
            dc = self.pdf_dc_bias_spin.value() or None
            tc = self.pdf_temp_spin.value()
            tc = tc if tc != 25.0 else None
            ac = self.pdf_ac_vrms_spin.value() or None
            from .derate import load_curve_csv
            _dcc = self.pdf_dc_curve_edit.text().strip()
            _tcc = self.pdf_tcc_curve_edit.text().strip()
            dc_curve = load_curve_csv(_dcc) if _dcc else None
            tcc_curve = load_curve_csv(_tcc) if _tcc else None
            s2p_path, cir_path, rep_path = process(tmp_json, out_dir, 50.0, 1e4, 1e10,
                                                   topo, dc, tc, ac,
                                                   dc_curve, tcc_curve)
            self.pdf_log.insertPlainText(
                f"✓ Başarılı!\n  → {Path(s2p_path).name}\n"
                f"  → {Path(cir_path).name}\n  → {Path(rep_path).name}\n")
            QMessageBox.information(self, "Başarı", "PDF'ten model başarıyla üretildi!")
        except Exception as e:
            self.pdf_log.insertPlainText(f"✗ Hata: {str(e)}\n")
            QMessageBox.critical(self, "Hata", f"Model üretme hatası:\n{str(e)}")
    
    def create_settings_tab(self):
        """Create settings tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setHtml("""
        <h3>Ayarlar ve Bilgi</h3>
        <p><b>S2P Tool v1.0.0</b></p>
        <p>Kapasitor ve Inductor datasheet parametrelerini SPICE modeline dönüştürür.</p>
        
        <h4>Çıktı Dosyaları:</h4>
        <ul>
            <li><b>.s2p</b> - Touchstone S-parametreleri</li>
            <li><b>.cir</b> - SPICE netlist</li>
            <li><b>_report.md</b> - Detaylı rapor</li>
            <li><b>_Zf.csv</b> - İmpedans tablosu</li>
        </ul>
        
        <h4>Desteklenen Giriş Formatları:</h4>
        <ul>
            <li><b>JSON</b> - Parametre dosyaları (components/*.json)</li>
            <li><b>S2P</b> - Vendor Touchstone dosyaları</li>
            <li><b>PDF</b> - Datasheet PDF'leri (CLI'da)</li>
        </ul>
        
        <h4>Frekans Aralığı:</h4>
        <p>Varsayılan: 10 kHz - 10 GHz</p>
        <p>Ayarlardan değiştirebilirsiniz.</p>
        """)
        layout.addWidget(info_text)
        
        tab.setLayout(layout)
        return tab

    def create_auto_tab(self):
        """One-click: datasheet PDF -> .s2p directly (text + graph extraction)."""
        tab = QWidget()
        layout = QVBoxLayout()

        intro = QLabel(
            "Datasheet PDF'ini seç → tek tıkla .s2p/.cir/rapor. Parametreler ve "
            "grafikler doğrudan PDF vektöründen okunur:\n"
            "• |Z|–frekans eğrisi bulunursa her noktadan vector-fit ile YÜKSEK "
            "DOĞRULUK modeli (ESR eğrisi de kullanılır).\n"
            "• Bulunamazsa lumped model + DC-bias/sıcaklık derating eğrileri.\n"
            "Varsayılan tarama 1 kHz – 10 GHz (graph-fit'te eğrinin kapsadığı aralık).")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # PDF file
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("Datasheet PDF:"))
        self.auto_pdf_edit = QLineEdit()
        pdf_row.addWidget(self.auto_pdf_edit)
        pdf_btn = QPushButton("Gözat...")
        pdf_btn.clicked.connect(lambda: self.browse_pdf_into(self.auto_pdf_edit))
        pdf_row.addWidget(pdf_btn)
        layout.addLayout(pdf_row)

        # Kind + topology
        kt_row = QHBoxLayout()
        kt_row.addWidget(QLabel("Tür:"))
        self.auto_kind_combo = QComboBox()
        self.auto_kind_combo.addItems(["capacitor", "inductor"])
        kt_row.addWidget(self.auto_kind_combo)
        kt_row.addWidget(QLabel("Topoloji:"))
        self.auto_topology_combo = QComboBox()
        self.auto_topology_combo.addItems(["Series (seri)", "Shunt (şönt)"])
        kt_row.addWidget(self.auto_topology_combo)
        self.auto_curve_chk = QCheckBox("PDF grafiklerinden derating eğrisi çek")
        self.auto_curve_chk.setChecked(True)
        kt_row.addWidget(self.auto_curve_chk)
        kt_row.addStretch()
        layout.addLayout(kt_row)

        # Frequency range (1 kHz - 10 GHz defaults)
        fr_row = QHBoxLayout()
        fr_row.addWidget(QLabel("Frekans:"))
        self.auto_fstart_spin = QDoubleSpinBox()
        self.auto_fstart_spin.setDecimals(0)
        self.auto_fstart_spin.setRange(1, 1e15)
        self.auto_fstart_spin.setValue(1e3)
        self.auto_fstart_spin.setSuffix(" Hz")
        fr_row.addWidget(self.auto_fstart_spin)
        fr_row.addWidget(QLabel("→"))
        self.auto_fstop_spin = QDoubleSpinBox()
        self.auto_fstop_spin.setDecimals(0)
        self.auto_fstop_spin.setRange(1, 1e15)
        self.auto_fstop_spin.setValue(1e10)
        self.auto_fstop_spin.setSuffix(" Hz")
        fr_row.addWidget(self.auto_fstop_spin)
        fr_row.addStretch()
        layout.addLayout(fr_row)

        # Operating point
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("DC Bias:"))
        self.auto_dc_spin = QDoubleSpinBox()
        self.auto_dc_spin.setRange(0.0, 2000.0)
        self.auto_dc_spin.setSuffix(" V")
        op_row.addWidget(self.auto_dc_spin)
        op_row.addWidget(QLabel("Sıcaklık:"))
        self.auto_temp_spin = QDoubleSpinBox()
        self.auto_temp_spin.setRange(-273.0, 400.0)
        self.auto_temp_spin.setValue(25.0)
        self.auto_temp_spin.setSuffix(" °C")
        op_row.addWidget(self.auto_temp_spin)
        op_row.addWidget(QLabel("AC:"))
        self.auto_ac_spin = QDoubleSpinBox()
        self.auto_ac_spin.setRange(0.0, 100.0)
        self.auto_ac_spin.setDecimals(2)
        self.auto_ac_spin.setSuffix(" Vrms")
        op_row.addWidget(self.auto_ac_spin)
        op_row.addStretch()
        layout.addLayout(op_row)

        # Output dir
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Çıktı Klasörü:"))
        self.auto_out_edit = QLineEdit("outputs")
        out_row.addWidget(self.auto_out_edit)
        out_btn = QPushButton("Gözat...")
        out_btn.clicked.connect(lambda: self.browse_output_dir(self.auto_out_edit))
        out_row.addWidget(out_btn)
        layout.addLayout(out_row)

        # Generate button
        self.auto_gen_btn = QPushButton("Otomatik Oluştur (Datasheet → S2P)")
        self.auto_gen_btn.setStyleSheet(
            "QPushButton { font-size:14px; padding:10px; background-color:#FF9800; color:white; }")
        self.auto_gen_btn.clicked.connect(self.start_auto)
        layout.addWidget(self.auto_gen_btn)

        layout.addWidget(QLabel("İşlem Günlüğü:"))
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        layout.addWidget(self.auto_log)

        tab.setLayout(layout)
        return tab

    def browse_pdf_into(self, line_edit):
        file, _ = QFileDialog.getOpenFileName(
            self, "Datasheet PDF Seç", "", "PDF Files (*.pdf);;Tüm Dosyalar (*)")
        if file:
            line_edit.setText(file)

    def start_auto(self):
        pdf = self.auto_pdf_edit.text().strip()
        if not pdf or not os.path.isfile(pdf):
            QMessageBox.warning(self, "Uyarı", "Geçerli bir datasheet PDF seçin!")
            return
        dc = self.auto_dc_spin.value() or None
        tc = self.auto_temp_spin.value()
        tc = tc if tc != 25.0 else None
        ac = self.auto_ac_spin.value() or None
        self.auto_gen_btn.setEnabled(False)
        self.auto_log.clear()
        self.auto_worker = AutoWorker(
            pdf,
            self.auto_kind_combo.currentText(),
            self.auto_out_edit.text(),
            50.0,
            self.auto_fstart_spin.value(),
            self.auto_fstop_spin.value(),
            "shunt" if self.auto_topology_combo.currentIndex() == 1 else "series",
            dc, tc, ac, self.auto_curve_chk.isChecked())
        self.auto_worker.progress.connect(
            lambda m: self.auto_log.append(m))
        self.auto_worker.finished.connect(self.on_auto_finished)
        self.auto_worker.start()

    def on_auto_finished(self, ok, msg):
        self.auto_gen_btn.setEnabled(True)
        self.auto_log.append("\n" + ("✓ " if ok else "✗ ") + msg)
        if not ok:
            QMessageBox.critical(self, "Hata", msg)

    # ---- Komponent Analizi (datasheet -> spec + curves) --------------------
    def create_analysis_tab(self):
        """Parent tab: one sub-tab per component analyzer, plus auto-detect."""
        from .component_analysis import ANALYZERS
        outer = QWidget()
        ol = QVBoxLayout()
        intro = QLabel(
            "Datasheet PDF → komponent analizi (elektriksel spec + karakteristik "
            "eğri). Her komponent türü kendi alt-sekmesinde; 'Otomatik' türü "
            "metinden kendi tespit eder. Çıktı: JSON + eğri CSV'leri + rapor.")
        intro.setWordWrap(True)
        ol.addWidget(intro)
        inner = QTabWidget()
        self._an_widgets = {}
        inner.addTab(self._make_analysis_panel("auto", "Otomatik algıla"),
                     "Otomatik")
        for a in ANALYZERS:
            inner.addTab(self._make_analysis_panel(a.key, a.label), a.label)
        ol.addWidget(inner)
        outer.setLayout(ol)
        return outer

    def _make_analysis_panel(self, hint, label):
        panel = QWidget()
        lay = QVBoxLayout()
        w = {}
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("Datasheet PDF:"))
        w["pdf"] = QLineEdit()
        pdf_row.addWidget(w["pdf"])
        b = QPushButton("Gözat...")
        b.clicked.connect(lambda _=False, e=w["pdf"]: self.browse_pdf_into(e))
        pdf_row.addWidget(b)
        lay.addLayout(pdf_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Çıktı Klasörü:"))
        w["out"] = QLineEdit("outputs")
        out_row.addWidget(w["out"])
        ob = QPushButton("Gözat...")
        ob.clicked.connect(lambda _=False, e=w["out"]: self.browse_output_dir(e))
        out_row.addWidget(ob)
        lay.addLayout(out_row)

        xl_row = QHBoxLayout()
        w["xlsx_chk"] = QCheckBox("Excel'e topla:")
        w["xlsx_chk"].setChecked(True)
        xl_row.addWidget(w["xlsx_chk"])
        w["xlsx"] = QLineEdit(self._default_xlsx_path())
        xl_row.addWidget(w["xlsx"])
        xb = QPushButton("Gözat...")
        xb.clicked.connect(lambda _=False, e=w["xlsx"]: self.browse_xlsx_into(e))
        xl_row.addWidget(xb)
        lay.addLayout(xl_row)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Rapor dili:"))
        w["lang"] = QComboBox()
        w["lang"].addItem("Türkçe (otomatik çeviri)", "tr")
        w["lang"].addItem("İngilizce (orijinal, çevirisiz)", "en")
        lang_row.addWidget(w["lang"])
        lang_row.addWidget(QLabel(self._translate_backend_hint()))
        lang_row.addStretch()
        lay.addLayout(lang_row)

        w["btn"] = QPushButton(f"Analiz Et ({label})")
        w["btn"].setStyleSheet("QPushButton { font-size:14px; padding:10px; "
                               "background-color:#3F51B5; color:white; }")
        w["btn"].clicked.connect(lambda _=False, h=hint: self.start_analysis(h))
        lay.addWidget(w["btn"])

        lay.addWidget(QLabel("Sonuç:"))
        w["result"] = QTextEdit()
        w["result"].setReadOnly(True)
        lay.addWidget(w["result"])

        self._an_widgets[hint] = w
        panel.setLayout(lay)
        return panel

    @staticmethod
    def _translate_backend_hint():
        """One-line status of the available translation backend for the UI."""
        try:
            from .analysis import translate as _tr
            if _tr.argos_available("en", "tr"):
                return "çeviri: offline (argos) ✓"
            if _tr.deepl_available():
                return "çeviri: DeepL ✓"
            return "çeviri: yok — İngilizce kalır"
        except Exception:
            return ""

    def start_analysis(self, hint):
        w = self._an_widgets[hint]
        pdf = w["pdf"].text().strip()
        if not pdf or not os.path.isfile(pdf):
            QMessageBox.warning(self, "Uyarı", "Geçerli bir datasheet PDF seçin!")
            return
        w["btn"].setEnabled(False)
        w["result"].clear()
        lang = w["lang"].currentData() if "lang" in w else "tr"
        worker = AnalysisWorker(pdf, hint, w["out"].text(), lang)
        worker.progress.connect(lambda m, e=w["result"]: e.append(m))
        worker.finished.connect(
            lambda ok, res, h=hint: self.on_analysis_done(h, ok, res))
        self._an_worker = worker  # keep a reference so it isn't GC'd
        worker.start()

    @staticmethod
    def _default_xlsx_path():
        """Default aggregate workbook in the user's Downloads (predictable,
        independent of the exe's working directory)."""
        home = os.path.expanduser("~")
        dl = os.path.join(home, "Downloads")
        base = dl if os.path.isdir(dl) else home
        return os.path.join(base, "komponent_analizi.xlsx")

    def browse_xlsx_into(self, line_edit):
        file, _ = QFileDialog.getSaveFileName(
            self, "Excel Çalışma Kitabı", line_edit.text(),
            "Excel (*.xlsx);;Tüm Dosyalar (*)")
        if file:
            if not file.lower().endswith(".xlsx"):
                file += ".xlsx"
            line_edit.setText(file)

    def on_analysis_done(self, hint, ok, res):
        w = self._an_widgets[hint]
        w["btn"].setEnabled(True)
        if not ok:
            w["result"].append("\n✗ " + str(res))
            QMessageBox.critical(self, "Hata", str(res))
            return
        w["result"].setPlainText(self._format_analysis(res))
        if res.get("error"):
            return
        if w["xlsx_chk"].isChecked():
            path = w["xlsx"].text().strip()
            try:
                from .excel_export import append_analysis, available
                if not available():
                    w["result"].append("\n⚠️ Excel: openpyxl kurulu değil.")
                elif path:
                    append_analysis(res, path)
                    w["result"].append(
                        f"\n📊 Excel'e toplandı: {path} "
                        f"(parça '{res.get('part')}' upsert edildi)")
            except Exception as e:
                w["result"].append(f"\n⚠️ Excel yazma hatası: {e}")

    @staticmethod
    def _format_analysis(res):
        L = []
        L.append(f"KOMPONENT: {res.get('part', '?')}")
        L.append(f"TÜR: {res.get('type_label', res.get('type'))}")
        if res.get("subtype") and res.get("subtype") != "general":
            L.append(f"ALT TÜR: {res.get('subtype_label')}")
        ven = res.get("vendor")
        if ven and ven.get("key") != "generic":
            L.append(f"ÜRETİCİ: {ven.get('label')} (skor {ven.get('score')})")
        sc = res.get("section_confidence")
        if sc:
            badge = {"high": "✅", "med": "🟡", "low": "⚠️", "none": "—"}
            parts = [f"{k}:{badge.get(v.get('confidence'), '?')}"
                     for k, v in sc.items()]
            L.append("BÖLÜM GÜVENİ: " + "  ".join(parts))
        if res.get("detect_scores"):
            L.append(f"  (tespit skorları: {res['detect_scores']})")
        if res.get("error"):
            L.append("\n⚠️ " + res["error"])
            return "\n".join(L)
        if res.get("description"):
            L.append("\nAÇIKLAMA:\n" + res["description"])
        specs = res.get("specs", [])
        L.append("\nELEKTRİKSEL ÖZELLİKLER:")
        if specs:
            width = max(len(lab) for lab, _ in specs)
            for lab, val in specs:
                L.append(f"  {lab.ljust(width)} : {val}")
        else:
            L.append("  (metinden yapısal spec çıkarılamadı)")
        pins = res.get("pinout", [])
        if pins:
            L.append(f"\nPINOUT ({len(pins)} pin):")
            for p in pins:
                L.append(f"  {p['name']:6} {p['number']:12} {p['io']:3} "
                         f"{p['desc'][:60]}")
        curves = res.get("curves", {})
        data_curves = {k: v for k, v in curves.items()
                       if k != "_log" and isinstance(v, dict) and "npoints" in v}
        L.append("\nÇIKARILAN KARAKTERİSTİK EĞRİLER:")
        if data_curves:
            for k, c in data_curves.items():
                mark = "✅" if c["confidence"] == "high" else "⚠️ düşük"
                if c.get("traces"):
                    npts = sum(t["npoints"] for t in c["traces"])
                    extra = f", {c['ntraces']} iz (renk bazlı)"
                else:
                    npts, extra = c["npoints"], ""
                L.append(f"  {mark} {c['desc']}: {npts} nokta{extra} "
                         f"[{c['unit_x']} → {c['unit_y']}]")
            L.append("  (⚠️ düşük güvenli eğriler doğrulanmadan kullanılmamalı)")
        else:
            L.append("  (vektör grafikten güvenilir eğri çıkarılamadı)")
        interp = res.get("curve_interpretation", [])
        if interp:
            L.append("\nGRAFİK YORUMU:")
            for s in interp:
                L.append(f"  • {s}")
        req = res.get("design_requirements", [])
        if req:
            L.append("\nTASARIM GEREKSİNİMLERİ (örnek tasarım):")
            for lab, val in req:
                L.append(f"  {lab}: {val}")
        proc = res.get("design_procedure", [])
        if proc:
            L.append("\nTASARIM HESAPLARI (adım + değişken/sabit sözlüğü):")
            for s in proc:
                L.append(f"  ▸ {s['step']}")
                if s["intent"]:
                    L.append(f"      {s['intent'][:96]}")
                for g in s["vars"]:
                    L.append(f"      - {g[:80]}")
        lay = res.get("layout_guidelines", [])
        if lay:
            L.append("\nLAYOUT ÖNERİLERİ (datasheet §Layout Guidelines):")
            for s in lay:
                L.append(f"  • {s[:96]}")
            L.append("  (gerçek şematik/PCB üretimi → kicad/eda-agent skill'i)")
        outs = res.get("outputs", {})
        if outs:
            L.append("\nYAZILAN DOSYALAR:")
            for k, p in outs.items():
                L.append(f"  {k}: {p}")
        return "\n".join(L)
    
    def create_help_tab(self):
        """Create help tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h3>S2P Tool Kullanım Kılavuzu</h3>
        
        <h4>1. Model Oluşturma (Model Üret Sekmesi)</h4>
        <ol>
            <li>"Dosya Ekle" ile JSON parametre dosyaları seçin</li>
            <li>veya "Klasör Ekle" ile klasördeki tüm JSON dosyaları ekleyin</li>
            <li>İsteğe bağlı olarak Parametre Ayarlarını düzenleyin</li>
            <li>"Model Üret" düğmesine tıklayın</li>
            <li>Çıktılar "Çıktı Klasörü"nde oluşturulacak</li>
        </ol>
        
        <h4>2. S2P Dosyası İçeri Aktarma (S2P İçeri Aktar Sekmesi)</h4>
        <ol>
            <li>Vendor S2P dosyasını seçin</li>
            <li>Bileşen türünü (capacitor/inductor) belirtin</li>
            <li>"İçeri Aktar" düğmesine tıklayın</li>
        </ol>
        
        <h4>3. PDF Datasheet'ten Model (PDF'ten Model Sekmesi)</h4>
        <ol>
            <li>PDF datasheet dosyasını seçin, bileşen türünü belirtin</li>
            <li>"PDF'ten Çıkar" ile değerleri çıkarın (kapasitans, voltaj, dielektrik, kılıf)</li>
            <li>Çıkan JSON'u GÖZDEN GEÇİRİN — SRF/ESR/ESL genelde PDF'te yoktur, elle ekleyin</li>
            <li>"Model Üret" düğmesine tıklayın</li>
        </ol>
        
        <h4>JSON Parametre Dosyası Örneği (Kapasitor)</h4>
        <pre>
{
  "kind": "capacitor",
  "part_number": "GRM188R71C104",
  "capacitance_f": 1e-7,
  "esr_ohm": 0.05,
  "esl_h": 5e-10,
  "srf_hz": 6e9,
  "voltage_rating_v": 16,
  "dielectric": "X7R",
  "source": 5
}
        </pre>
        
        <h4>Açıklamalar</h4>
        <ul>
            <li><b>capacitance_f</b> - Kapasitans (Farad cinsinden)</li>
            <li><b>esr_ohm</b> - Equivalent Series Resistance</li>
            <li><b>esl_h</b> - Equivalent Series Inductance</li>
            <li><b>srf_hz</b> - Self Resonant Frequency</li>
            <li><b>source</b> - Veri kaynağı (1=ölçüm, 6=tahmini)</li>
        </ul>
        
        <h4>İçeri Aktarma Sekmesi Notları</h4>
        <p>Vendor tarafından sağlanan Touchstone dosyaları bu sekmede işlenir.
        SPICE netlist ve raporla birlikte çıktı üretilir.</p>
        """)
        layout.addWidget(help_text)
        
        tab.setLayout(layout)
        return tab
    
    # File management methods
    def add_input_files(self):
        """Add individual JSON files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "JSON Dosyası Seç", "",
            "JSON Files (*.json);;Tüm Dosyalar (*)"
        )
        for f in files:
            if f not in self.input_files:
                self.input_files.append(f)
                self.file_list.addItem(Path(f).name)
    
    def add_input_directory(self):
        """Add all JSON files from a directory."""
        directory = QFileDialog.getExistingDirectory(self, "Klasör Seç")
        if directory:
            json_files = list(Path(directory).glob("*.json"))
            for f in json_files:
                f_str = str(f)
                if f_str not in self.input_files:
                    self.input_files.append(f_str)
                    self.file_list.addItem(f.name)
    
    def remove_input_file(self):
        """Remove selected input file."""
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.takeItem(row)
            del self.input_files[row]
    
    def clear_input_files(self):
        """Clear all input files."""
        self.file_list.clear()
        self.input_files.clear()
    
    def browse_output_dir(self, line_edit=None):
        """Browse for output directory."""
        if line_edit is None:
            line_edit = self.output_dir_edit
        
        directory = QFileDialog.getExistingDirectory(self, "Çıktı Klasörü Seç")
        if directory:
            line_edit.setText(directory)

    def browse_csv_curve(self, line_edit):
        """Browse for a digitized derating-curve CSV (SimSurfing export)."""
        file, _ = QFileDialog.getOpenFileName(
            self, "Derating Eğrisi CSV Seç", "",
            "CSV Files (*.csv);;Tüm Dosyalar (*)")
        if file:
            line_edit.setText(file)
    
    def browse_s2p_file(self):
        """Browse for S2P file."""
        file, _ = QFileDialog.getOpenFileName(
            self, "S2P Dosyası Seç", "",
            "S2P Files (*.s2p);;Tüm Dosyalar (*)"
        )
        if file:
            self.import_s2p_edit.setText(file)
    
    # Processing methods
    def start_processing(self):
        """Start the processing thread."""
        if not self.input_files:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir JSON dosyası seçin!")
            return
        
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.output_log.clear()
        
        output_dir = self.output_dir_edit.text()
        dc = self.dc_bias_spin.value() or None
        tc = self.temp_spin.value()
        tc = tc if tc != 25.0 else None
        ac = self.ac_vrms_spin.value() or None
        from .derate import load_curve_csv
        dcc = self.dc_curve_edit.text().strip()
        tcc = self.tcc_curve_edit.text().strip()
        dc_curve = load_curve_csv(dcc) if dcc else None
        tcc_curve = load_curve_csv(tcc) if tcc else None
        self.worker = ProcessWorker(
            self.input_files,
            output_dir,
            self.z0_spin.value(),
            self.f_start_spin.value(),
            self.f_stop_spin.value(),
            "shunt" if self.topology_combo.currentIndex() == 1 else "series",
            dc, tc, ac, dc_curve, tcc_curve
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def on_progress(self, message):
        """Handle progress messages."""
        cursor = self.output_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_log.setTextCursor(cursor)
        self.output_log.insertPlainText(message + "\n")
    
    def on_finished(self, success, message):
        """Handle processing completion."""
        self.process_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            QMessageBox.information(self, "Başarı", message)
        else:
            QMessageBox.critical(self, "Hata", message)
    
    def start_import(self):
        """Start S2P import process."""
        s2p_file = self.import_s2p_edit.text()
        if not s2p_file or not os.path.isfile(s2p_file):
            QMessageBox.warning(self, "Uyarı", "Lütfen geçerli bir S2P dosyası seçin!")
            return
        
        try:
            from .pipeline import process_import
            
            self.import_log.clear()
            self.import_log.insertPlainText("İşlem başlıyor...\n")
            
            output_dir = self.import_out_edit.text()
            os.makedirs(output_dir, exist_ok=True)
            
            kind = self.kind_combo.currentText()
            
            self.import_log.insertPlainText(f"S2P dosyası işleniyor: {Path(s2p_file).name}\n")
            topo = "shunt" if self.import_topology_combo.currentIndex() == 1 else "series"
            s2p_path, cir_path, rep_path = process_import(s2p_file, kind, output_dir, 50.0, topo)
            
            self.import_log.insertPlainText(f"\n✓ İçeri aktarma başarılı!\n")
            self.import_log.insertPlainText(f"Çıktı: {output_dir}\n")
            
            QMessageBox.information(self, "Başarı", "S2P dosyası başarıyla içeri aktarıldı!")
            
        except Exception as e:
            self.import_log.insertPlainText(f"\n✗ Hata: {str(e)}")
            QMessageBox.critical(self, "Hata", f"İçeri aktarma hatası:\n{str(e)}")


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show GUI
    gui = S2PGui()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
