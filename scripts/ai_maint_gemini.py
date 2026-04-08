#!/usr/bin/env python3
"""
Call Gemini from GitHub Actions: analyze Jira summary/description, write analysis + files, commit-ready.
Requires: GEMINI_API_KEY, ISSUE_KEY; optional ISSUE_SUMMARY, ISSUE_DESCRIPTION, MODE, GEMINI_MODEL.
Default model is gemini-2.5-flash (stable); override with GEMINI_MODEL / repo variable if needed.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from google import genai
from google.genai import types


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _sanitize_segment(seg: str) -> str:
    seg = seg.strip().replace("\\", "/")
    return re.sub(r"[^a-zA-Z0-9._\- ]+", "", seg).strip() or "file"


def safe_path(issue_key: str, raw: str, root: Path) -> Path | None:
    """Map model path into docs/ai-maint/<ISSUE_KEY>/... only."""
    raw = (raw or "").strip().replace("\\", "/").lstrip("/")
    if not raw or ".." in raw.split("/"):
        return None
    key_safe = _sanitize_segment(issue_key).replace(" ", "-")
    prefix = f"docs/ai-maint/{key_safe}/"
    if raw.startswith(prefix):
        rel = raw
    else:
        name = Path(raw).name
        name = _sanitize_segment(name)
        rel = f"{prefix}{name}"
    full = (root / rel).resolve()
    root_res = root.resolve()
    try:
        rel_full = full.relative_to(root_res)
    except ValueError:
        return None
    parts = rel_full.parts
    if len(parts) < 3 or parts[0] != "docs" or parts[1] != "ai-maint" or parts[2] != key_safe:
        return None
    return full


def main() -> None:
    root = Path.cwd()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    issue_key = os.environ.get("ISSUE_KEY", "").strip()
    if not issue_key:
        print("ERROR: ISSUE_KEY is not set", file=sys.stderr)
        sys.exit(1)

    summary = os.environ.get("ISSUE_SUMMARY", "")
    description = os.environ.get("ISSUE_DESCRIPTION", "")
    mode = os.environ.get("MODE", "fix")
    model_name = (os.environ.get("GEMINI_MODEL") or "").strip() or "gemini-2.5-flash"
    model_name = model_name.removeprefix("models/")

    client = genai.Client(api_key=api_key)
    gen_cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
    )

    prompt = f"""You are an automated maintenance agent for a GitHub repository.

Jira issue key: {issue_key}
Summary: {summary}
Mode: {mode}

Description (what the user wants done):
{description}

Respond with JSON only (no markdown outside JSON) using exactly this structure:
{{
  "analysis_markdown": "Markdown with sections ## Engineering, ## QA, ## PM covering approach, test ideas, and product notes.",
  "files": [
    {{ "path": "docs/ai-maint/{issue_key}/FILENAME", "content": "full file text utf-8" }}
  ]
}}

Rules:
- Every file path MUST start with docs/ai-maint/{issue_key}/ (use this exact issue key in the path).
- Use simple ASCII filenames (e.g. hello-world.txt, notes.md). Spaces in filenames are allowed if needed.
- Create the files needed to satisfy the description (e.g. if they ask for a hello world file with a name inside, create it).
- Keep file count small (typically 1–5 files).
- analysis_markdown should briefly list what you created and why.
"""

    response = None
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=gen_cfg,
        )
        raw_text = (response.text or "").strip()
        if not raw_text:
            print("ERROR: Empty Gemini response", file=sys.stderr)
            sys.exit(1)
        data = json.loads(_strip_code_fence(raw_text))
    except Exception as e:
        print(f"ERROR: Gemini call or JSON parse failed: {e}", file=sys.stderr)
        if response is not None and getattr(response, "text", None):
            print(response.text[:2000], file=sys.stderr)
        sys.exit(1)

    analysis = data.get("analysis_markdown") or "_No analysis._"
    files = data.get("files") if isinstance(data.get("files"), list) else []

    runs = root / "docs" / "ai-runs"
    runs.mkdir(parents=True, exist_ok=True)
    analysis_path = runs / f"{issue_key}-analysis.md"
    analysis_path.write_text(analysis, encoding="utf-8")

    written: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        raw_path = item.get("path", "")
        content = item.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        dest = safe_path(issue_key, raw_path, root)
        if dest is None:
            print(f"WARN: skip unsafe path {raw_path!r}", file=sys.stderr)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(str(dest.relative_to(root)))

    trace = runs / f"{issue_key}.md"
    trace.write_text(
        f"# {issue_key}\n\n**Summary:** {summary}\n\n**Gemini files:** {written}\n",
        encoding="utf-8",
    )

    print("analysis:", analysis_path.relative_to(root))
    print("files:", written)


if __name__ == "__main__":
    main()
