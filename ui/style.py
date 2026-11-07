"""Ultra-modern dark aesthetic stylesheet for KesCollah.
Custom palette: Deep Obsidian (#0B0D14), Midnight Surfaces (#141824),
Neon Teal (#00E5FF / #00B4D8), and Electric Purple (#8B5CF6 / #A855F7).
"""

KESCOLLAH_QSS = """
/* Base Global Settings */
QWidget {
    background-color: #0B0D14;
    color: #E2E8F0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Inter", Roboto, sans-serif;
    font-size: 13px;
    selection-background-color: #00B4D8;
    selection-color: #0B0D14;
}

QMainWindow {
    background-color: #0B0D14;
}

/* Card Surfaces */
QFrame#cardFrame, QWidget#cardWidget {
    background-color: #131722;
    border: 1px solid #1F2637;
    border-radius: 10px;
}

QFrame#elevatedCard {
    background-color: #181D2B;
    border: 1px solid #283248;
    border-radius: 10px;
}

/* Typography */
QLabel {
    background: transparent;
}
QLabel#appTitle {
    font-size: 20px;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 0.5px;
}
QLabel#appSubtitle {
    font-size: 11px;
    color: #00E5FF;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QLabel#viewTitle {
    font-size: 18px;
    font-weight: 700;
    color: #F8FAFC;
}
QLabel#viewSubtitle {
    font-size: 12px;
    color: #94A3B8;
}
QLabel#statNumber {
    font-size: 22px;
    font-weight: 800;
    color: #00E5FF;
}
QLabel#statLabel {
    font-size: 11px;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
}
QLabel#badgeTeal {
    background-color: #083344;
    color: #38BDF8;
    border: 1px solid #0284C7;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#badgePurple {
    background-color: #2E1065;
    color: #C084FC;
    border: 1px solid #7E22CE;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#badgeEmerald {
    background-color: #064E3B;
    color: #34D399;
    border: 1px solid #059669;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#badgeRose {
    background-color: #4C0519;
    color: #FB7185;
    border: 1px solid #E11D48;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}

/* Inputs & Spinners */
QLineEdit, QSpinBox {
    background-color: #10131B;
    border: 1px solid #232B3E;
    border-radius: 6px;
    padding: 7px 12px;
    color: #F8FAFC;
    font-size: 13px;
}
QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #00E5FF;
    background-color: #141924;
}

/* Base Buttons */
QPushButton {
    background-color: #1A202E;
    border: 1px solid #283247;
    border-radius: 7px;
    padding: 8px 16px;
    color: #E2E8F0;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #232B3D;
    border-color: #3B4863;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #141924;
}
QPushButton:disabled {
    background-color: #10131B;
    border-color: #1A202C;
    color: #475569;
}

/* Teal Accent Primary Button */
QPushButton#primaryButton {
    background-color: #00B4D8;
    border: 1px solid #00E5FF;
    color: #0B0D14;
    font-weight: 700;
}
QPushButton#primaryButton:hover {
    background-color: #00E5FF;
    border-color: #70F2FF;
}
QPushButton#primaryButton:pressed {
    background-color: #0096B4;
}

/* Purple Accent Button */
QPushButton#purpleButton {
    background-color: #7C3AED;
    border: 1px solid #8B5CF6;
    color: #FFFFFF;
    font-weight: 700;
}
QPushButton#purpleButton:hover {
    background-color: #8B5CF6;
    border-color: #A78BFA;
}
QPushButton#purpleButton:pressed {
    background-color: #6D28D9;
}

/* Emerald Success Button */
QPushButton#successButton {
    background-color: #059669;
    border: 1px solid #10B981;
    color: #FFFFFF;
    font-weight: 700;
}
QPushButton#successButton:hover {
    background-color: #10B981;
    border-color: #34D399;
}
QPushButton#successButton:pressed {
    background-color: #047857;
}

/* Danger / Undo Button */
QPushButton#dangerButton {
    background-color: #9F1239;
    border: 1px solid #E11D48;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#dangerButton:hover {
    background-color: #BE123C;
    border-color: #FB7185;
}

/* Checkbox */
QCheckBox {
    spacing: 8px;
    color: #CBD5E1;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #2B354C;
    border-radius: 4px;
    background-color: #10131B;
}
QCheckBox::indicator:hover {
    border-color: #00E5FF;
}
QCheckBox::indicator:checked {
    background-color: #00B4D8;
    border-color: #00E5FF;
}

/* Tables */
QTableWidget {
    background-color: #10131B;
    border: 1px solid #1F2637;
    border-radius: 8px;
    gridline-color: #1A202E;
    color: #E2E8F0;
    outline: none;
}
QTableWidget::item {
    padding: 7px 10px;
    border-bottom: 1px solid #181D29;
}
QTableWidget::item:hover {
    background-color: #19202E;
}
QTableWidget::item:selected {
    background-color: #212B3E;
    color: #FFFFFF;
}
QHeaderView::section {
    background-color: #141824;
    color: #94A3B8;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #222B3D;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #0E1119;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #263045;
    min-height: 25px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background-color: #00B4D8;
}
QScrollBar:horizontal {
    border: none;
    background-color: #0E1119;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background-color: #263045;
    min-width: 25px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #00B4D8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    height: 0px;
}

/* Progress Bar */
QProgressBar {
    background-color: #10131B;
    border: 1px solid #202738;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 700;
    height: 14px;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00B4D8, stop:1 #8B5CF6);
    border-radius: 5px;
}

/* Status Bar */
QStatusBar {
    background-color: #0E1119;
    border-top: 1px solid #1A202E;
    color: #94A3B8;
    font-size: 12px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #1F2637;
    background-color: #131722;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    background-color: #0E121B;
    color: #94A3B8;
    border: 1px solid #1F2637;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    margin-right: 4px;
}
QTabBar::tab:hover {
    background-color: #181E2C;
    color: #F8FAFC;
}
QTabBar::tab:selected {
    background-color: #131722;
    color: #00E5FF;
    border-bottom: 2px solid #00E5FF;
}

/* List Widgets */
QListWidget {
    background-color: #10131B;
    border: 1px solid #1F2637;
    border-radius: 8px;
    color: #E2E8F0;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 2px;
}
QListWidget::item:hover {
    background-color: #19202E;
}
QListWidget::item:selected {
    background-color: #212B3E;
    color: #00E5FF;
    font-weight: 700;
}

/* Console Logs */
QPlainTextEdit {
    background-color: #0D1017;
    border: 1px solid #1F2637;
    border-radius: 8px;
    color: #CBD5E1;
    font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 12px;
    padding: 10px;
}
"""
