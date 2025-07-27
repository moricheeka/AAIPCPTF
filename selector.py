
"""Prompt Selector Helper for AAIPCPTF.

Selects the most appropriate prompt blocks from `prompt_library_v1.0.md`
based on domain, category (canonical or alias), register, and free‑form tags.

Environment variables
---------------------
AAIPCPTF_PROMPT_LIBRARY   – absolute path to prompt_library_v1.0.md
AAIPCPTF_TAXONOMY_INDEX   – absolute path to taxonomy_index.json
AAIPCPTF_TAXONOMY_ALIAS   – absolute path to taxonomy_aliases.json

If the env‑vars are not set, the helper falls back to files in the
current working directory.

Typical usage
-------------
from selector import select_prompts
blocks = select_prompts(
    domain="Literary Texts",
    category="Dystopian Fiction",
    tags=["metaphor","tone"],
    top_k=2
)
print("----\n".join(blocks))
"""
from __future__ import annotations
import os, json, re, pathlib, textwrap, math
from typing import List, Dict, Any

# ---------------------------------------------------------------------#
# Utility paths
# ---------------------------------------------------------------------#
ROOT = pathlib.Path.cwd()

PROMPT_LIB_PATH  = pathlib.Path(
    os.getenv("AAIPCPTF_PROMPT_LIBRARY", ROOT / "prompt_library_v1.0.md")
)
TAXONOMY_PATH    = pathlib.Path(
    os.getenv("AAIPCPTF_TAXONOMY_INDEX", ROOT / "taxonomy_index.json")
)
ALIAS_PATH       = pathlib.Path(
    os.getenv("AAIPCPTF_TAXONOMY_ALIAS", ROOT / "taxonomy_aliases.json")
)

def _load_json(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path!s}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------#
# Load resources once (module‑level cache)
# ---------------------------------------------------------------------#
TAXONOMY: Dict[str,str] = _load_json(TAXONOMY_PATH)
ALIAS_MAP: Dict[str,str] = _load_json(ALIAS_PATH) if ALIAS_PATH.exists() else {}

# ---------------------------------------------------------------------#
# Prompt library parser
# ---------------------------------------------------------------------#
def _iter_prompt_blocks() -> List[Dict[str,Any]]:
    """Yield dicts: {meta:<dict>, body:<str>}"""
    md = PROMPT_LIB_PATH.read_text(encoding="utf‑8")
    parts = re.split(r'^---\s*$', md, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if part.startswith('{'):
            # front‑matter JSON
            try:
                meta_end = part.index('}') + 1
                meta = json.loads(part[:meta_end])
            except Exception:
                continue
            body = part[meta_end:].lstrip()
            yield {"meta": meta, "body": body}

# ---------------------------------------------------------------------#
# Normalisation helpers
# ---------------------------------------------------------------------#
def normalise_label(label: str) -> str:
    """Return canonical category path or empty string if unknown."""
    if not label:
        return ""
    key = label.lower().strip()
    # direct hit
    if key in TAXONOMY:
        return TAXONOMY[key]
    # alias hit
    if label in ALIAS_MAP:
        return ALIAS_MAP[label]
    # fuzzy: try to match last component
    for k,v in TAXONOMY.items():
        if key == v.split(' > ')[-1].lower():
            return v
    return ""

def _score(block_meta: Dict[str,Any],
           domain: str|None,
           category_path: str|None,
           tags: List[str]|None) -> float:
    """Simple linear score: 1 per match."""
    score = 0.0
    if domain and domain in (block_meta.get("domain") or []):
        score += 1
    if category_path:
        blk_cat = block_meta.get("category") or []
        # category in front‑matter may be canonical label or alias
        blk_path = normalise_label(blk_cat[0]) if blk_cat else ""
        if blk_path == category_path:
            score += 1
    if tags:
        overlap = len(set(t.lower() for t in tags)
                      & set(t.lower() for t in (block_meta.get("tags") or [])))
        score += overlap * 0.2   # 0.2 per tag overlap
    return score

# ---------------------------------------------------------------------#
# Public API
# ---------------------------------------------------------------------#
def select_prompts(domain: str|None = None,
                   category: str|None = None,
                   register: str|None = None,
                   tags: List[str]|None = None,
                   top_k: int = 1) -> List[str]:
    """Return list of prompt block strings (meta + body) with highest score."""
    category_path = normalise_label(category) if category else None
    blocks = []
    for blk in _iter_prompt_blocks():
        meta, body = blk["meta"], blk["body"]
        # Optional filter by register
        if register and meta.get("register") != register:
            continue
        score = _score(meta, domain, category_path, tags)
        if score == 0:  # early discard if no matches at all
            continue
        blocks.append((score, blk))
    # rank
    blocks.sort(key=lambda x: x[0], reverse=True)
    return [
        textwrap.dedent(f"""---
{json.dumps(b['meta'], indent=2, ensure_ascii=False)}
---
{b['body']}""")
        for score,b in blocks[:top_k]
    ]

# tiny self‑test when executed directly
if __name__ == "__main__":
    example = select_prompts(domain="Legal", category="Contract Review", top_k=1)
    print(example[0] if example else "No match")
