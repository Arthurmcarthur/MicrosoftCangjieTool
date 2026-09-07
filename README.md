# MicrosoftCangjieTool

用你自己的倉頡碼表替換 Windows 內建「微軟倉頡」的原廠碼表，並保留微軟詞庫。

微軟倉頡的原廠碼表錯訛不少，又沒有官方修正管道。這個工具讓你拿一份純文字碼表
（例如自行整理的 Cangjie 3 / Cangjie 5），轉成微軟倉頡的辭典二進位檔，直接裝進系統。

> **v2 是 Python 重寫版，開發中。**
> v1（C++/Qt，只做擴充區 `Ext.lex` 生成）保留在
> [`legacy-cpp`](../../tree/legacy-cpp) 分支，以及 `0.2.1a` 等 tag / Release。

## 能做什麼

- **轉換**：一份純文字碼表 → 微軟倉頡辭典檔（新版 `ChtCangjie.sdc` 或舊版
  `ChtChangjie.lex`，加配套 `.spd` 與擴充區 `ChtChangjieExt.lex`）。
- **併詞庫**：預設把微軟原廠詞庫（44572 詞，已從官方檔解出並內附）逐字改用你的碼、
  併進辭典，所以換碼表不會失去打詞的能力。
- **安裝**：在 Windows 上備份原檔、結束輸入法行程、把新辭典複製進系統目錄；
  失敗可從備份還原。
- **驗證**：轉換或安裝前先檢查檔案有沒有踩到會讓輸入法卡死或候選錯位的隱藏限制。
- **跨世代轉換**：新版（`sdc`）↔ 舊版（`lex`）辭典互轉。

辭典格式無公開文件，是逐位元核對官方檔 + 反組譯 `ChtChangjieDS.DLL` 得出的，
並在 Windows 實機驗證過。細節見 [`docs/format-notes.md`](docs/format-notes.md)。

## 安裝與執行

v2 還沒有打包成單一 `.exe`（規劃中）。目前從原始碼跑：

```bash
git clone https://github.com/Arthurmcarthur/MicrosoftCangjieTool.git
cd MicrosoftCangjieTool
pip install -e ".[gui]"        # 只要命令列：pip install -e .
```

之後：

```bash
cjtoolkit-gui                  # 圖形介面
cjtoolkit --help              # 命令列
```

需要 Python 3.10+；圖形介面需要 PySide6（`[gui]` 會一起裝）。
非 Windows 平台可以轉換 / 打包 / 驗證，「安裝」功能停用。

## 圖形介面

<!-- 截圖待補 -->

1. **加入檔案** —— 一份純文字碼表，或一整套辭典二進位
   （`spd` + `lex`/`sdc` + 可選 `Ext.lex`）。
2. 選**碼表格式**（欄序 / 分隔 / 編碼）—— 只在自動偵測猜錯時才要動。
3. **驗證** —— 合法才會解鎖「轉換」「安裝」。
4. 選**系統版本**（決定產出哪一代辭典），按**轉換並打包**，選輸出資料夾。
5. **安裝到微軟 IME**（僅 Windows）—— 會跳 UAC。裝前先把輸入法切成「英文（美國）」
   鍵盤或其他非微軟輸入法。

## 命令列

大多數情況只需要兩步：

```bash
# 純文字碼表 → 辭典套件（產出在 out/pack/）
cjtoolkit build cangjie.txt -o out

# 裝進系統（僅 Windows；非管理員會自動跳 UAC；--profile 預設 auto 依系統版本判定）
cjtoolkit install out/pack
cjtoolkit install out/pack --dry-run       # 先看它會做什麼，不動任何檔
```

從備份還原：

```bash
cjtoolkit uninstall "C:\Windows\System32\zh-hk\Backup_20260908-120000" --profile 2004
```

<details>
<summary>其他子命令</summary>

```bash
cjtoolkit validate cangjie.txt                              # 只驗純文字碼表
cjtoolkit validate ChtChangjie.spd ChtChangjie.lex ChtChangjieExt.lex --as-set
cjtoolkit convert cangjie.txt -o out                        # 只轉成三個文本檔（不打包）
cjtoolkit pack out --profile both                           # 三個文本檔 → 二進位
cjtoolkit transcode ChtChangjie.spd ChtChangjie.lex ChtChangjieExt.lex --to 2004 -o out
```
</details>

## 純文字碼表格式

一行一字，`#` 開頭是註解。三個維度都能指定（自動偵測失敗或猜錯時）：

| 維度 | 選項 | 說明 |
|---|---|---|
| 欄序 `--layout` | `auto` / `char-code` / `code-char` | `char-code`＝漢字在左（`日<TAB>a`）；`code-char`＝倉頡碼在左（`a<TAB>日`）|
| 分隔 `--sep` | `auto` / `tab` / `space` | `space` 吃任意空白（一個或多個空格、tab）|
| 編碼 `--encoding` | `utf-8`（預設，容忍 BOM）、`big5hkscs`、`gb18030`、任何 Python codec 名 | |

圖形介面有對應的三個下拉選單。

## 轉換規則

- 單字全用你的碼表；一字多碼時每個碼各出一條，全部可打。
- 基本區（含擴展 A、相容字）進主辭典；增補平面（擴展 B 以上）進 `Ext.lex`。
- 重碼順序 = 碼表行序。
- 詞組：預設併入內附的微軟詞庫，逐字換成你碼表的碼、保留原權重；
  `--phrases` 換自己的詞表，`--no-phrases` 全不要。

可調參數與更多細節見 [`docs/format-notes.md`](docs/format-notes.md)。

## 安裝流程與風險

`install` 做的事：

1. 非管理員 → 跳 UAC 提權。
2. 結束 `ChtIME` / `MicrosoftIME` 行程（系統會立即自動重啟，屬正常）。
3. 把原檔備份到目標目錄的 `Backup_<時間戳>\`。
4. 刪除原檔、複製新檔。
   - 新版 `C:\Windows\System32\zh-hk\`：提權即可。
   - 舊版 `C:\Windows\InputMethod\CHT\`：原檔屬 TrustedInstaller，覆寫被拒時
     自動 `takeown` / `icacls` 取得所有權再試。
5. 重啟 `ctfmon`；可能要重新選一次輸入法或登出。

**你在覆寫系統檔。** 工具每次都會先備份、`uninstall` 可還原，但仍建議先在虛擬機或
有還原點的環境試。裝前務必把輸入法整個切成「英文（美國）」鍵盤或其他**非微軟**
輸入法 —— 只把倉頡切成英文模式不會解除檔案佔用。

**Windows 版本**：Windows 10 2004（build 19041）以後與 Windows 11 用新版辭典格式，
更早的只能用舊版。`--profile auto`（預設）會自己判斷 —— 2004 以後的系統會**同時**
更新新舊兩處，因為你可能開了「使用之前版本的 Microsoft 倉頡」開關。

## 開發

```bash
pip install -e ".[dev]"
pytest
```

`cjtoolkit/codec.py` 負責所有 txt ↔ 二進位編解碼，已逐位元對齊三個官方 `.spd` 樣本；
會讓輸入法卡死或候選錯位的硬約束列在 [`docs/format-notes.md`](docs/format-notes.md)。
遠端獲取（`fetch`）模組還在，暫時未接入 CLI / GUI。

## 致謝

- [xionghuaidong](https://gitee.com/xionghuaidong) 的[微軟五筆碼表編輯器](https://gitee.com/gitwub/WubiTools) —— 介面與安裝流程的參考。
- [mrhso](https://github.com/mrhso) —— 最早以 JavaScript 讀出 lex 擴展區，釐清了該檔結構。

## 授權

MIT，見 [`LICENSE`](LICENSE)。
