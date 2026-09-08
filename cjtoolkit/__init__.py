"""cjtoolkit —— 微軟倉頡碼表工具（v2，Python 重寫）。

子模組：
    codec    txt/二進位 ↔ ChtChangjie.lex / ChtCangjie.sdc / .spd / Ext.lex
             （vendored，來源 microsoft_cangjie/ime_codec.py，逐位元驗證過官方檔）
    convert  一份 txt 碼表 → 三檔文本（lex / spd / ext）
    validate 檢查匯入的文字碼表 / 二進位是否合法（對應 docs/format-notes.md 硬約束）
    install  部署到 Windows IME 目錄（僅 Windows）
    cli      命令列入口
    gui      PySide6 圖形介面（安裝頁在非 Windows 停用）
    fetch    從 URL / GitHub raw 取得 txt（暫未接入 CLI/GUI）
"""

__version__ = "2.0.0"
