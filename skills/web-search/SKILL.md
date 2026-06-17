---
name: web-search
description: Use when a request needs web information, source-backed facts, current context, overviews, comparisons, technical documentation, monitoring, citations, or verification via SearXNG and crawl4ai.
tags: ["web", "search", "searxng", "crawl4ai", "research"]
---

# Web Search

Use this skill for universal web research with SearXNG + crawl4ai. SearXNG discovers and ranks sources. crawl4ai extracts clean content from selected pages.

Use the lightest mode that really answers the request. If existing knowledge is enough and the answer does not need current or source-backed information, answer directly instead.

## Tools

- `searxng-web_search`: discovery and ranking. Returns URLs, titles, snippets, engines, and metadata.
- `crawl4ai-md`: default extraction tool. Prefer markdown with `f: "bm25"` and `q` set to the query keywords.
- `crawl4ai-html` or `crawl4ai-execute_js`: use when markdown is empty because the page is rendered by JavaScript.
- `crawl4ai-crawl`: use for multiple pages within the same site.
- `crawl4ai-pdf`: use for PDF documents.

If these tools are unavailable, state that limitation briefly and use the best available web search or browsing tool only when the request still requires web information.

## Modes

| Mode | Use When | Width | Depth |
| --- | --- | --- | --- |
| `fast` | Fact, definition, date, number, who/when/how much | 1 SearXNG query | Snippets only by default |
| `wide` | Panorama, comparison, options, market map | 3-6 SearXNG queries | Mostly snippets; crawl 1-2 key sources if needed |
| `deep` | Precise topic, technical docs, serious verification | 1-2 targeted SearXNG queries | Crawl 3-5 strong sources |
| `deep & wide` | Report, market review, due diligence, broad monitoring | Many complementary SearXNG queries | Crawl many diverse sources by subtopic |

Depth and width are independent:

- Depth: how far to dig into each source. Low depth uses snippets. High depth crawls pages and cross-checks.
- Width: how many angles and domains to cover. Narrow width uses one query and a few sources. Wide coverage fans out across synonyms, subquestions, categories, and domains.

## Workflow

1. Choose the mode.
2. Search with SearXNG before crawling.
3. Sort results: deduplicate domains, remove off-topic pages, and keep relevant varied sources.
4. Crawl only selected article, documentation, report, or PDF pages. Do not crawl homepages unless specifically useful; they are often huge and low signal.
5. Cross-check important claims, especially dates, numbers, pricing, legal/regulatory details, product capabilities, benchmarks, and technical behavior.
6. Answer with synthesis first and citations after.

## SearXNG Defaults

Use compact, parseable output:

- `format: json` always.
- `categories: general` by default.
- `categories: news` only when dated current events matter.
- `language: all` by default.
- `time_range: day`, `week`, `month`, or `year` when freshness matters.
- `pageno` only when first-page coverage is insufficient.
- Query operators: `site:example.com`, `-site:example.com`, quoted exact phrases, and `OR`.

If results are empty and `unresponsive_engines` lists CAPTCHA or rate-limit failures, retry or vary the query before concluding that nothing exists.

## crawl4ai Defaults

Default extraction:

```json
{
  "f": "bm25",
  "q": "keywords from the query"
}
```

Use `f: "fit"` or `f: "raw"` only for short, clean pages where full content is needed. Use `f: "llm"` only when `bm25` is insufficient and the extra latency is justified.

Keep crawl outputs small. Extract relevant passages, title, final URL, date if available, and facts needed for synthesis. Do not dump raw page content into the conversation.

## Mode Details

### Fast

Run one SearXNG query with `format: json`, `categories: general`, and `language: all`. Read snippets and answer without crawling. Cross-check 2-3 snippets only when the fact is sensitive or disputed.

### Wide

Run 3-6 complementary SearXNG queries in parallel: synonyms, subquestions, alternative framings, and opposing viewpoints. Deduplicate by domain, group by angle or option, and crawl only 1-2 key sources when snippets do not settle an important point.

### Deep

Run one or two targeted queries. Add `site:` for official docs, standards, regulator pages, repositories, filings, papers, or other reference sources. Crawl 3-5 strong distinct sources with `bm25`, compare passages, keep useful exact citations, and mention disagreements.

### Deep & Wide

Use for research-grade coverage. Fan out across angles, categories, domains, and time ranges. Group results by subtopic, crawl diverse sources across those groups, and cite sources by section. If the user requests formal adversarial fact-checking or a long verified report and a `deep-research` harness is available, escalate to it.

## Output

Answer directly and keep the structure proportional to the mode:

- `fast` and `deep`: concise synthesis with sources.
- `wide`: synthesis by angle, option, or category.
- `deep & wide`: sectioned synthesis with sources per section.

Always include a `Sources` section containing only sources actually used, formatted as `[Title](URL)`. Note partial coverage when engines failed, sources diverged, or the topic is poorly documented.

## Keep Outputs Small

- Use `general` search unless dated news is required.
- Crawl with `bm25` + `q`.
- Crawl selected pages only; do not crawl every top result.
- Never send a large tool dump to another agent for parsing. If an output was written to disk, extract fields with `rg` patterns such as `"url":`, `"title":`, or `"content":`.
- Do not cite snippets as definitive when the page can be crawled and the claim matters.

## Out of Scope

- Semantic nearest-neighbor search by embeddings; SearXNG is keyword/metasearch, not semantic search.
- Web browsing for stable knowledge that can be answered without the web.
