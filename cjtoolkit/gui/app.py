"""PySide6 圖形介面（骨架）。

三頁：來源（本地檔 / URL）→ 轉換設定 → 產出/安裝。
安裝頁在非 Windows 平台停用（見 install.is_windows）。

執行：  python -m cjtoolkit.gui.app    或    cjtoolkit-gui
需要：  pip install "cjtoolkit[gui]"
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover
    print('需要 PySide6：pip install "cjtoolkit[gui]"', file=sys.stderr)
    raise

from .. import __version__, convert as _convert
from .. import install as _install


class SourceTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        self.path = QLineEdit()
        self.path.setPlaceholderText("本地 txt 碼表路徑，或貼上 URL")
        browse = QPushButton("選擇檔案…")
        browse.clicked.connect(self._browse)
        lay.addWidget(QLabel("碼表來源"))
        lay.addWidget(self.path)
        lay.addWidget(browse)
        lay.addStretch(1)

    def _browse(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "選擇碼表", "", "文字檔 (*.txt);;所有檔案 (*)")
        if fn:
            self.path.setText(fn)


class ConvertTab(QWidget):
    def __init__(self, source: SourceTab, log: QPlainTextEdit) -> None:
        super().__init__()
        self.source = source
        self.log = log
        lay = QVBoxLayout(self)
        self.phrases = QLineEdit()
        self.phrases.setPlaceholderText("微軟詞表 TSV（可選）")
        run = QPushButton("轉換並打包")
        run.clicked.connect(self._run)
        lay.addWidget(QLabel("詞組來源（可選）"))
        lay.addWidget(self.phrases)
        lay.addWidget(run)
        lay.addStretch(1)

    def _run(self) -> None:
        table = Path(self.source.path.text().strip())
        if not table.exists():
            self.log.appendPlainText(f"找不到檔案：{table}（URL 下載尚未接上 GUI）")
            return
        try:
            res = _convert.convert(
                table,
                phrases=Path(self.phrases.text()) if self.phrases.text().strip() else None,
            )
        except Exception as e:  # noqa: BLE001
            self.log.appendPlainText(f"轉換失敗：{e}")
            return
        self.log.appendPlainText(
            f"單字 {res.n_char}  詞組 {res.n_phrase}  擴充 {res.n_ext}  SPD 碼 {res.n_codes}"
        )
        # TODO: 選輸出資料夾、呼叫 pack、把結果交給安裝頁


class InstallTab(QWidget):
    def __init__(self, log: QPlainTextEdit) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        if not _install.is_windows():
            lay.addWidget(QLabel("安裝功能僅限 Windows。\n"
                                 "在此平台請用「轉換並打包」產生檔案，再複製到目標機器。"))
            lay.addStretch(1)
            self.setEnabled(False)
            return
        self.log = log
        btn = QPushButton("安裝到微軟 IME 目錄（需系統管理員）")
        btn.clicked.connect(self._install)
        lay.addWidget(btn)
        if not _install.is_admin():
            lay.addWidget(QLabel("⚠ 目前非管理員，安裝會失敗。"))
        lay.addStretch(1)

    def _install(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("安裝前準備")
        box.setText(_install.PRE_INSTALL_ADVICE)
        box.setInformativeText("要現在替你結束 ChtIME.exe 嗎？（系統會自動重啟它）")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        choice = box.exec()
        if choice == QMessageBox.StandardButton.Cancel:
            return
        if choice == QMessageBox.StandardButton.Yes:
            for m in _install.kill_cht_ime():
                self.log.appendPlainText(m)
        # TODO: 選 pack 資料夾 + profile，提權後呼叫 install.apply_install
        self.log.appendPlainText("TODO: 提權 + install.apply_install")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"微軟倉頡碼表工具 {__version__}")
        self.resize(560, 460)

        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setPlaceholderText("訊息")

        source = SourceTab()
        tabs = QTabWidget()
        tabs.addTab(source, "來源")
        tabs.addTab(ConvertTab(source, log), "轉換")
        tabs.addTab(InstallTab(log), "安裝")

        central = QWidget()
        v = QVBoxLayout(central)
        v.addWidget(tabs)
        v.addWidget(QLabel("記錄"))
        v.addWidget(log)
        self.setCentralWidget(central)


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
