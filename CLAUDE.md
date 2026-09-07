# MicrosoftCangjieTool v2

微軟倉頡碼表工具。v1 是 C++/Qt（0.1.1a–0.2.1a，只做 Ext.lex 生成），
v2 用 Python 重寫，範圍擴大為：**txt 碼表 → 完整二進位套件、遠端獲取、安裝**。
v1 程式碼保留在 `legacy-cpp` 分支與 `0.2.1a` 等 tag。

## 結構

```
cjtoolkit/
  codec.py      vendored：txt/二進位 ↔ lex/sdc/spd/Ext.lex。逐位元驗證過官方檔。
                來源 = ../microsoft_cangjie/ime_codec.py（改那邊要同步回來，或反過來以此為主）
  convert.py    一份 txt 碼表 → 三檔文本（lex/spd/ext）。移植自 build_tables.py
  fetch.py      URL → txt（純 urllib，github blob→raw 自動轉）
  install.py    部署到 Windows IME 目錄；非 Windows raise PlatformError
  cli.py        fetch / convert / pack / build / install / codec
  gui/app.py    PySide6；安裝頁在非 Windows 停用
```

## 二進位格式硬約束（踩過坑，務必遵守）

微軟倉頡辭典是三檔成套，由 `ChtChangjieDS.DLL` 一起 mmap 載入：

| 檔 | 舊版（`%windir%\InputMethod\Cht\`） | 新版（`%windir%\System32\zh-hk\`） |
|---|---|---|
| 辭典本體 | `ChtChangjie.lex` L_count=8, 最長 8 字 | `ChtCangjie.sdc` L_count=5, 最長 5 字 |
| 合法碼表 | `ChtChangjie.spd` | `ChtCangjie.spd`（與舊版 bytes 相同）|
| 擴充字 | `ChtChangjieExt.lex` | `ChtCangjieExt.lex`（同上）|

1. **SPD TRIE 格式**：`"TRIE"(4) + size(4) + 20-byte subheader + N×12-byte nodes`
   （0-based，node 0 = root）。node：`+0 u32 leaf<<16`、`+4 u32 (term<<31)|child_base`、
   `+8 u16 n_children`、`+10 u16 letter`。n_children==26 → dense 直接索引；<26 → sparse
   二分。實際相異子字母 ≥14 → dense。node 配置順序 = preorder DFS。size = `8+20+N*12`。
   **舊版 `build_spd_trie` 格式全錯（40-byte subheader、1-based、無 root）→ 非官方碼集匯入後輸入法卡死。**
   codec.py 已修，逐位元對上 3 個官方 spd。

2. **lex 權重必須 < 2^24（16,777,216）**。官方 72,176 條全部 < 2^24（max 14,958,243）。
   超過 → DLL 把高位元組另作他用 → 候選錯位、選字上屏錯字、該候選不出現。
   convert.py 用 `weight = 14,000,000 - 行號`（高於詞組 max ~1.076e7，且 < 2^24）。

3. **SPD 相異碼上限 65,535**（TRIE leaf 是 16-bit）。Ext.lex 的碼是字面字串、不進 SPD，不受此限。

4. **Ext.lex 記錄必須依小寫 code 升冪排序**（DLL 二分搜尋找字）。
   `codec.encode_ext` 已強制穩定排序（同 code 保留輸入順序 = 重碼順序）。

5. `--profile 2004` 會丟掉 > 5 codepoint 的詞。**不影響 SPD**：SPD 只收單字碼，
   單字不會因長度被濾；詞組逐字碼 ⊆ 單字碼。

以上第 2、4 點已在 Windows 實機驗證修好（2026-09）。

## 轉換規則（convert.py 預設，可調參數）

- 單字全用輸入碼表的碼。一字多碼：每個碼各出一條（全部可打）。
- BMP（含 Ext-A U+3400–4DBF、相容字 U+F900–FAFF）→ 主 lex；增補平面 → Ext.lex。
- Ext-A 放主 lex＝免開 CJK 擴充開關就能打（貼近微軟原廠）。`--ext-a-separate` 可改。
- 重碼順序 = 碼表行序（單字 weight 遞減）。
- 詞組（`--phrases`）逐字改用碼表該字第一個碼，沿用原權重，一律排在單字後。
- Ext.lex flags：big5-hkscs 專有 → 6，其餘 → 2。

## 安裝（install.py，待完成）

- **舊版 `C:\Windows\InputMethod\CHT`：需提權 + 取得所有權**
  （原檔屬 TrustedInstaller，`takeown /f` + `icacls /grant`，或
  `MoveFileEx(..., MOVEFILE_DELAY_UNTIL_REBOOT)`）。
- **新版 `C:\Windows\System32\zh-hk`：只要提權即可**（不必取得所有權）。
- **安裝前**：彈窗（GUI）／提示（CLI）請使用者先把輸入法切到英文，
  再結束 `ChtIME.exe`（`install.kill_cht_ime()`，系統會自動重啟）。
  否則碼表檔正被 IME 佔用，無法覆寫。
- IME 使用中檔案可能被鎖；安裝後需登出/重啟輸入法。
- 一律先備份原檔。
- 非 Windows：CLI `install` 回傳 2，GUI 安裝頁 disabled。

## 開發

- `pip install -e ".[dev]"`；`pytest`
- GUI：`pip install -e ".[gui]"` 後 `cjtoolkit-gui`
- Windows 打包：Nuitka → 單一 `.exe`（AV 誤報比 PyInstaller 少）
