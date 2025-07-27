# AAIPCPTF Module · Automated Prompt‑Synthesis & Deployment Engine  
*Version 1.0 • pinned‑commit‑placeholder*

---

## Insertion Point in the Pipeline  
**Stage:** Prompt‑Synthesis & Deployment (PSD) — immediately **after** Multi‑Tiered Hierarchical Categorisation and **before** Deep Semantic Mapping.

### Upstream Inputs  
- Completed categorisation metadata.  
- Domain‑adaptation features from iterative dual‑domain preprocessing.

### Downstream Consumers  
- Deep Semantic Mapping & Conceptual Equivalence and subsequent loops.  
- The **user‑approved prompt** produced here launches all downstream stages.

---

## Core Workflow

| Step | Actor | Action |
|------|-------|--------|
| **1** | ChatGPT‑PSD | Detect categorisation completion; load category‑specific template. |
| **2** | ChatGPT‑PSD | Populate template with category data, confidence, source attributes, domain cues, and user constraints. |
| **3** | ChatGPT‑PSD → **User** | Ask: *“Auto‑generate an optimized translation prompt for category **<X>**? (Yes / No)”* |
| **4A** | **User** | **No** → Skip PSD. |
| **4B** | **User** | **Yes** → Draft **Editable Prompt**; display for review. |
| **5** | **User** | Edit/accept; click **Approve**. |
| **6** | ChatGPT‑PSD | Record approved prompt; pass to Deep Semantic Mapping. |

---

## Template Architecture  
- **Source:** GitHub repo (raw‑URL placeholder).  
- **Parameter Slots:** `{SOURCE_LANG}`, `{TARGET_LANG}`, `{REGISTER}`, `{DOMAIN_GLOSSARY}`, `{STYLE_GUIDE}`, `{LENGTH_CONSTRAINT}`, `{ADAPTATION_FEATURES}`, …  
- **Dual‑Domain Enhancements:** Domain phrasing hints and fallback strategies.

---

## Governance & Orchestration  
- **Traceability:** Log template SHA and timestamp for every prompt.  
- **Re‑entrancy:** Allow safe re‑use if iterative loops need a refreshed prompt.  
- **User Autonomy:** Require explicit consent for draft and final prompt.  
- **Non‑Programmer Friendly:** Interaction limited to Yes/No and text edits.

---

## Outcome  
Delivers a high‑precision, context‑aware starting prompt while keeping the user in full control.

---

### End of Module


## Automated Selector Helper — production-ready

> This block wires the selector into the PSD Engine, inserts the chosen
> prompt template between `<!-- PTE_INSERT_START -->` … `<!-- PTE_INSERT_END -->`,
> and logs the operation for audit/debugging.

```python
from pathlib import Path
import json

# selector imports (already in your repo root)
from selector import select_prompts           # ranking engine
from taxonomy_utils import normalize_category # thin wrapper used by selector

# optional audit trail
from logging_utils import log_metadata_to_file

PTE_START = "<!-- PTE_INSERT_START -->"
PTE_END   = "<!-- PTE_INSERT_END -->"

def inject_selector_block(md_text: str, metadata: dict) -> str:
    """
    1. Normalise the category label with taxonomy + alias map.
    2. Pull the best prompt block from the library.
    3. Splice it between PTE markers (creates the markers if missing).
    4. Return the modified markdown string.
    """
    domain   = metadata.get("domain")                # e.g. "Marketing"
    category = normalize_category(metadata["category_label"])
    register = metadata.get("register", "default")

    prompt_block = select_prompts(domain, category, register)[0]  # top-ranked
    front_matter = "---\n" + json.dumps(prompt_block, indent=2) + "\n---"

    # ensure markers exist
    if PTE_START not in md_text:
        md_text += f"\n\n{PTE_START}\n{PTE_END}\n"

    pre, rest = md_text.split(PTE_START, 1)
    _, post   = rest.split(PTE_END,   1)
    new_md    = f"{pre}{PTE_START}\n{front_matter}\n{PTE_END}{post}"

    # audit
    metadata["inserted_prompt_id"] = prompt_block["id"]
    log_metadata_to_file(metadata, filename_prefix="pte_inject")

    return new_md


# ── Orchestrator hook example ────────────────────────────────────────────
def on_ready_to_assemble(md_path: Path, metadata: dict):
    """
    Call this once categorisation is complete and metadata is populated.
    It rewrites the markdown file *in place*.
    """
    text = md_path.read_text(encoding="utf-8")
    text = inject_selector_block(text, metadata)
    md_path.write_text(text, encoding="utf-8")
