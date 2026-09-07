# 微軟倉頡辭典格式與硬約束

微軟倉頡辭典是三檔成套，由 `ChtChangjieDS.DLL` 一起 mmap 載入。格式無公開文件，
以下由 DLL 反組譯 + 逐位元核對官方檔得出，並在 Windows 實機驗證。

| 檔 | 舊版（`%windir%\InputMethod\CHT\`） | 新版（`%windir%\System32\zh-hk\`） |
|---|---|---|
| 辭典本體 | `ChtChangjie.lex` L_count=8，最長 8 字 | `ChtCangjie.sdc` L_count=5，最長 5 字 |
| 合法碼表 | `ChtChangjie.spd` | `ChtCangjie.spd`（與舊版 bytes 相同）|
| 擴充字 | `ChtChangjieExt.lex` | `ChtCangjieExt.lex`（同上）|

## 硬約束（違反 → 卡死 / 候選錯位 / 打不出）

1. **SPD TRIE 格式**：`"TRIE"(4) + size(4) + 20-byte subheader + N×12-byte nodes`
   （0-based，node 0 = root）。node：`+0 u32 leaf<<16`、`+4 u32 (term<<31)|child_base`、
   `+8 u16 n_children`、`+10 u16 letter`。n_children==26 → dense 直接索引；<26 → sparse
   二分。實際相異子字母 ≥14 → dense。node 配置順序 = preorder DFS。size = `8+20+N*12`。
   `cjtoolkit.codec.build_spd_trie` 逐位元對齊 3 個官方 `.spd` 樣本。

2. **lex 權重必須 < 2^24（16,777,216）**。官方 72,176 條全部 < 2^24（max 14,958,243）。
   超過 → DLL 把 uint32 高位元組另作他用 → 候選錯位、選字上屏錯字、該候選不出現。
   `convert.py` 用 `weight = 14,000,000 - 行號`（> 詞組 max ~1.076e7 且 < 2^24）。

3. **SPD 相異碼上限 65,535**（TRIE leaf 是 16-bit）。Ext.lex 的碼是字面字串、
   不進 SPD，不受此限。

4. **Ext.lex 記錄必須依小寫 code 升冪排序**（DLL 二分搜尋找字）。
   `codec.encode_ext` 已強制穩定排序（同 code 保留輸入順序 = 重碼順序）。

5. `--profile 2004` 會丟掉 > 5 codepoint 的詞。**不影響 SPD**：SPD 只收單字碼，
   單字不會因長度被濾；詞組逐字碼 ⊆ 單字碼。

## 跨世代轉換（`transcode`）

一整套二進位（spd + lex/sdc + 可選 Ext.lex）→ 另一世代：decode（用配套 spd
查 spell index）→ 針對目標 profile 重新 `encode_lex`（max_len/force_lcount 不同）
→ 配套 spd / Ext.lex 直接重編（byte-exact，Ext.lex 時間戳沿用來源）。

**legacy → 2004 會丟 > 5 字的詞**（官方樣本 120 條）；反向轉回來不會復原，
所以別把 2004 當中繼。

## 輸入純文字碼表格式

一行一字，`#` 開頭為註解。三個維度可由使用者指定（`parse_code_table` /
CLI `--layout/--sep/--encoding` / GUI 下拉）：

- **欄序** `auto | char-code | code-char`：`char-code`＝漢字在左，`code-char`＝碼在左。
  `auto` 看前 200 行投票（哪一欄整欄是 ASCII 字母就是碼）。
- **分隔** `auto | tab | space`：`space` = `str.split()`（任意空白）。
  `auto` = 有 tab 用 tab，否則任意空白。
- **編碼**：任何 Python codec 名；`utf-8` 會自動改用 `utf-8-sig` 容忍 BOM。

## 轉換規則（`convert.py` 預設，可調參數）

- 單字全用輸入碼表的碼。一字多碼：每個碼各出一條（全部可打）。
- BMP（含 Ext-A U+3400–4DBF、相容字 U+F900–FAFF）→ 主 lex；增補平面 → Ext.lex。
- Ext-A 放主 lex＝免開 CJK 擴充開關就能打（貼近微軟原廠）。`--ext-a-separate` 可改。
- 重碼順序 = 碼表行序（單字 weight 遞減）。
- 詞組（`--phrases`）逐字改用碼表該字第一個碼，沿用原權重，一律排在單字後。
- Ext.lex flags：big5-hkscs 專有 → 6，其餘 → 2。

## 安裝（`install.py`）

流程：UAC 提權 → 結束 `ChtIME`/`MicrosoftIME` → 備份 → 刪除+複製 → 重啟 `ctfmon`。

- **新版 `C:\Windows\System32\zh-hk`：提權即可**（`apply_install` 直接刪+複製）。
- **舊版 `C:\Windows\InputMethod\CHT`：原檔屬 TrustedInstaller**，覆寫被拒時
  自動 `takeown /f` + `icacls /grant %USERNAME%:F` 再試（`needs_ownership=True`）。
- 提權：非管理員時用 `run_elevated()`（`ShellExecuteExW "runas"`）開一個管理員
  子行程跑 `python -m cjtoolkit install … --_child`，**不重跑呼叫者本身**。
  從原始碼跑時要把 `source_cwd()`（含 `cjtoolkit/` 的資料夾）當子行程工作目錄，
  否則 `-m cjtoolkit` 找不到模組。`relaunch_as_admin()` 仍在但別用在會壞的情境。
- 只結束 `ChtIME`（鎖檔的是它）；**不動 ctfmon**——殺了語言列會壞、又難乾淨還原。
- **版本判定**：`windows_build()`（`sys.getwindowsversion().build`）。
  build ≥ 19041＝Win10 2004＝支援新版格式；< 19041 只能裝 legacy。
  `--profile auto`（CLI 預設）/ GUI「自動判定」：
  · < 19041 → 只裝 legacy
  · ≥ 19041 → **同時裝 2004 + legacy**，因為使用者可能在 IME 設定開了
    「使用之前版本的 Microsoft 倉頡」，那樣會改讀 legacy 路徑，只更新 2004 沒效果。
    （沒找到可靠的登錄機碼判斷該開關，所以一律兩處都更新，最穩。）
  不支援的 profile 會被跳過，`--force` 才強制。
- 備份預設寫到 `<目標目錄>\Backup_<時間戳>\`；`restore()` / CLI `uninstall` 可還原。
- **2026-09-07 VM 實測（管理員終端）：2004 碼表成功替換、備份正常**。
  即使沒先切走輸入法也成功，但仍要求使用者先切成「英文（美國）」鍵盤或其他
  **非微軟**的輸入法（只把倉頡切英文模式沒用；速成等共用同一框架也會鎖檔）。
- 2026-09-07 legacy（`InputMethod\CHT`）也在 VM 實測成功：覆寫被拒 → takeown
  目錄+檔案 → 成功替換。
- 參考 Eden5Wu/Windows-Cangjie-Updater（PowerShell）：只做 2004、不取得所有權。
