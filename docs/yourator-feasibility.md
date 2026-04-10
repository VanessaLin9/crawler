# Yourator Feasibility Check

Date: 2026-04-08

## Summary

Yourator is feasible as the next provider, but there are two implementation paths with different tradeoffs:

1. Category/list-based adapter via `GET /api/v4/jobs`
2. Keyword-search adapter via `GET /api/v3/search?s=...`

The first path is more stable and fits the current crawler architecture better because it is paginated and returns normalized job cards. The second path supports free-text keyword search, but current probing suggests it returns a small fixed result set and does not expose obvious pagination.

## What Was Verified

### Public crawling surface

- `https://www.yourator.co/robots.txt` is public.
- Current robots rules only disallow `/r/*`.
- Public job detail pages are accessible without login.

### Public list API

- `GET https://www.yourator.co/api/v4/jobs`
- Response includes:
  - `payload.currentPage`
  - `payload.nextPage`
  - `payload.hasMore`
  - `payload.jobs`
- Each job includes stable structured fields:
  - `id`
  - `name`
  - `path`
  - `salary`
  - `location`
  - `tags`
  - `lastActiveAt`
  - `company.brand`
  - `company.enName`
  - `company.badges`
  - `thirdPartyUrl`

### Public search API

- `GET https://www.yourator.co/api/v3/search?s=backend`
- Response includes:
  - `jobs`
  - `companies`
  - `articles`
- Job entries are richer than the v4 list API:
  - `content`
  - `salary`
  - `category`
  - `company.brand`
  - `company.enName`

### Detail-page fallback

- Job detail HTML pages expose structured data in the page source.
- The page contains:
  - title and description meta tags
  - "最近更新於"
  - "工作內容"
  - "條件要求"
  - "薪資範圍"
  - embedded JSON for recommended jobs

This means we can parse job detail pages if we need fields that the list API does not provide.

## Main Findings

### 1. Best low-risk path: use `/api/v4/jobs`

This is the strongest signal that Yourator is feasible:

- open access
- structured JSON
- explicit pagination
- stable per-job `path`

For a first provider version, this is the safest foundation.

Example job URL can be built as:

- `https://www.yourator.co{path}`

Example:

- `/companies/linkst/jobs/46716`

### 2. Keyword support is the main uncertainty

Direct keyword probing against `/api/v4/jobs` did not show an obvious working free-text parameter:

- `keyword=backend` looked ignored
- `s=backend` looked ignored
- several guessed area/category variants were inconsistent or ignored

By contrast, `/api/v3/search?s=backend` clearly works for keyword search, but:

- `page=2` looked ignored
- `size=20` looked ignored
- response shape looks like a top-result search surface, not a crawl-all paginated listing

Current inference:

- free-text keyword search is available
- but crawl depth for keyword search is probably capped unless we find another internal endpoint or reproduce front-end filter behavior more precisely

### 3. Data completeness is good enough for V1

Using the two surfaces together, we can likely fill most crawler fields:

- `title`: yes
- `company_name`: yes
- `job_url`: yes
- `salary_display`: yes
- `tags`: yes
- `location`: yes
- `content_updated_at`: yes, from detail page
- `summary`: yes, from search API or detail-page meta/content

Potentially missing in V1 unless we add detail-page parsing:

- normalized salary min/max/type
- detailed requirement sections
- richer description summary from the list API path alone

## Recommendation

### Recommended V1

Build a Yourator adapter on top of `GET /api/v4/jobs` first.

Scope it as:

- paginated list crawl
- public detail-page parsing when extra fields are needed
- keyword handling limited to known mapped categories at first if necessary

Suggested initial mapping:

- `後端` -> job category `23`
- `前端` -> job category `22`
- `全端` -> job category `24`
- `DevOps` / `SRE` -> job category `28`
- `資料` / `ML` / `AI` -> job categories `29`, `47`, `48`, `49`, `50`

This would let us ship a useful provider even if arbitrary free-text keyword parity is not ready yet.

### Not recommended for V1

Do not build the first version purely on `/api/v3/search`.

Reason:

- it supports keyword search
- but current probing does not show pagination or size control
- it may be better as a supplement for summaries, not the crawl backbone

## Risk Notes

- Some jobs carry `thirdPartyUrl` or `externalSource`; we should decide whether canonical `job_url` should be the Yourator page or the third-party apply link.
- Some filters on `/api/v4/jobs` are still unclear; bundle inspection shows the endpoint is query-driven, but parameter names are not fully mapped yet.
- Detail-page parsing is feasible, but HTML structure could be noisier than the JSON APIs.

## Suggested Next Step

If we want to move forward now, the next practical step is:

1. scaffold `crawler/sites/yourator.py`
2. use `/api/v4/jobs?page=N` as the primary crawl source
3. add a small keyword-to-category mapping for the first supported searches
4. parse job detail pages only for fields missing from the list API

If we want better keyword parity before coding, the next research step is:

1. capture the exact front-end query object passed into `/api/v4/jobs`
2. map real filter parameter names from the running jobs UI
3. verify whether any hidden keyword-capable jobs endpoint exists beyond `/api/v3/search`
