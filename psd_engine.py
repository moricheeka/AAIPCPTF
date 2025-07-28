"""
psd_engine.py – AAIPCPTF Prompt-Synthesis & Deployment Engine
5th Pass: Supreme Flexibility, Modularization, AAIPCPTF/ChatGPT Hyper-Compatibility

Placement: This file (and all referenced files) must reside in the branch-root: AAIPCPTF/tree/main/
No code or data subfolders. No relative or package imports except for optional logging utilities.

Key Features:
- Universal prompt library source: file (from main branch-root), in-memory dict, callback, or string.
- Pluggable rendering: Python .format(), Jinja2, or user-defined backend (auto-detect).
- Flexible logging: auto-selects AAIPCPTF logging_utils, OpenAI logger, or standard Python logger.
- Hot reload, dynamic runtime context injection, user callback hooks, alias/normalization for all AAIPCPTF/ChatGPT stage names.
- Ready for “invisible” system prompt orchestration, LLM workflows, and human-in-the-loop scripting.

Ultra-extensible and future-proof.
"""

import os
import re
import json
from typing import Any, Dict, List, Optional, Tuple, Callable, Union

try:
    from jinja2 import Template as JinjaTemplate, meta as jinja_meta
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

def get_logger(user_logger: Optional[Any] = None) -> Any:
    if user_logger:
        return user_logger
    try:
        from logging_utils import logger  # expects logging_utils.py in AAIPCPTF/tree/main/
        return logger
    except Exception:
        import logging
        logger = logging.getLogger("PSD_ENGINE")
        if not logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        logger.setLevel(logging.INFO)
        return logger

class PromptLibrarySource:
    """
    Flexible prompt library source: supports branch-root file, in-memory, callback, or dict.
    """
    def __init__(
        self,
        source: Optional[Union[str, Callable[[], str], Dict[str, Any]]] = None,
        logger: Optional[Any] = None,
    ):
        self.logger = get_logger(logger)
        self.source = source
        self._cached = None
        self._last_mtime = None

    def load(self) -> Dict[str, Any]:
        if isinstance(self.source, str) and os.path.isfile(self.source):
            mtime = os.path.getmtime(self.source)
            if self._cached and mtime == self._last_mtime:
                return self._cached
            with open(self.source, "r", encoding="utf-8") as f:
                content = f.read()
            out = self._parse(content)
            self._cached = out
            self._last_mtime = mtime
            return out
        elif isinstance(self.source, str):
            out = self._parse(self.source)
            self._cached = out
            return out
        elif callable(self.source):
            val = self.source()
            if isinstance(val, dict):
                self._cached = val
                return val
            elif isinstance(val, str):
                out = self._parse(val)
                self._cached = out
                return out
            else:
                self.logger.warning("Unknown return type from prompt library callback.")
                return {}
        elif isinstance(self.source, dict):
            self._cached = self.source
            return self.source
        else:
            raise ValueError(f"Unsupported prompt library source: {type(self.source)}")

    def _parse(self, content: str) -> Dict[str, Any]:
        # Try JSON
        if content.strip().startswith("{") and content.strip().endswith("}"):
            try:
                return json.loads(content)
            except Exception as ex:
                self.logger.warning(f"JSON parse failed: {ex}")
        # Try YAML
        if (content.strip().startswith("---") or content.strip().startswith("```yaml")) and HAS_YAML:
            try:
                if content.startswith("---"):
                    _, yaml_block, rest = content.split("---", 2)
                elif content.startswith("```yaml"):
                    _, yaml_block, rest = content.split("```yaml", 2)
                    yaml_block, rest = yaml_block.split("```", 1)
                else:
                    yaml_block, rest = content, ""
                meta = yaml.safe_load(yaml_block)
                prompts = meta.get("prompts", {})
                if isinstance(prompts, dict) and prompts:
                    return prompts
            except Exception as ex:
                self.logger.warning(f"YAML parse failed: {ex}")
        # Markdown multi-block (branch-root files)
        prompts = {}
        blocks = re.split(r"\n(?=## )", content)
        for block in blocks:
            lines = block.strip().splitlines()
            if not lines:
                continue
            meta, raw, template, curr_id = {}, block, [], None
            if lines[0].strip() in ("---", "```yaml"):
                try:
                    fm_lines = []
                    end_idx = 1
                    for i in range(1, len(lines)):
                        if lines[i].strip() in ("---", "```", "```yaml"):
                            end_idx = i + 1
                            break
                        fm_lines.append(lines[i])
                    fm = "\n".join(fm_lines)
                    meta = yaml.safe_load(fm) if HAS_YAML else {}
                    lines = lines[end_idx:]
                except Exception as ex:
                    self.logger.warning(f"Prompt YAML front matter parse failed: {ex}")
            for idx, line in enumerate(lines):
                if line.startswith("## "):
                    curr_id = line[3:].strip()
                elif line.startswith(">"):
                    try:
                        k, v = line[1:].split(":", 1)
                        meta[k.strip().lower()] = v.strip()
                    except Exception:
                        continue
                else:
                    template = lines[idx:]
                    break
            prompt_body = "\n".join(template).strip()
            key = meta.get("id") or curr_id or f"prompt_{len(prompts)}"
            prompts[key] = {"content": prompt_body, "metadata": meta, "raw": raw}
        return prompts

class PromptTemplate:
    """
    Single prompt template, agnostic to backend. Supports .format(), Jinja2, or user-defined.
    """
    def __init__(
        self,
        content: str,
        metadata: dict,
        backend: Optional[str] = None,
        custom_renderer: Optional[Callable[[str, dict], str]] = None,
    ):
        self.content = content
        self.metadata = metadata
        self.custom_renderer = custom_renderer
        self.backend = backend or metadata.get("engine")
        if not self.backend:
            if custom_renderer:
                self.backend = "custom"
            elif HAS_JINJA and ("{{" in content or "{%" in content):
                self.backend = "jinja2"
            else:
                self.backend = "format"

    def render(self, context: dict) -> str:
        try:
            if self.backend == "custom" and self.custom_renderer:
                return self.custom_renderer(self.content, context)
            elif self.backend == "jinja2" and HAS_JINJA:
                tmpl = JinjaTemplate(self.content)
                ast = tmpl.environment.parse(self.content)
                undeclared = jinja_meta.find_undeclared_variables(ast)
                missing = undeclared - set(context.keys())
                if missing:
                    pass
                return tmpl.render(**context)
            else:
                return self.content.format(**context)
        except Exception as ex:
            raise RuntimeError(f"Prompt render failed: {ex}")

class PromptSelector:
    """
    Manages all prompt templates; supports aliasing, context, hot reload, flexible querying.
    """
    def __init__(
        self,
        prompt_library: Optional[Union[str, Callable, Dict[str, Any], PromptLibrarySource]] = None,
        logger: Optional[Any] = None,
        custom_renderer: Optional[Callable[[str, dict], str]] = None,
    ):
        self.logger = get_logger(logger)
        if isinstance(prompt_library, PromptLibrarySource):
            self.library = prompt_library
        else:
            self.library = PromptLibrarySource(prompt_library, logger=self.logger)
        self.custom_renderer = custom_renderer
        self._cache = None

    def _load(self):
        self._cache = self.library.load()

    def get_prompt(self, prompt_id: str) -> PromptTemplate:
        if self._cache is None:
            self._load()
        keys = list(self._cache.keys())
        pid_norm = prompt_id.replace(" ", "_").lower()
        match = None
        for k in keys:
            if k == prompt_id or k.lower() == prompt_id.lower() or k.replace(" ", "_").lower() == pid_norm:
                match = k
                break
        if not match:
            raise KeyError(f"Prompt template not found: {prompt_id}")
        v = self._cache[match]
        return PromptTemplate(
            v["content"], v["metadata"], backend=v["metadata"].get("engine"), custom_renderer=self.custom_renderer
        )

    def find_by_category(self, category: str) -> List[Tuple[str, PromptTemplate]]:
        if self._cache is None:
            self._load()
        return [
            (k, PromptTemplate(v["content"], v["metadata"]))
            for k, v in self._cache.items()
            if v["metadata"].get("category", "").lower() == category.lower()
        ]

    def list_prompts(self) -> List[str]:
        if self._cache is None:
            self._load()
        return list(self._cache.keys())

    def prompt_metadata(self, prompt_id: str) -> dict:
        return self.get_prompt(prompt_id).metadata

    def reload(self):
        self._cache = None

class PSDEngine:
    """
    Orchestrates prompt assembly, context injection, runtime selection, and full AAIPCPTF/ChatGPT pipeline integration.
    """
    DEFAULT_ALIASES = {
        "pre_categorisation": ["Pre-Categorization", "pre_categorization"],
        "semantic_mapping": ["Semantic Mapping", "semantic-mapping"],
        "cultural_adaptation": ["Cultural Adaptation", "cultural-adaptation"],
        "iterative_refinement": ["Iterative Refinement", "iterative-refinement"],
        "final_qc": ["Final QC", "final-quality-check", "final_quality_check"],
    }

    def __init__(
        self,
        prompt_library: Optional[Union[str, Callable, Dict[str, Any], PromptLibrarySource]] = None,
        logger: Optional[Any] = None,
        custom_renderer: Optional[Callable[[str, dict], str]] = None,
        aliases: Optional[Dict[str, List[str]]] = None,
    ):
        self.logger = get_logger(logger)
        self.selector = PromptSelector(prompt_library, logger=logger, custom_renderer=custom_renderer)
        self.aliases = aliases or self.DEFAULT_ALIASES

    def _resolve_stage(self, stage: str) -> str:
        prompts = self.selector.list_prompts()
        stage_norm = stage.replace(" ", "_").lower()
        if stage in prompts:
            return stage
        for canon, alist in self.aliases.items():
            if stage == canon or stage.lower() == canon.lower() or stage in alist or stage_norm in [a.replace(" ", "_").lower() for a in alist]:
                for try_key in [canon] + alist:
                    if try_key in prompts or try_key.replace(" ", "_").lower() in [k.replace(" ", "_").lower() for k in prompts]:
                        for k in prompts:
                            if try_key == k or try_key.replace(" ", "_").lower() == k.replace(" ", "_").lower():
                                return k
        if stage_norm in [k.replace(" ", "_").lower() for k in prompts]:
            for k in prompts:
                if k.replace(" ", "_").lower() == stage_norm:
                    return k
        raise KeyError(f"Stage/prompt not found or mapped: {stage}")

    def assemble_prompt(
        self,
        stage: str,
        metadata: Dict[str, Any],
        extra_context: Optional[Dict[str, Any]] = None,
        custom_renderer: Optional[Callable[[str, dict], str]] = None,
        backend: Optional[str] = None,
    ) -> str:
        prompt_id = self._resolve_stage(stage)
        pt = self.selector.get_prompt(prompt_id)
        ctx = dict(metadata)
        if extra_context:
            ctx.update(extra_context)
        if custom_renderer:
            pt.custom_renderer = custom_renderer
            pt.backend = "custom"
        if backend:
            pt.backend = backend
        return pt.render(ctx)

    def run_prompt_stage(
        self,
        stage: str,
        metadata: Dict[str, Any],
        extra_context: Optional[Dict[str, Any]] = None,
        text: Optional[str] = None,
        **kwargs
    ) -> str:
        prompt = self.assemble_prompt(stage, metadata, extra_context, **kwargs)
        if text:
            prompt += "\n\n" + text
        return prompt

    def list_prompts(self) -> List[str]:
        return self.selector.list_prompts()

    def get_prompt_metadata(self, prompt_id: str) -> dict:
        return self.selector.prompt_metadata(prompt_id)

    def reload_library(self):
        self.selector.reload()

    def set_custom_renderer(self, renderer: Callable[[str, dict], str]):
        self.selector.custom_renderer = renderer

    def set_logger(self, logger: Any):
        self.logger = logger
        self.selector.logger = logger

def get_psd_engine(
    prompt_library: Optional[Union[str, Callable, Dict[str, Any], PromptLibrarySource]] = None,
    logger: Optional[Any] = None,
    custom_renderer: Optional[Callable[[str, dict], str]] = None,
    aliases: Optional[Dict[str, List[str]]] = None,
) -> PSDEngine:
    return PSDEngine(prompt_library, logger, custom_renderer, aliases)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AAIPCPTF PSD Engine – Ultra-Prompt Synthesis CLI")
    parser.add_argument("--stage", help="Pipeline stage (prompt id or alias)")
    parser.add_argument("--context", help="JSON string of metadata/context vars", default="{}")
    parser.add_argument("--text", help="Additional user/source text", default=None)
    parser.add_argument("--list", action="store_true", help="List all available prompt keys")
    parser.add_argument("--meta", help="Show metadata for a given prompt id")
    parser.add_argument("--reload", action="store_true", help="Reload prompt library")
    parser.add_argument("--library", help="Prompt library path (file) or in-memory string", default=None)
    args = parser.parse_args()

    library = args.library or os.environ.get("PROMPT_LIBRARY_PATH", None)
    engine = get_psd_engine(prompt_library=library)
    if args.reload:
        engine.reload_library()
    if args.list:
        print("Available prompts:", engine.list_prompts())
    elif args.meta:
        print(json.dumps(engine.get_prompt_metadata(args.meta), indent=2))
    elif args.stage:
        try:
            context = json.loads(args.context)
        except Exception:
            context = {}
        try:
            prompt = engine.run_prompt_stage(args.stage, context, text=args.text)
            print(f"\n--- {args.stage} Prompt ---\n")
            print(prompt)
        except Exception as ex:
            print(f"Error: {ex}")
    else:
        parser.print_help()
