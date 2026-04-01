# Search Crawler

用來抓職缺站搜尋結果的 Python 爬蟲專案，目前已完成兩個 provider：`Cake` 與 `104`。

這個專案目前已經打通：

- 依關鍵字搜尋職缺
- 多頁抓取
- 結構化欄位解析
- 同步到 Google Sheets
- 以 `job_url` 去重
- 寄送人類可讀摘要信
- 額外寄送 machine-readable JSON 信

## 快速開始

### 1. 安裝

```bash
git clone https://github.com/VanessaLin9/crawler.git
cd crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 建立本地設定

```bash
cp .env.sample .env
```

然後編輯 `.env`，至少填這些：

- `GOOGLE_SHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_TO_EMAIL`

如果你要另外寄一封 JSON 格式通知給其他系統，再加：

- `MACHINE_EMAIL_ENABLED=true`
- `MACHINE_EMAIL_TO=machine-consumer@example.com`

如果你目前不需要寄信，可以先不填 `SMTP_*`。
只有在使用 `--send-email-notification` 時，才需要 SMTP 相關設定。

### `.env` 欄位說明

- `GOOGLE_SHEET_ID`: Google Sheet 的 spreadsheet ID
  可以從 Google Sheet URL 中間那段拿到
- `GOOGLE_SHEET_NAME`: 可選，自訂要寫入的工作表名稱
  如果不填，程式會依站台自動分流，例如 `cake_jobs`、`104_jobs`
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Google service account JSON 檔案路徑
  例如 `secrets/google-service-account.json`
- `SMTP_HOST`: SMTP 伺服器位址
  Gmail 通常是 `smtp.gmail.com`
- `SMTP_PORT`: SMTP port
  Gmail STARTTLS 通常是 `587`
- `SMTP_USERNAME`: SMTP 登入帳號
  通常就是寄件信箱
- `SMTP_PASSWORD`: SMTP 密碼
  如果是 Gmail，通常要填 app password，不是一般登入密碼
- `SMTP_FROM_EMAIL`: 寄件者 email
- `SMTP_TO_EMAIL`: 人類可讀摘要信的收件者
- `MACHINE_EMAIL_ENABLED`: 是否額外寄一封 JSON 通知信
- `MACHINE_EMAIL_TO`: JSON 通知信的收件者

### 3. 準備 Google Sheet

你需要：

1. 建一份 Google Sheet
2. 建立 Google service account JSON
3. 把那份 Sheet 分享給 service account email，權限給 `Editor`
4. 把 JSON 檔放到本機，例如：
   `secrets/google-service-account.json`

`.env` 對應範例：

```env
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SERVICE_ACCOUNT_JSON=secrets/google-service-account.json
```

如果你不特別指定 worksheet，程式會自動用站台名稱分流：

- `cake` -> `cake_jobs`
- `104` -> `104_jobs`

## 最常用指令

下面指令都假設你已經先：

```bash
cd /Users/vanessa/develop/search
source .venv/bin/activate
```

### 列出可用站點

```bash
crawl-site --list-sites
```

### 只爬，不更新表單、不寄信

```bash
crawl-site cake "後端"
```

也可以直接跑 104：

```bash
crawl-site 104 "後端"
```

### 爬完後同步到 Google Sheet

```bash
crawl-site cake "後端" --sync-google-sheet
```

對 `104` 也是同樣用法，預設會寫到 `104_jobs`：

```bash
crawl-site 104 "後端" --sync-google-sheet
```

### 爬完後同步到 Google Sheet，並寄通知信

```bash
crawl-site cake "後端" --sync-google-sheet --send-email-notification
```

### 強制重建 Google Sheet 後重跑

這條會清空工作表再重建，平常不要亂下：

```bash
crawl-site cake "後端" \
  --sync-google-sheet \
  --reset-google-sheet \
  --send-email-notification
```

### 換關鍵字搜尋

例如改成搜尋前端：

```bash
crawl-site cake "前端" --sync-google-sheet --send-email-notification
```

### 手動指定 worksheet

平常你不用管這個，只有你想故意寫到另一張工作表時才需要：

```bash
crawl-site 104 "後端" --sync-google-sheet --google-sheet-name my_custom_jobs
```

## 預設設定

目前集中在 [crawler/settings.py](/Users/vanessa/develop/search/crawler/settings.py)：

- `max_pages = 9`
- `per_page = 20`
- `delay_seconds = 0.5`
- `timeout_seconds = 10.0`

也就是說，預設會抓：

- 最多 `9` 頁
- 每頁 `20` 筆

如果你想暫時覆寫：

```bash
crawl-site cake "後端" --max-pages 5 --per-page 30
```

## 寄信行為

如果有加 `--send-email-notification`：

- 會先同步到 Google Sheet
- 只會寄送「這次新增的職缺」
- 如果這次沒有新職缺，就不寄信

目前支援兩種通知：

- 人類可讀摘要信
- machine-readable JSON 信

JSON 信是可選功能，預設關閉。  
開啟方式：

```env
MACHINE_EMAIL_ENABLED=true
MACHINE_EMAIL_TO=machine-consumer@example.com
```

## Google Sheet 去重規則

同步到 Google Sheets 時，會先把搜尋頁結果 flatten 成「一職缺一列」，然後用 `job_url` 去重。

所以這條：

```bash
crawl-site cake "後端" --sync-google-sheet --send-email-notification
```

在 Google Sheet 已經有相同職缺時：

- 不會重複寫入
- 不會重複寄信

只有你加上 `--reset-google-sheet`，才會整張表清掉重來。

## 目前支援的站點

- `104`
- `cake`
- `generic`

### 104

`104` 目前走搜尋頁對應的 API：

`https://www.104.com.tw/jobs/search/?keyword={keyword}`

例如：

- `後端`
- `前端`
- `python`
- `react`

### Cake

`cake` 目前針對這種搜尋頁：

`https://www.cake.me/jobs/{keyword}/for-it`

例如：

- `後端`
- `前端`
- `python`
- `react`

### Generic

`generic` 是快速模板，適合先接其他網站：

```bash
crawl-site generic "openai" \
  --search-url-template "https://example.com/search?q={keyword}" \
  --max-pages 10 \
  --output data/example.jsonl
```

## 輸出格式

原始輸出是 `.jsonl`，每一行是一頁搜尋結果，欄位大致包含：

- `url`
- `status_code`
- `title`
- `meta_description`
- `matches`
- `links`

同步到 Google Sheets 時，會轉成一職缺一列。

目前主要欄位包含：

- `job_url`
- `title`
- `company_name`
- `company_url`
- `keyword`
- `location`
- `salary_min`
- `salary_max`
- `salary_currency`
- `salary_type`
- `salary_display`
- `openings_count`
- `employment_type`
- `seniority_level`
- `experience_required_years`
- `management_responsibility`
- `tags`
- `matched_fields`
- `matched_terms`
- `summary`

## 專案結構

- `crawler/core/`: 共用抓取流程與輸出
- `crawler/sites/`: 各網站 adapter
- `crawler/sites/template.py`: 新網站模板
- `crawler/google_sheets.py`: Google Sheets 同步
- `crawler/emailer.py`: email 通知
- `crawler/settings.py`: 預設設定集中管理

## 自己擴充新網站

1. 以 [template.py](/Users/vanessa/develop/search/crawler/sites/template.py) 為基礎建立新的 adapter
2. 實作 `build_start_urls()`
3. 實作 `parse_page()`
4. 視需要調整 `should_visit()`
5. 在 [registry.py](/Users/vanessa/develop/search/crawler/sites/registry.py) 註冊站點名稱

## 注意事項

- `.env` 不會進 git
- `secrets/` 不會進 git
- `.env.sample` 只是範例，請自己填自己的 Google Sheet 和 SMTP 設定
- 如果你 clone 這個 repo 給別人用，對方必須用自己的 `.env` 和自己的 service account
