# MicrosoftCangjieTool

微軟倉頡碼表工具：把一份純文字碼表轉成微軟倉頡的辭典檔
（`ChtChangjie.lex` / `ChtCangjie.sdc` + 配套 `.spd` + `ChtChangjieExt.lex`），
可從遠端獲取碼表，並在 Windows 上直接安裝。

> **v2 是 Python 重寫版**（開發中）。v1 的 C++/Qt 版本（只做 Ext.lex 生成）
> 保留在 [`legacy-cpp`](../../tree/legacy-cpp) 分支與 `0.2.1a` 等 tag / Release。

## 為什麼

微軟倉頡原廠碼表錯訛甚多。這個工具讓你用自己整理的碼表（例如 Cangjie 3 / 5）
覆蓋原廠碼表，且保留微軟的詞庫。

微軟把辭典拆成三個互相耦合的二進位檔，格式無公開文件、且有數個會讓輸入法
**卡死或候選錯位**的隱藏約束。本工具的 `codec` 已逐位元對齊三個官方 `.spd`
樣本，並在 Windows 實機驗證過那些約束（詳見 [`docs/format-notes.md`](docs/format-notes.md)）。

## 安裝

```
pip install cjtoolkit                 # 命令列
pip install "cjtoolkit[gui]"          # 附 PySide6 圖形介面
```

## 用法

### 命令列

```bash
# 檢查檔案合不合法（文字碼表，或一整套二進位）
cjtoolkit validate cangjie.txt
cjtoolkit validate ChtChangjie.lex ChtChangjie.spd ChtChangjieExt.lex --as-set

# txt 碼表 → 二進位套件（兩代都產）
cjtoolkit build cangjie.txt --phrases ms-phrases.tsv -o out --profile both

# 只轉文本 / 只打包
cjtoolkit convert cangjie.txt -o out
cjtoolkit pack out --profile both

# 已是一整套二進位 → 轉成另一世代（新舊互轉）
cjtoolkit transcode ChtChangjie.spd ChtChangjie.lex ChtChangjieExt.lex --to 2004 -o out

# 安裝（僅 Windows；非管理員會自動跳 UAC；--profile 預設 auto 依系統版本判定）
cjtoolkit install out/pack
cjtoolkit install out/pack --dry-run          # 先看會做什麼
cjtoolkit uninstall "C:\Windows\System32\zh-hk\Backup_20260907-120000" --profile 2004
```

安裝流程：提權 → 結束 `ChtIME`/`MicrosoftIME` → 備份原檔到目標目錄的
`Backup_<時間戳>\` → 刪除+複製 → 重啟 `ctfmon`。
`legacy`（`InputMethod\CHT`）原檔屬 TrustedInstaller，覆寫失敗時自動 `takeown`/`icacls`。

### 純文字碼表格式

一行一字。三個維度都可指定（自動偵測失敗或猜錯時）：

| 維度 | 選項 | 說明 |
|---|---|---|
| 欄序 `--layout` | `auto` / `char-code` / `code-char` | `char-code`＝漢字在左（`日<TAB>a`）；`code-char`＝倉頡碼在左（`a<TAB>日`）|
| 分隔 `--sep` | `auto` / `tab` / `space` | `space` 吃任意空白（單／多個空格或 tab）|
| 編碼 `--encoding` | `utf-8`（預設，自動容忍 BOM）/ `big5hkscs` / `gb18030` / 任何 Python codec 名 | |

`#` 開頭的行視為註解。GUI 有對應的三個下拉選單。

驗證會檢查 [`docs/format-notes.md`](docs/format-notes.md) 列出的硬約束
（權重 < 2^24、SPD 相異碼 ≤ 65535、Ext.lex 排序、SPD TRIE 格式等）。
合法才允許轉換或安裝。遠端獲取（`fetch`）暫時隱藏。

### 圖形介面

```
cjtoolkit-gui
```

非 Windows 平台可轉換 / 打包，「安裝」頁停用。

## 轉換規則

- 單字全用你的碼表；一字多碼時每個碼各出一條，全部可打。
- 基本區（含擴展 A、相容字）進主辭典；增補平面（擴展 B 以上）進 `Ext.lex`。
- 重碼順序 = 碼表行序。
- 詞組：預設併入內附的微軟詞庫（44572 詞，自官方 `ChtChangjie.lex` 解出），
  逐字換成你碼表的碼、保留原權重；`--phrases` 換自己的詞表，`--no-phrases` 全不要。

細節與可調參數見 [`docs/format-notes.md`](docs/format-notes.md)。

## 致謝

- [xionghuaidong](https://gitee.com/xionghuaidong) 的[微軟五筆碼表編輯器](https://gitee.com/gitwub/WubiTools) —— 介面與安裝流程的參考。
- [mrhso](https://github.com/mrhso) —— 最早以 JavaScript 讀出 lex 擴展區，釐清了該檔結構。

## 授權

MIT
