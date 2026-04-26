#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import urlparse

import requests
import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BRANCH = "main"
GITHUB_API = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"
HTTP_TIMEOUT = 30  # seconds, per request

# Extension -> fence language. Anything not listed gets an empty fence info.
FENCE_LANG = {
    ".py": "python",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".jsonc": "jsonc",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".env": "dotenv",
    ".md": "markdown",
    ".rst": "rst",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".lua": "lua",
    ".vim": "vim",
    ".dockerfile": "dockerfile",
    ".tf": "hcl",
    ".hcl": "hcl",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".proto": "protobuf",
    ".csv": "csv",
    ".tsv": "tsv",
    ".xml": "xml",
    ".txt": "",
}

# Files we never want in the flatten (lockfiles, vendored deps, etc.)
SKIP_FILE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock", "poetry.lock"}
SKIP_DIR_PARTS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("deploy-skills")


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class GHTarget:
    """A resolved (owner, repo, ref, path) pointer into GitHub.

    path is a directory containing SKILL.md (possibly empty for repo root,
    in which case discovery walks the top-level dirs).
    """

    owner: str
    repo: str
    ref: str
    path: str  # posix-style, no leading slash; '' = repo root
    is_root_discovery: bool = False  # True when caller wants children walk


@dataclass
class SkillBundle:
    """Everything we need to build the flattened markdown for one skill."""

    source_url: str  # for logging / traceability
    target: GHTarget
    skill_md: str  # raw text of SKILL.md
    assets: list[tuple[str, str]] = field(default_factory=list)  # (relpath, text)


# ---------------------------------------------------------------------------
# GitHub HTTP helpers
# ---------------------------------------------------------------------------


def _gh_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "deploy-skills/1.0"
    s.headers["Accept"] = "application/vnd.github+json"
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def _raw_url(t: GHTarget, relpath: str) -> str:
    base = f"{RAW_BASE}/{t.owner}/{t.repo}/{t.ref}"
    rel = relpath.lstrip("/")
    if t.path:
        return f"{base}/{t.path}/{rel}" if rel else f"{base}/{t.path}"
    return f"{base}/{rel}" if rel else base


def _fetch_raw(session: requests.Session, url: str) -> bytes | None:
    log.debug("GET %s", url)
    r = session.get(url, timeout=HTTP_TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


def _list_contents(session: requests.Session, t: GHTarget) -> list[dict]:
    """List entries at t.path in repo, at ref. Returns list of GitHub content dicts."""
    api = f"{GITHUB_API}/repos/{t.owner}/{t.repo}/contents"
    if t.path:
        api = f"{api}/{t.path}"
    log.debug("GET %s?ref=%s", api, t.ref)
    r = session.get(api, params={"ref": t.ref}, timeout=HTTP_TIMEOUT)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        # single file response, normalize to list
        return [data]
    return data


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

_RE_REPO_ROOT = re.compile(r"^/([^/]+)/([^/]+)/?$")
_RE_TREE = re.compile(r"^/([^/]+)/([^/]+)/tree/([^/]+)(?:/(.*))?/?$")
_RE_BLOB = re.compile(r"^/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$")


def parse_url(url: str) -> GHTarget:
    """Parse one of the 4 supported GitHub URL shapes into a GHTarget.

    Raises ValueError on anything we don't understand.
    """
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme: {url}")

    host = p.netloc.lower()
    path = p.path.rstrip("/")

    # raw.githubusercontent.com/owner/repo/ref/.../SKILL.md
    if host in ("raw.githubusercontent.com", "raw.github.com"):
        parts = path.lstrip("/").split("/")
        if len(parts) < 4:
            raise ValueError(f"raw URL missing components: {url}")
        owner, repo, ref, *rest = parts
        rel = "/".join(rest)
        # Caller wants the directory containing the file, not the file itself
        rel_dir = str(PurePosixPath(rel).parent) if rel else ""
        if rel_dir == ".":
            rel_dir = ""
        return GHTarget(owner=owner, repo=repo, ref=ref, path=rel_dir)

    if host != "github.com":
        raise ValueError(f"unsupported host: {host}")

    # github.com/owner/repo
    m = _RE_REPO_ROOT.match(path + "/")
    if m:
        owner, repo = m.group(1), m.group(2)
        return GHTarget(owner=owner, repo=repo, ref=DEFAULT_BRANCH, path="", is_root_discovery=True)

    # github.com/owner/repo/tree/<ref>/<path?>
    m = _RE_TREE.match(path)
    if m:
        owner, repo, ref, sub = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        return GHTarget(owner=owner, repo=repo, ref=ref, path=sub)

    # github.com/owner/repo/blob/<ref>/<path-to-file>
    m = _RE_BLOB.match(path)
    if m:
        owner, repo, ref, sub = m.group(1), m.group(2), m.group(3), m.group(4)
        rel_dir = str(PurePosixPath(sub).parent)
        if rel_dir == ".":
            rel_dir = ""
        return GHTarget(owner=owner, repo=repo, ref=ref, path=rel_dir)

    raise ValueError(f"unrecognized GitHub URL shape: {url}")


# ---------------------------------------------------------------------------
# Resolve a manifest URL into one or more skill targets
# ---------------------------------------------------------------------------


def resolve_targets(session: requests.Session, t: GHTarget) -> list[GHTarget]:
    """Expand a parsed URL into 1+ concrete skill directories.

    A skill directory is one that contains SKILL.md at its root.

    Strategy:
        - If t already points at a dir with SKILL.md, return [t].
        - Else walk children one level and keep those that have SKILL.md.
          (matches Fu-Jie's "auto-discovery" behavior)
    """
    skill_md_url = _raw_url(t, "SKILL.md")
    log.debug("Probing SKILL.md at %s", skill_md_url)
    head = session.head(skill_md_url, timeout=HTTP_TIMEOUT, allow_redirects=True)
    if head.status_code == 200:
        return [t]

    # Not a single skill -> try discovery
    entries = _list_contents(session, t)
    children: list[GHTarget] = []
    for e in entries:
        if e.get("type") != "dir":
            continue
        name = e.get("name") or ""
        if not name or name.startswith("."):
            continue
        sub_path = f"{t.path}/{name}" if t.path else name
        sub = GHTarget(owner=t.owner, repo=t.repo, ref=t.ref, path=sub_path)
        # cheap probe
        probe = session.head(_raw_url(sub, "SKILL.md"), timeout=HTTP_TIMEOUT, allow_redirects=True)
        if probe.status_code == 200:
            children.append(sub)
        else:
            log.debug("skip %s/%s: no SKILL.md", t.path or t.repo, name)
    return children


# ---------------------------------------------------------------------------
# Fetch the bundle (SKILL.md + textual assets) for one skill target
# ---------------------------------------------------------------------------


def _walk_files(session: requests.Session, t: GHTarget) -> Iterable[tuple[str, str]]:
    """Yield (relative_path, raw_url) for every file under t (recursively).

    Uses the GitHub trees API for efficiency on large skills (xlsx skill ships
    a `scripts/` dir with several files).

    On API failure (rate limit, auth, transient) yields nothing and logs a
    warning — the caller still gets SKILL.md from the raw CDN, so the skill
    installs without its assets rather than failing entirely. Set GITHUB_TOKEN
    to lift the 60/h anonymous limit to 5000/h.
    """
    api_ref = f"{GITHUB_API}/repos/{t.owner}/{t.repo}/git/trees/{t.ref}?recursive=1"
    try:
        r = session.get(api_ref, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning(
            "trees API failed for %s/%s@%s (%s); installing SKILL.md only, "
            "no assets. Set GITHUB_TOKEN to fix.",
            t.owner, t.repo, t.ref, e,
        )
        return
    data = r.json()
    if data.get("truncated"):
        log.warning("repo %s/%s tree truncated; some files may be missed", t.owner, t.repo)

    prefix = (t.path + "/") if t.path else ""
    for entry in data.get("tree", []):
        if entry.get("type") != "blob":
            continue
        full = entry["path"]
        if prefix and not full.startswith(prefix):
            continue
        rel = full[len(prefix):] if prefix else full

        # filter
        parts = rel.split("/")
        if any(p in SKIP_DIR_PARTS for p in parts[:-1]):
            continue
        if parts[-1] in SKIP_FILE_NAMES:
            continue

        yield rel, _raw_url(t, rel)


def fetch_bundle(session: requests.Session, t: GHTarget, source_url: str) -> SkillBundle | None:
    skill_md_bytes = _fetch_raw(session, _raw_url(t, "SKILL.md"))
    if skill_md_bytes is None:
        log.error("[%s] no SKILL.md at %s", source_url, _raw_url(t, "SKILL.md"))
        return None
    try:
        skill_md = skill_md_bytes.decode("utf-8")
    except UnicodeDecodeError:
        log.error("[%s] SKILL.md is not UTF-8", source_url)
        return None

    bundle = SkillBundle(source_url=source_url, target=t, skill_md=skill_md)

    # Walk every other file
    for rel, url in _walk_files(session, t):
        if rel == "SKILL.md":
            continue
        raw = _fetch_raw(session, url)
        if raw is None:
            log.debug("missed asset %s", url)
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            log.debug("skip binary asset %s", rel)
            continue
        bundle.assets.append((rel, text))

    bundle.assets.sort(key=lambda x: x[0])
    return bundle


# ---------------------------------------------------------------------------
# Frontmatter parsing (just enough to find the skill name)
# ---------------------------------------------------------------------------


def parse_frontmatter(md: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). If no frontmatter, returns ({}, md)."""
    if not md.startswith("---"):
        return {}, md
    # Find the closing ---
    lines = md.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, md
    fm_text = "\n".join(lines[1:end])
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        log.warning("invalid YAML frontmatter: %s", e)
        return {}, md
    if not isinstance(fm, dict):
        return {}, md
    body = "\n".join(lines[end + 1:])
    return fm, body


# ---------------------------------------------------------------------------
# Slug + flatten
# ---------------------------------------------------------------------------


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "skill"


def fence_lang_for(relpath: str) -> str:
    name = PurePosixPath(relpath).name.lower()
    if name == "dockerfile":
        return "dockerfile"
    suffix = PurePosixPath(relpath).suffix.lower()
    return FENCE_LANG.get(suffix, "")


def _safe_fence(text: str) -> str:
    """Pick a fence length that doesn't clash with any backtick run inside text."""
    longest = 0
    for m in re.finditer(r"`+", text):
        longest = max(longest, len(m.group(0)))
    return "`" * max(3, longest + 1)


def flatten(bundle: SkillBundle) -> str:
    """Build the single-blob markdown that becomes Skill.content."""
    parts: list[str] = []
    parts.append(bundle.skill_md.rstrip())

    if bundle.assets:
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("## Skill assets")
        parts.append("")
        parts.append(
            f"_The following files ship alongside `SKILL.md` in "
            f"`{bundle.target.owner}/{bundle.target.repo}` "
            f"(ref `{bundle.target.ref}`, path `{bundle.target.path or '/'}`)._"
        )
        for relpath, text in sorted(bundle.assets, key=lambda x: x[0]):
            lang = fence_lang_for(relpath)
            fence = _safe_fence(text)
            parts.append("")
            parts.append(f"### `{relpath}`")
            parts.append("")
            parts.append(f"<!-- path: {relpath} -->")
            parts.append(f"{fence}{lang}")
            parts.append(text.rstrip("\n"))
            parts.append(fence)

    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Skill identity (what we send to OpenWebUI)
# ---------------------------------------------------------------------------


@dataclass
class SkillPayload:
    id: str
    name: str
    description: str | None
    content: str
    tags: list[str]


def build_payload(bundle: SkillBundle) -> SkillPayload | None:
    fm, _ = parse_frontmatter(bundle.skill_md)
    name = (fm.get("name") or fm.get("title") or "").strip()
    if not name:
        log.error(
            "[%s] SKILL.md frontmatter has no `name` (or `title`); cannot derive id",
            bundle.source_url,
        )
        return None
    sid = slugify(name)
    description = fm.get("description")
    if description is not None:
        description = str(description).strip()

    tags = fm.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t) for t in tags]

    content = flatten(bundle)
    return SkillPayload(id=sid, name=name, description=description, content=content, tags=tags)


# ---------------------------------------------------------------------------
# OpenWebUI client
# ---------------------------------------------------------------------------


class OpenWebUI:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {api_key}"
        self.s.headers["Accept"] = "application/json"
        self.s.headers["User-Agent"] = "deploy-skills/1.0"

    def list_skills(self) -> list[dict]:
        url = f"{self.base}/api/v1/skills/"
        r = self.s.get(url, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def create(self, payload: SkillPayload) -> dict:
        url = f"{self.base}/api/v1/skills/create"
        body = {
            "id": payload.id,
            "name": payload.name,
            "description": payload.description,
            "content": payload.content,
            "meta": {"tags": payload.tags},
            "is_active": True,
        }
        r = self.s.post(url, json=body, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def update(self, sid: str, payload: SkillPayload) -> dict:
        url = f"{self.base}/api/v1/skills/id/{sid}/update"
        body = {
            "id": sid,
            "name": payload.name,
            "description": payload.description,
            "content": payload.content,
            "meta": {"tags": payload.tags},
            "is_active": True,
        }
        r = self.s.post(url, json=body, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()


def upsert(client: OpenWebUI, payload: SkillPayload, existing_ids: set[str]) -> str:
    """Returns 'created' or 'updated'."""
    if payload.id in existing_ids:
        client.update(payload.id, payload)
        return "updated"
    try:
        client.create(payload)
        existing_ids.add(payload.id)
        return "created"
    except requests.HTTPError as e:
        # Race: id was created between our list and our create. Fall back to update.
        if e.response is not None and e.response.status_code == 400:
            client.update(payload.id, payload)
            existing_ids.add(payload.id)
            return "updated"
        raise


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def load_manifest(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    skills = data.get("skills") or []
    if not isinstance(skills, list):
        raise ValueError(f"{path}: 'skills' must be a list of URLs")
    return [str(s).strip() for s in skills if str(s).strip()]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Deploy SKILL.md-style skills from a manifest into OpenWebUI.",
    )   
    ap.add_argument(
        "-m", "--manifest",
        default="skills/manifest.yaml",
        help="path to manifest yaml (default: skills/manifest.yaml)",
    )
    ap.add_argument("--dry-run", action="store_true", help="do everything except the OpenWebUI write")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument(
        "--print-payload",
        action="store_true",
        help="with --dry-run, print each skill's flattened content to stdout",
    )
    args = ap.parse_args()
    setup_logging(args.verbose)

    base = os.environ.get("OPENWEBUI_URL")
    key = os.environ.get("OPENWEBUI_API_KEY")
    if not args.dry_run and (not base or not key):
        log.error("OPENWEBUI_URL and OPENWEBUI_API_KEY must be set (or use --dry-run)")
        return 2

    try:
        urls = load_manifest(args.manifest)
    except (OSError, ValueError, yaml.YAMLError) as e:
        log.error("manifest: %s", e)
        return 2
    log.info("manifest: %d entries", len(urls))

    gh = _gh_session()

    # 1. Resolve manifest URLs -> concrete skill targets
    targets: list[tuple[str, GHTarget]] = []  # (source_url, target)
    for url in urls:
        try:
            parsed = parse_url(url)
        except ValueError as e:
            log.error("[%s] %s", url, e)
            continue
        try:
            resolved = resolve_targets(gh, parsed)
        except requests.RequestException as e:
            log.error("[%s] resolve failed: %s", url, e)
            continue
        if not resolved:
            log.error("[%s] no SKILL.md found (and no children with SKILL.md)", url)
            continue
        for t in resolved:
            targets.append((url, t))
            log.info("resolved %s -> %s/%s@%s:%s", url, t.owner, t.repo, t.ref, t.path or "/")

    # 2. Fetch + flatten + build payload
    payloads: list[SkillPayload] = []
    for source_url, t in targets:
        try:
            bundle = fetch_bundle(gh, t, source_url)
        except requests.RequestException as e:
            log.error("[%s] fetch failed: %s", source_url, e)
            continue
        if bundle is None:
            continue
        payload = build_payload(bundle)
        if payload is None:
            continue
        log.info(
            "built payload id=%s name=%r assets=%d size=%d",
            payload.id, payload.name, len(bundle.assets), len(payload.content),
        )
        payloads.append(payload)

    if not payloads:
        log.error("nothing to upsert")
        return 1

    # 3. Upsert
    if args.dry_run:
        for p in payloads:
            log.info("[dry-run] would upsert id=%s name=%r", p.id, p.name)
            if args.print_payload:
                print(f"\n===== {p.id} =====\n{p.content}\n===== end {p.id} =====\n")
        return 0

    client = OpenWebUI(base, key)
    try:
        existing = client.list_skills()
    except requests.RequestException as e:
        log.error("OpenWebUI list failed: %s", e)
        return 1
    existing_ids = {s["id"] for s in existing}
    log.info("OpenWebUI: %d existing skills", len(existing_ids))

    succeeded: list[str] = []
    failed: list[str] = []
    for p in payloads:
        try:
            action = upsert(client, p, existing_ids)
            log.info("%-7s %s (%s)", action, p.id, p.name)
            succeeded.append(p.id)
        except requests.HTTPError as e:
            body = e.response.text if e.response is not None else ""
            log.error("upsert failed for %s: %s %s", p.id, e, body[:200])
            failed.append(p.id)
        except requests.RequestException as e:
            log.error("upsert failed for %s: %s", p.id, e)
            failed.append(p.id)

    log.info("done: %d ok, %d failed", len(succeeded), len(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())