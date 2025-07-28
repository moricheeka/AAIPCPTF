# orchestration_example.py
"""
AAIPCPTF-Compliant Orchestration Example (Live Repo SOP-Ready Edition)
----------------------------------------------------------------------
- All project files are expected at AAIPCPTF/tree/main/.
- 100% compliant with AAIPCPTF workflow, pipeline, and metadata orchestration as described in aaipcptf.docx.
- Supports invisible function-call orchestration, QA hooks, mode/IDDA state, and audit logging.
"""

import json
import copy
import sys
import os
from psd_engine import get_psd_engine, PSDEngine

# === Stage Sequence: Use the canonical AAIPCPTF pipeline order ===
AAIPCPTF_PIPELINE = [
    "pre_categorisation",
    "semantic_mapping",
    "cultural_adaptation",
    "iterative_refinement",
    "final_qc",
]

# === Minimal Example Prompt Library (All must be present) ===
DEFAULT_PROMPT_LIBRARY = {
    "pre_categorisation": {
        "content": "Categorize the text into primary, secondary, and hybrid genres. Provide confidence scores.",
        "metadata": {"category": "categorization"},
        "raw": "",
    },
    "semantic_mapping": {
        "content": "Map key concepts and frames for {subject} in a {tone} tone. Ensure deep equivalence.",
        "metadata": {"category": "semantic"},
        "raw": "",
    },
    "cultural_adaptation": {
        "content": "Adapt culture-specific references and idioms for the target audience. Source: {source_culture}, Target: {target_culture}",
        "metadata": {"category": "cultural"},
        "raw": "",
    },
    "iterative_refinement": {
        "content": "Perform iterative back-translation and QA for {qa_score}/{max_score}. Refine for fidelity and nuance.",
        "metadata": {"category": "refinement"},
        "raw": "",
    },
    "final_qc": {
        "content": "Run final quality check: coherence={coherence}, style={style}, terminology={terminology}, completeness={completeness}. Overall pass threshold: {pass_threshold}",
        "metadata": {"category": "qc"},
        "raw": "",
    },
}

# === Metadata Initialization (as in SOP: section 7.1) ===
def load_initial_metadata():
    return {
        "framework_version": "AAIPCPTF_v1.0",
        "mode_state": {"idda": "off"},
        "source_details": {},
        "category_label": "",
        "confidence": 0.0,
        "tonal_profile": {},
        "concept_list": [],
        "disambiguation_map": {},
        "embeddings": {},
        "chunks": [],
        "neologisms": [],
        "pipeline_parameters": {},
        "iteration_logs": [],
        "human_feedback": {},
        "final_quality_scores": {},
        "error_logs": [],
        "logs": [],
        # Add/extend as needed to match current metadata_schema.json
    }

# === Unified Orchestration Result Object ===
class AAIPCPTFStepResult:
    """Structured result for each pipeline stage for AAIPCPTF master log/audit compatibility."""
    def __init__(self, stage, input_context, prompt, output, metadata, success=True, error=None):
        self.stage = stage
        self.input_context = copy.deepcopy(input_context)
        self.prompt = prompt
        self.output = output
        self.metadata = copy.deepcopy(metadata)
        self.success = success
        self.error = str(error) if error else None

    def to_dict(self):
        return {
            "stage": self.stage,
            "input_context": self.input_context,
            "prompt": self.prompt,
            "output": self.output,
            "metadata": self.metadata,
            "success": self.success,
            "error": self.error,
        }

    def __str__(self):
        status = "[OK]" if self.success else f"[ERROR: {self.error}]"
        return (f"{status} {self.stage}:\nPrompt: {self.prompt}\nOutput: {self.output}\nMetadata: {json.dumps(self.metadata, ensure_ascii=False)}\n")

# === Orchestration Functions ===

def universal_engine(prompt_library=None, logger=None, custom_renderer=None, aliases=None):
    plib = prompt_library if prompt_library is not None else DEFAULT_PROMPT_LIBRARY
    return get_psd_engine(prompt_library=plib, logger=logger, custom_renderer=custom_renderer, aliases=aliases)

def orchestrate_aaipcptf_step(
    stage,
    input_context,
    engine=None,
    extra_context=None,
    metadata=None,
    logger=None,
    custom_renderer=None,
    as_result=True,
    qa_hook=None,
    addon_hooks=None
):
    """Orchestrate one SOP-compliant AAIPCPTF pipeline step with context and metadata propagation."""
    if engine is None:
        engine = universal_engine(logger=logger, custom_renderer=custom_renderer)
    ctx = copy.deepcopy(input_context)
    if extra_context:
        ctx.update(extra_context)
    _meta = copy.deepcopy(metadata) if metadata else {}
    try:
        prompt = engine.assemble_prompt(stage, ctx)
        output = engine.run_prompt_stage(stage, ctx)
        # --- QA/Add-on Hooks ---
        qa_result = None
        if qa_hook:
            qa_result = qa_hook(stage, ctx, prompt, output)
            _meta["qa"] = qa_result
        if addon_hooks:
            for hook in addon_hooks:
                output, _meta = hook(stage, ctx, prompt, output, _meta)
        return AAIPCPTFStepResult(stage, ctx, prompt, output, _meta, success=True) if as_result else output
    except Exception as ex:
        if logger:
            logger.error(f"Stage '{stage}' failed: {ex}")
        return AAIPCPTFStepResult(stage, ctx, None, None, _meta, success=False, error=ex) if as_result else None

def orchestrate_aaipcptf_pipeline(
    pipeline_stages,
    base_context,
    engine=None,
    logger=None,
    custom_renderer=None,
    per_stage_context=None,
    per_stage_metadata=None,
    qa_hook=None,
    addon_hooks=None,
    as_result=True
):
    """Orchestrate a full AAIPCPTF pipeline, including metadata/context propagation and logging hooks."""
    if engine is None:
        engine = universal_engine(logger=logger, custom_renderer=custom_renderer)
    results = {}
    context = copy.deepcopy(base_context)
    metadata = context.get("metadata", {}) if isinstance(context, dict) else {}
    for stage in pipeline_stages:
        extra_ctx = (per_stage_context or {}).get(stage, {})
        stage_meta = (per_stage_metadata or {}).get(stage, {})
        step_result = orchestrate_aaipcptf_step(
            stage, context, engine=engine,
            extra_context=extra_ctx, metadata=stage_meta,
            logger=logger, custom_renderer=custom_renderer,
            as_result=as_result, qa_hook=qa_hook, addon_hooks=addon_hooks
        )
        results[stage] = step_result
        # SOP: Propagate/merge stage outputs/metadata into master context
        if step_result and step_result.success and step_result.output:
            context[f"{stage}_output"] = step_result.output
            if hasattr(step_result, "metadata") and isinstance(step_result.metadata, dict):
                context.update(step_result.metadata)
    return results

# === CLI/Human/LLM Entrypoint ===

def cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="AAIPCPTF Orchestration Example: SOP-Compatible")
    parser.add_argument("--metadata", type=str, default=None, help="JSON string or file for metadata/context")
    parser.add_argument("--pipeline", type=str, nargs='*', default=None, help="Pipeline stages (space-separated)")
    parser.add_argument("--prompt_library", type=str, default=None, help="Path to prompt library file (JSON, YAML, or Markdown)")
    parser.add_argument("--alias", action='append', help="Alias mapping in 'canon:alias1,alias2' format")
    parser.add_argument("--json", action='store_true', help="Print results as JSON")
    args = parser.parse_args()

    # Metadata
    if args.metadata:
        if os.path.isfile(args.metadata):
            with open(args.metadata, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = json.loads(args.metadata)
    else:
        metadata = load_initial_metadata()

    # Pipeline
    pipeline_stages = args.pipeline if args.pipeline else list(AAIPCPTF_PIPELINE)

    # Prompt Library
    prompt_library = None
    if args.prompt_library:
        if os.path.isfile(args.prompt_library):
            prompt_library = args.prompt_library
        else:
            print(f"Prompt library file '{args.prompt_library}' not found. Using default.")
            prompt_library = None

    # Aliases
    aliases = None
    if args.alias:
        aliases = {}
        for alias_arg in args.alias:
            try:
                canon, alist = alias_arg.split(":")
                aliases[canon.strip()] = [a.strip() for a in alist.split(",")]
            except Exception:
                print(f"Ignoring malformed alias: {alias_arg}")

    engine = universal_engine(prompt_library=prompt_library, aliases=aliases)
    try:
        results = orchestrate_aaipcptf_pipeline(pipeline_stages, metadata, engine=engine, as_result=True)
    except Exception as e:
        print(f"Fatal orchestration error: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps({k: v.to_dict() for k, v in results.items()}, indent=2, ensure_ascii=False))
    else:
        for stage, result in results.items():
            print(result)

# === Demo (Invisible/Scripted Orchestration) ===

def demo():
    print("\n[AAIPCPTF SOP-Compatible Orchestration Example]\n")

    engine = universal_engine()
    metadata = load_initial_metadata()
    pipeline_results = orchestrate_aaipcptf_pipeline(AAIPCPTF_PIPELINE, metadata, engine)
    for stage, result in pipeline_results.items():
        print(f"[{stage}]:\n{result}")

    print("\nAlias/dynamic context example:")
    alias_metadata = copy.deepcopy(metadata)
    alias_metadata["tone"] = "creative"
    alias_result = orchestrate_aaipcptf_step("Final QC", alias_metadata, engine)
    print(alias_result)

    print("\nError demonstration (missing required context):")
    err_result = orchestrate_aaipcptf_step("semantic_mapping", {"subject": "foo"}, engine)
    print(err_result)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_main()
    else:
        demo()
