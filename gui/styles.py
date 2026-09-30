STYLES = '''
QWidget { color: #25334b; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
QMainWindow, QWidget#appSurface { background: transparent; }
QWidget#workspace { background: #f3f5f9; border-top-right-radius: 14px; border-bottom-right-radius: 14px; }
QFrame#sidebar { background: #111e36; border: none; border-top-left-radius: 14px; border-bottom-left-radius: 14px; }
QWidget#workspace[square="true"], QFrame#sidebar[square="true"] { border-radius: 0; }
QFrame#sidebar QLabel { color: #94a5bf; background: transparent; }
QFrame#sidebar QLabel#brand { color: #ffffff; font-size: 19px; font-weight: 600; }
QFrame#sidebar QLabel#sideTitle { color: #f1f5fb; font-size: 15px; font-weight: 600; }
QFrame#sidebar QLabel#sideActive { background: #26385b; color: #c4d7ff; border-radius: 9px; padding: 13px; }
QLabel#eyebrow { color: #6280ab; font-size: 11px; font-weight: 700; }
QLabel#title { font-size: 24px; font-weight: 700; color: #182844; }
QLabel#muted { color: #7c889c; }
QLabel#sectionTitle { font-size: 16px; font-weight: 700; }
QLabel#count { background: #edf2ff; color: #4b6fcb; border-radius: 11px; padding: 4px 10px; }
QLabel#dropTitle { font-size: 18px; font-weight: 600; color: #415477; }
QLabel#dropIcon { color: #6a8dee; font-size: 44px; }
QLabel#feature { color: #506886; font-size: 12px; padding: 4px 0; }
QLabel#summary { font-weight: 600; color: #426398; }
QFrame#card { background: white; border: 1px solid #e4e9f2; border-radius: 9px; }
QFrame#drop { background: #f8faff; border: 2px dashed #d1dcf0; border-radius: 12px; }
QPushButton { background: white; border: 1px solid #dce3ef; border-radius: 7px; padding: 8px 13px; min-height: 18px; font-weight: 500; }
QPushButton:hover { background: #f0f5ff; border-color: #a3b8ea; }
QPushButton:pressed { background: #e5ecfc; }
QPushButton:disabled { color: #a6afbd; background: #f5f6f8; border-color: #e7eaf0; }
QPushButton#primary { background: #3669e8; color: white; border: none; font-weight: 600; padding: 13px; }
QPushButton#primary:hover { background: #2759d6; }
QPushButton#primary:disabled { background: #aec2f2; color: white; }
QPushButton#quiet { background: transparent; color: #7b8799; border: none; padding: 7px; }
QPushButton#quiet:hover { background: #f0f3f8; color: #415675; }
QLineEdit { background: #f8faff; border: 1px solid #dce4ef; border-radius: 7px; padding: 10px; min-height: 18px; selection-background-color: #3669e8; }
QLineEdit:focus { border-color: #668ce9; }
QCheckBox { spacing: 8px; color: #53627a; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #bfcce0; border-radius: 4px; background: white; }
QCheckBox::indicator:checked { background: #3669e8; border: 3px solid #c3d3fa; }
QTableWidget { background: white; alternate-background-color: #fbfcff; border: none; gridline-color: #edf1f7; outline: none; }
QTableWidget::item { border-bottom: 1px solid #edf1f7; padding: 7px; }
QTableWidget::item:selected { background: #edf3ff; color: #25334b; }
QHeaderView::section { background: #f7f9fc; color: #8190a6; border: none; border-bottom: 1px solid #e7edf5; padding: 9px 7px; font-size: 12px; }
QTabWidget::pane { border: none; background: white; }
QTabBar::tab { color: #8894a6; background: transparent; padding: 10px 15px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #3566d4; border-bottom: 2px solid #3669e8; font-weight: 600; }
QTextBrowser, QPlainTextEdit { border: none; background: white; padding: 8px; selection-background-color: #dce8ff; }
QProgressBar { background: #edf1f8; border: none; border-radius: 4px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #3669e8; border-radius: 4px; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 1px; }
QScrollBar::handle:vertical { background: #d3ddeb; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QToolTip { background: #182844; color: white; border: none; padding: 6px; }
QComboBox { background: #f8faff; border: 1px solid #dce4ef; border-radius: 7px; padding: 8px; min-height: 18px; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: white; color: #25334b; selection-background-color: #edf3ff; selection-color: #25334b; padding: 5px; }
QScrollArea { border: none; background: transparent; }
QPushButton#navigation { background: transparent; color: #96a8c5; border: none; text-align: left; padding: 13px 12px; }
QPushButton#navigation:checked { background: #26385b; color: #dae6ff; }
QPushButton#navigation:hover { background: #1d2f4d; }
QCheckBox::indicator:indeterminate { background: #91a8d5; border: 4px solid #e1e8f5; }
QDialog { background: #f3f5f9; }
QWidget#formatPage { background: #ffffff; border-radius: 7px; }
QListWidget { background: #ffffff; border: 1px solid #e2e7ef; border-radius: 7px; outline: none; padding: 5px; }
QListWidget::item { padding: 10px 7px; border-radius: 5px; }
QListWidget::item:selected { background: #eaf0fc; color: #285ac2; }
QListWidget::item:hover { background: #f0f4fa; }
QGroupBox { border: 1px solid #e2e7ef; border-radius: 7px; margin-top: 13px; padding-top: 13px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }

QFrame#windowControls { background: transparent; border: none; }
QPushButton#windowControl, QPushButton#windowClose { border: none; border-radius: 7px; background: transparent; padding: 0; min-height: 0; }
QPushButton#windowControl:hover { background: #e3e9f2; }
QPushButton#windowClose:hover { background: #e81123; }
'''
