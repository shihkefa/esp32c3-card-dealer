# 逐腳接線圖

從儲存庫根目錄執行 `python V1.0.0/source/pictorial/build_pictorial.py` 可依板型與實際引腳重新產生接線圖。使用 Python 3、ReportLab、pypdf、Pillow 及 Poppler 的 pdftoppm。Windows 預設使用微軟正黑體，其他系統請將 CJK_FONT、CJK_BOLD_FONT 設為支援繁體中文的相容 TrueType 字型路徑。以 PDFTOPPM 可指定轉檔工具路徑。

`routes-cache.json` 保存現行每條線的折點，`../wiring/logical_nets.json` 保存接腳與電氣網路。產出的 PDF、SVG、PNG 與互動 HTML 位於 `../../wiring/`。
