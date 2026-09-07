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

import os
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
        QCheckBox,
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
        for value, label in (("auto", "自動"),
                             ("char-code", "先字符後編碼"),
                             ("code-char", "先編碼後字符")):
            self.layout_box.addItem(label, value)
        self.sep_box = QComboBox()
        for value, label in (("auto", "自動"),
                             ("tab", "Tab（定位字元）"),
                             ("space", "空格")):
            self.sep_box.addItem(label, value)
        self.enc_box = QComboBox()
        self.enc_box.setEditable(True)
        for value, label in (("utf-8", "UTF-8"), ("utf-8-sig", "UTF-8（含 BOM）"),
                             ("utf-16", "UTF-16"), ("gb18030", "GB18030"),
                             ("big5hkscs", "Big5-HKSCS"), ("big5", "Big5")):
            self.enc_box.addItem(label, value)

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
        _auto_label = "自動判定"
        if _install.is_windows():
            _auto_label += f"（{_install.windows_name()}）"
        for value, label in (
            ("auto", _auto_label),
            ("2004", "Windows 10 2004 及以後，或 Windows 11"),
            ("legacy", "Windows 10 2004 以前"),
            ("both", "兩者皆要"),
        ):
            self.profile.addItem(label, value)
        self.phrases_box = QCheckBox("併入微軟詞庫（44572 詞）")
        self.phrases_box.setChecked(_convert.bundled_phrases().exists())
        self.phrases_box.setEnabled(_convert.bundled_phrases().exists())
        self.convert_btn = QPushButton("轉換並打包")
        self.convert_btn.clicked.connect(self._convert)
        self.convert_btn.setEnabled(False)
        self.install_btn = QPushButton("安裝到微軟 IME")
        self.install_btn.clicked.connect(self._install)
        self.install_btn.setEnabled(False)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("系統版本"))
        row2.addWidget(self.profile)
        row2.addWidget(self.convert_btn)
        row2.addWidget(self.install_btn)
        row2.addStretch(1)
        row3 = QHBoxLayout()
        row3.addWidget(self.phrases_box)
        row3.addStretch(1)

        central = QWidget()
        v = QVBoxLayout(central)
        v.addWidget(QLabel("匯入檔案（文字碼表，或 spd + lex/sdc + Ext.lex 一整套）"))
        v.addWidget(self.list)
        v.addLayout(row1)
        v.addLayout(fmt_row)
        v.addLayout(row2)
        v.addLayout(row3)
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

    @staticmethod
    def _combo(box, fallback: str) -> str:
        """回傳選項的內部值（addItem 的 userData）；可編輯欄自行輸入時用文字。"""
        data = box.currentData()
        if data:
            return str(data)
        text = box.currentText().strip()
        return text or fallback

    def _fmt(self) -> tuple[str, str, str]:
        return (self._combo(self.layout_box, "auto"),
                self._combo(self.sep_box, "auto"),
                self._combo(self.enc_box, "utf-8"))

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

    def _target(self) -> str:
        """要產出哪些世代：auto → 兩套（安裝時再挑）；其餘照選。"""
        v = self.profile.currentData()
        return "both" if v == "auto" else v

    def _convert(self) -> None:
        if self.report is None or not self.report.ok:
            return
        out = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if not out:
            return
        outdir = Path(out)
        target = self._target()
        layout, sep, enc = self._fmt()
        self._say(f"產出世代：{target}")
        try:
            if self.report.kind == "code-table":
                phrases = (_convert.bundled_phrases()
                           if self.phrases_box.isChecked() else None)
                res = _convert.convert(self.files[0], layout=layout,
                                       separator=sep, encoding=enc, phrases=phrases)
                paths = _convert.write_result(res, outdir)
                self._say(f"單字 {res.n_char}  詞組 {res.n_phrase}  "
                          f"擴充 {res.n_ext}  SPD 碼 {res.n_codes}")
                from ..cli import _cmd_pack  # 重用打包流程
                import argparse

                _cmd_pack(argparse.Namespace(
                    outdir=str(outdir), stem="cangjie", profile=target))
                self.pack_dir = outdir / "pack"
            else:  # kind == "set"：已是一整套二進位 → 轉成另一世代
                packdir = outdir / "pack"
                res = _convert.transcode_set(self.files, packdir, target=target)
                self._say(f"詞條 {res.n_entries}  SPD 碼 {res.n_codes}  "
                          f"擴充 {res.n_ext}")
                for prof, n in res.dropped.items():
                    if n:
                        self._say(f"  {prof}：丟掉 {n} 條過長的詞")
                self.pack_dir = packdir
        except Exception as e:  # noqa: BLE001
            self._say(f"轉換失敗：{e}")
            return
        self._say(f"完成 → {self.pack_dir}")
        self.install_btn.setEnabled(_install.is_windows() and self.pack_dir.is_dir())

    # ---- 安裝 ----

    def _install(self) -> None:
        if not _install.is_windows() or self.pack_dir is None:
            return
        profile = self.profile.currentData()
        profiles = _install.resolve_profiles(profile)
        if profile == "auto":
            self._say(f"系統版本 {_install.windows_name()} → 安裝 {' + '.join(profiles)}")
            if len(profiles) > 1:
                self._say("（同時更新新舊兩處，以防你開了「使用之前版本的 Microsoft 倉頡」）")

        # 版本防禦：系統不支援的 profile 直接擋下
        blocked = [(p, why) for p in profiles
                   for ok, why in [_install.profile_supported(p)] if not ok]
        if blocked:
            supported = [p for p in profiles if p not in dict(blocked)]
            msg = "\n".join(why for _, why in blocked)
            if not supported:
                QMessageBox.critical(self, "系統版本不支援", msg)
                return
            r = QMessageBox.question(
                self, "部分不支援",
                f"{msg}\n\n仍要安裝其餘（{' + '.join(supported)}）嗎？")
            if r != QMessageBox.StandardButton.Yes:
                return
            profiles = supported

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("安裝前確認")
        box.setText(
            f"即將把 {' + '.join(profiles)} 碼表寫入系統目錄。\n"
            "原檔會先備份到目標目錄的 Backup_<時間戳>。")
        box.setInformativeText(_install.PRE_INSTALL_ADVICE)
        cb = QCheckBox("我已切換成「英文（美國）」鍵盤或其他非微軟的輸入法")
        box.setCheckBox(cb)
        box.setStandardButtons(QMessageBox.StandardButton.Ok
                               | QMessageBox.StandardButton.Cancel)
        box.button(QMessageBox.StandardButton.Ok).setText("開始安裝")
        if box.exec() != QMessageBox.StandardButton.Ok:
            return
        if not cb.isChecked():
            QMessageBox.warning(
                self, "尚未切換輸入法",
                "請把輸入法切換成「英文（美國）」鍵盤或其他非微軟的輸入法。\n"
                "請勿簡單將微軟倉頡切換到英文模式，這種做法無法解除佔用。\n"
                "勾選確認後再按「開始安裝」。")
            return

        if _install.is_admin():
            # 已是管理員：直接跑，不必再開子行程
            self._say("執行安裝（目前已是管理員）…")
            QApplication.processEvents()
            try:
                msgs = _install.full_install(self.pack_dir, profiles)
            except Exception as e:  # noqa: BLE001
                self._say(f"安裝失敗：{e}")
                return
            for m in msgs:
                self._say(m)
            return

        # 非管理員：只提權跑 install 子命令（不重開整個 GUI），輸出回收到暫存檔
        import tempfile

        log_path = Path(tempfile.gettempdir()) / f"cjtoolkit-install-{os.getpid()}.log"
        log_path.unlink(missing_ok=True)
        pchoice = "both" if len(profiles) == 2 else profiles[0]
        argv = _install.worker_argv() + [
            "install", str(self.pack_dir),
            "--profile", pchoice, "--yes", "--no-elevate",
            "--log", str(log_path),
        ]

        self._say("UAC 提權中，請在提示視窗按「是」…")
        QApplication.processEvents()
        try:
            rc = _install.run_elevated(argv, cwd=_install.source_cwd(),
                                       show=True, wait=True)
        except OSError as e:
            self._say(f"提權或執行失敗：{e}")
            return

        if log_path.exists():
            self._say(log_path.read_text(encoding="utf-8").rstrip())
            log_path.unlink(missing_ok=True)
        else:
            self._say("（沒有收到安裝輸出；可能被取消）")
        self._say(f"安裝行程結束，代碼 {rc}。可能需要重新選一次輸入法或登出。")

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
