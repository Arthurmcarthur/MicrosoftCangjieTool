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
# 下載碼表
cjtoolkit fetch https://example.com/cangjie.txt -o cangjie.txt

# txt 碼表 → 二進位套件（兩代都產）
cjtoolkit build cangjie.txt --phrases ms-phrases.tsv -o out --profile both

# 只轉文本 / 只打包
cjtoolkit convert cangjie.txt -o out
cjtoolkit pack out --profile both

# 安裝（僅 Windows，需系統管理員）
cjtoolkit install out/pack --profile both --kill-ime
```

碼表格式：一行一字，倉頡碼與漢字以 TAB 或空格分隔，UTF-8。
欄位順序自動偵測（`--layout char-code | code-char` 可強制）。

### 圖形介面

```
cjtoolkit-gui
```

非 Windows 平台可轉換 / 打包，「安裝」頁停用。

## 轉換規則

- 單字全用你的碼表；一字多碼時每個碼各出一條，全部可打。
- 基本區（含擴展 A、相容字）進主辭典；增補平面（擴展 B 以上）進 `Ext.lex`。
- 重碼順序 = 碼表行序。
- 詞組（`--phrases`）沿用微軟詞表，逐字換成你碼表的碼，保留原權重。

細節與可調參數見 [`docs/format-notes.md`](docs/format-notes.md)。

## 致謝

- [xionghuaidong](https://gitee.com/xionghuaidong) 的[微軟五筆碼表編輯器](https://gitee.com/gitwub/WubiTools) —— 介面與安裝流程的參考。
- [mrhso](https://github.com/mrhso) —— 最早以 JavaScript 讀出 lex 擴展區，釐清了該檔結構。

## 授權

MIT
