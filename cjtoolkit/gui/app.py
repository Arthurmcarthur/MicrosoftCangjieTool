"""PySide6 圖形介面。

流程：匯入檔案 → 驗證 → （合法才）轉換 / 安裝。

匯入可以是：
  · 純文字碼表（一行一字，倉頡碼 + 漢字）
  · 一整套二進位：spd + lex/sdc + 可選 Ext.lex（新版 ChtCangjie.* 或舊版 ChtChangjie.*）

安裝頁在非 Windows 平台停用。

執行：  cjtoolkit-gui    或    python -m cjtoolkit.gui.app
需要：  pip install "cjtoolkit[gui]"
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允許 `python cjtoolkit/gui/app.py` 直接跑（開發方便）
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "cjtoolkit.gui"

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover
    print('需要 PySide6：pip install "cjtoolkit[gui]"', file=sys.stderr)
    raise

from .. import __version__
from .. import convert as _convert
from .. import install as _install
from .. import validate as _validate

_BIN = {"spd", "lex", "ext"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"微軟倉頡碼表工具 {__version__}")
        self.resize(640, 560)

        self.files: list[Path] = []
        self.report: _validate.Report | None = None
        self.pack_dir: Path | None = None   # 可安裝的套件資料夾

        self.list = QListWidget()
        self.log = QPlainTextEdit(readOnly=True)

        add_btn = QPushButton("加入檔案…")
        add_btn.clicked.connect(self._add_files)
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear)
        self.validate_btn = QPushButton("驗證")
        self.validate_btn.clicked.connect(self._validate)

        row1 = QHBoxLayout()
        row1.addWidget(add_btn)
        row1.addWidget(clear_btn)
        row1.addWidget(self.validate_btn)
        row1.addStretch(1)

        # 純文字碼表格式（欄序 / 分隔 / 編碼）
        self.layout_box = QComboBox()
        self.layout_box.addItems(list(_convert.LAYOUTS))
        self.layout_box.setToolTip("欄序：char-code=字在左，code-char=碼在左")
        self.sep_box = QComboBox()
        self.sep_box.addItems(list(_convert.SEPARATORS))
        self.sep_box.setToolTip("分隔字元：tab / space（任意空白）")
        self.enc_box = QComboBox()
        self.enc_box.setEditable(True)
        self.enc_box.addItems(list(_convert.ENCODINGS))

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("碼表格式  欄序"))
        fmt_row.addWidget(self.layout_box)
        fmt_row.addWidget(QLabel("分隔"))
        fmt_row.addWidget(self.sep_box)
        fmt_row.addWidget(QLabel("編碼"))
        fmt_row.addWidget(self.enc_box)
        fmt_row.addStretch(1)
        self.fmt_row = fmt_row

        self.profile = QComboBox()
        self.profile.addItems(["both", "2004", "legacy"])
        self.convert_btn = QPushButton("轉換並打包")
        self.convert_btn.clicked.connect(self._convert)
        self.convert_btn.setEnabled(False)
        self.install_btn = QPushButton("安裝到微軟 IME")
        self.install_btn.clicked.connect(self._install)
        self.install_btn.setEnabled(False)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("世代"))
        row2.addWidget(self.profile)
        row2.addWidget(self.convert_btn)
        row2.addWidget(self.install_btn)
        row2.addStretch(1)

        central = QWidget()
        v = QVBoxLayout(central)
        v.addWidget(QLabel("匯入檔案（文字碼表，或 spd + lex/sdc + Ext.lex 一整套）"))
        v.addWidget(self.list)
        v.addLayout(row1)
        v.addLayout(fmt_row)
        v.addLayout(row2)
        if not _install.is_windows():
            v.addWidget(QLabel("非 Windows：可轉換打包，安裝功能停用。"))
        v.addWidget(QLabel("訊息"))
        v.addWidget(self.log)
        self.setCentralWidget(central)

    # ---- 檔案清單 ----

    def _add_files(self) -> None:
        fns, _ = QFileDialog.getOpenFileNames(
            self, "選擇檔案", "",
            "支援的檔案 (*.txt *.tsv *.spd *.lex *.sdc);;所有檔案 (*)")
        for fn in fns:
            p = Path(fn)
            if p not in self.files:
                self.files.append(p)
                self.list.addItem(str(p))
        self._reset_state()

    def _clear(self) -> None:
        self.files.clear()
        self.list.clear()
        self._reset_state()

    def _reset_state(self) -> None:
        self.report = None
        self.pack_dir = None
        self.convert_btn.setEnabled(False)
        self.install_btn.setEnabled(False)

    # ---- 驗證 ----

    def _fmt(self) -> tuple[str, str, str]:
        return (self.layout_box.currentText().strip() or "auto",
                self.sep_box.currentText().strip() or "auto",
                self.enc_box.currentText().strip() or "utf-8")

    def _validate(self) -> None:
        if not self.files:
            self._say("先加入檔案。")
            return
        layout, sep, enc = self._fmt()
        kinds = {_validate.classify(p) for p in self.files}
        try:
            if kinds & _BIN and (len(self.files) > 1 or kinds <= _BIN):
                self.report = _validate.validate_set(self.files)
            else:
                spd = next((p for p in self.files
                            if _validate.classify(p) == "spd"), None)
                self.report = _validate.validate_path(
                    self.files[0], spd=spd, layout=layout,
                    separator=sep, encoding=enc)
        except Exception as e:  # noqa: BLE001
            self._say(f"驗證時發生錯誤：{e}")
            return

        self.log.clear()
        self._say(self.report.render())
        if not self.report.ok:
            self._say("\n→ 不合法，未啟用轉換 / 安裝。")
            self.convert_btn.setEnabled(False)
            self.install_btn.setEnabled(False)
            return

        kind = self.report.kind
        if kind == "code-table":
            self.convert_btn.setEnabled(True)
            self._say("\n→ 合法。可「轉換並打包」。")
        elif kind == "set":
            # 已是一整套二進位 → 直接可安裝
            self.pack_dir = self.files[0].parent
            self.install_btn.setEnabled(_install.is_windows())
            self.convert_btn.setEnabled(True)  # 可轉成另一世代
            self._say(f"\n→ 合法。套件位於 {self.pack_dir}，可直接安裝，或轉成另一世代。")
        else:
            self._say(f"\n→ 合法（{kind}），但單一檔不成套；請補齊 spd + lex/sdc。")

    # ---- 轉換 ----

    def _convert(self) -> None:
        if self.report is None or not self.report.ok:
            return
        out = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if not out:
            return
        outdir = Path(out)
        layout, sep, enc = self._fmt()
        try:
            if self.report.kind == "code-table":
                res = _convert.convert(self.files[0], layout=layout,
                                       separator=sep, encoding=enc)
                paths = _convert.write_result(res, outdir)
                self._say(f"單字 {res.n_char}  詞組 {res.n_phrase}  "
                          f"擴充 {res.n_ext}  SPD 碼 {res.n_codes}")
                from ..cli import _cmd_pack  # 重用打包流程
                import argparse

                _cmd_pack(argparse.Namespace(
                    outdir=str(outdir), stem="cangjie", profile=self.profile.currentText()))
                self.pack_dir = outdir / "pack"
            else:
                self._say("二進位跨世代轉換尚未實作。")
                return
        except Exception as e:  # noqa: BLE001
            self._say(f"轉換失敗：{e}")
            return
        self._say(f"完成 → {self.pack_dir}")
        self.install_btn.setEnabled(_install.is_windows() and self.pack_dir.is_dir())

    # ---- 安裝 ----

    def _install(self) -> None:
        if not _install.is_windows() or self.pack_dir is None:
            return
        box = QMessageBox(self)
        box.setWindowTitle("安裝前準備")
        box.setText(_install.PRE_INSTALL_ADVICE)
        box.setInformativeText("要現在替你結束 ChtIME.exe 嗎？（系統會自動重啟）")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel)
        choice = box.exec()
        if choice == QMessageBox.StandardButton.Cancel:
            return
        if choice == QMessageBox.StandardButton.Yes:
            for m in _install.kill_cht_ime():
                self._say(m)
        # TODO: 提權 + install.apply_install（見 CLAUDE.md 待實作）
        self._say(f"TODO: 提權後安裝 {self.pack_dir} "
                  f"（profile={self.profile.currentText()}）")

    # ----

    def _say(self, text: str) -> None:
        self.log.appendPlainText(text)


def main() -> int:
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
