# Search Crawler

一個可直接開始改的 Python 網頁爬蟲骨架，採用 `core + site adapters` 架構，方便同一個專案支援多個網站。

## 功能

- 共用核心流程：抓取、延遲、輸出、同網域追蹤
- 每個網站用一個 adapter 實作搜尋網址與解析規則
- 支援以關鍵字啟動搜尋流程
- 自訂最大頁數、延遲、timeout、User-Agent
- 將結果輸出成 JSON Lines
- 內含 adapter 與 URL 工具函式測試

## 環境

建議使用 Python 3.11 以上。

## 安裝

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 使用

```bash
crawl-site --list-sites
```

目前內建：

- `generic`: 適合先快速接任意搜尋頁模板
- `cake`: 針對 `https://www.cake.me/jobs/{keyword}/for-it` 的 IT 職缺搜尋頁

`generic` 用法：

```bash
crawl-site generic "openai" \
  --search-url-template "https://example.com/search?q={keyword}" \
  --max-pages 10 \
  --output data/example.jsonl
```

`cake` 用法：

```bash
crawl-site cake "python" --max-pages 3 --output data/cake-python.jsonl
```

這會從像 `https://www.cake.me/jobs/python/for-it` 這類 Cake 搜尋結果頁開始抓。

## 輸出格式

每一行都是一筆 JSON，欄位包含：

- `url`
- `status_code`
- `title`
- `meta_description`
- `matches`
- `links`

## 專案結構

- `crawler/core/`: 共用抓取流程與輸出
- `crawler/sites/`: 各網站 adapter
- `crawler/sites/template.py`: 新網站的起始模板

## 新增網站

1. 以 `crawler/sites/template.py` 為基礎建立新的 adapter
2. 實作 `build_start_urls()`
3. 實作 `parse_page()`
4. 視需要調整 `should_visit()`
5. 在 `crawler/sites/registry.py` 註冊站點名稱

## 下一步建議

- 目標網站如果依賴 JavaScript，再補 Playwright adapter
- Cake 如果要抓更細的欄位，可以再補薪資、地點、年資解析
- 如果要長期跑，再補上重試、proxy、robots.txt 與排程
