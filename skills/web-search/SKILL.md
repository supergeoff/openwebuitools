---
name: web-search
description: Use when a request needs information from the web (a fact, an overview, a comparison, technical documentation, monitoring, sources to cite, or a claim to verify). SearXNG discovers and ranks sources, crawl4ai extracts clean content from the selected pages, both reached through the MCP broker. Four modes cross depth and width (fast, wide, deep, deep & wide) and keep tool outputs small.
---

# Web Search: SearXNG + crawl4ai

Use this skill for every web search. SearXNG discovers and ranks sources; crawl4ai extracts
clean content from the pages worth reading. Use the lightest mode that really answers the
request. If existing knowledge is enough and the answer needs neither current nor
source-backed information, answer directly.

## Tools

Both servers sit behind the MCP broker. When a name below is not in your tool list, find it
with `search_tools` (for example `server: "searxng"`), then run it with the tool its
`run_with` names, passing the exact returned name and its parameters in `arguments`.

- `searxng-web_search`: discovery and ranking. Returns URLs, titles, snippets, engines and
  metadata. Read-only (`call_tool`).
- `crawl4ai-md`: default extraction, markdown with `f: "bm25"` and `q` set to the query
  keywords. Not flagged read-only (`call_tool_write`), which is expected for a page a search
  retained or that the user asked to read.
- `crawl4ai-html` or `crawl4ai-execute_js`: when markdown comes back empty because the page
  is rendered by JavaScript. Run `execute_js` only to read a page, never to act on it unless
  the user asked.
- `crawl4ai-crawl`: several pages of the same site.
- `crawl4ai-pdf`: a PDF document.

If these tools are unavailable, say so in one sentence. Use another web tool only when the
request still needs the web, and say which one you used and why.

## Two axes, four modes

Depth and width are independent:

- **Depth**: how far to dig into each source. Low depth reads SearXNG snippets. High depth
  crawls the pages and cross-checks them.
- **Width**: how many angles and domains to cover. Narrow width uses one query and a handful
  of sources. Wide coverage fans out across synonyms, subquestions, categories and domains.

| | Narrow | Wide |
|---|---|---|
| **Low depth** | Fast | Wide |
| **High depth** | Deep | Deep & wide |

### Fast

A fact, a definition, a date, a number, a who, when or how much.

1. One SearXNG query (`format: json`, `categories: general`, `language: all`).
2. Read the snippets and answer, without crawling.

The top snippet is usually enough. Cross-check two or three snippets when the fact is
sensitive or disputed.

### Wide

An overview, a comparison, a "what exists", a map of options.

1. Run 3 to 6 SearXNG queries in parallel from complementary angles: synonyms,
   subquestions, alternative framings, opposing viewpoints.
2. Sort the results: deduplicate by domain, drop off-topic pages, keep relevant and varied
   sources.
3. Snippets often cover the question already. Crawl one or two key sources in `bm25` only
   when an important point needs confirmation.
4. Answer with a synthesis organized by angle or option, sources cited.

Coverage matters more than the depth of each source: favor diverse domains.

### Deep

A precise topic to support seriously, technical documentation, "how exactly does it work",
a claim to verify.

1. One or two targeted SearXNG queries. Add `site:` to aim at official docs, standards,
   regulator pages, repositories, filings or papers.
2. Crawl 3 to 5 strong and distinct sources in `bm25`, with `q` set to the query keywords.
3. Cross-check the passages, note where sources disagree, keep the exact quotes that matter.
4. Answer with a precise synthesis, sources cited, and the points where sources diverge.

Reliability and precision on a narrow scope matter most.

### Deep & wide

A report, a market review, due diligence, broad monitoring of a large topic.

1. Fan out many SearXNG queries: several angles, several categories (`general`, plus `news`
   when current events matter), several `time_range` values when needed.
2. Sort and group the results by subtopic, deduplicating by domain.
3. Crawl many diverse sources in `bm25`, spread across the subtopics.
4. To parallelize the crawl, subagents may fetch and summarize batches of sources, but each
   one returns a synthesis with its citations, never the raw dump (see the rules below).
5. Answer with a synthesis organized by section, sources cited per section.

When the user wants a long, multi-source and formally verified report (adversarial
fact-checking, systematic contradiction), escalate to a `deep-research` harness if one is
available. This skill covers everything else inline.

## SearXNG parameters

- `format: json` always (bounded, parseable output).
- `categories: general` by default; `categories: news` only for dated current events.
- `language: all` by default.
- `time_range: day`, `week`, `month` or `year` when freshness matters.
- `pageno` to go past the first page when coverage is short.
- Query operators: `site:example.com` to target, `-site:example.com` to exclude, quotes for an
  exact phrase, `OR` to widen.

## crawl4ai parameters

- `crawl4ai-md` with `f: "bm25"` and `q` set to the keywords returns only the useful passages,
  a few kilobytes. It is the default extraction setting.
- Crawl **article or documentation pages**, never a homepage: a homepage in `fit` or `raw`
  can weigh 50 to 140 KB and become unmanageable.
- `f: "fit"` or `f: "raw"` only for the full content of a page already known to be short and
  clean.
- `f: "llm"` calls a model (slower): keep it for cases where `bm25` is not enough.
- A page that comes back empty in markdown is often rendered by JavaScript: try
  `crawl4ai-html` or `crawl4ai-execute_js`.

## Rules that keep outputs small

- Discover in `general` by default: the volume stays bounded and the answer arrives inline.
  `news` can return many heavy and noisy results, so keep it for dated events.
- Crawl in `bm25` with `q`, on article or documentation pages.
- Keep discovery and extraction separate: crawl a few chosen sources, not the whole top of the
  list.
- Never hand a tool result to a subagent for parsing. When an output is too large and was
  written to disk, extract it with grep or ripgrep on the file (patterns such as `"url":`,
  `"title":`, `"content":`) instead of reading it whole.
- Do not cite a snippet as definitive when the page can be crawled and the claim matters.

## Robustness

- Engines fail intermittently with a CAPTCHA or "too many requests", listed in
  `unresponsive_engines`. When `results` is empty while engines are unavailable, retry or vary
  the query before concluding that nothing exists.
- Several queries in parallel widen coverage and smooth over these failures.
- Few sources expose a reliable date in their snippets: cross-check when freshness matters.

## Answer

- A direct synthesis that answers the request, structured by mode: flat for fast and deep, by
  angle or section for wide and deep & wide.
- A **Sources** section with `[Title](URL)` for each source actually used.
- Flag partial coverage: engines down, a poorly documented topic, sources that disagree.

## Out of scope

- Knowledge available without the web: answer directly.
- Semantic nearest-neighbor search by embeddings: SearXNG is keyword metasearch, not semantic
  search.
