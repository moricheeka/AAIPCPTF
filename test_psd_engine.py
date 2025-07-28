import pytest
import os
import json
from psd_engine import PSDEngine, PromptLibrarySource

# --- In-memory prompt library for deterministic unit tests ---
PROMPT_LIB = {
    "semantic_mapping": {
        "content": "Semantic prompt for {subject} with tone: {tone}.",
        "metadata": {"category": "mapping"},
        "raw": "Semantic prompt block"
    },
    "final_qc": {
        "content": "Final QC: {qc_score} / {max_score}",
        "metadata": {"category": "qc"},
        "raw": "Final QC block"
    }
}

def test_assemble_prompt_basic():
    """Test basic in-memory prompt assembly."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    prompt = engine.assemble_prompt("semantic_mapping", {"subject": "math", "tone": "formal"})
    assert "math" in prompt and "formal" in prompt

def test_run_prompt_stage_with_extra_text():
    """Test run_prompt_stage with extra appended text."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    result = engine.run_prompt_stage(
        "final_qc",
        {"qc_score": 98, "max_score": 100},
        text="Additional notes here."
    )
    assert "Final QC" in result and "98" in result and "notes" in result

def test_prompt_alias_resolution():
    """Test that alias resolution works for default AAIPCPTF aliases."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    # Should resolve canonical/alias and case-insensitive
    prompt = engine.assemble_prompt("final_qc", {"qc_score": 10, "max_score": 10})
    assert "10" in prompt
    # Also test alternate spelling/alias
    prompt = engine.assemble_prompt("Final QC", {"qc_score": 5, "max_score": 5})
    assert "5" in prompt

def test_missing_variable_is_handled_gracefully():
    """Test that missing variables raise clear error."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    # 'tone' missing, should raise RuntimeError
    with pytest.raises(RuntimeError) as excinfo:
        engine.assemble_prompt("semantic_mapping", {"subject": "x"})
    # Optionally check error message content
    assert "Prompt render failed" in str(excinfo.value)

def test_list_prompts_and_metadata():
    """Test prompt listing and metadata access."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    prompts = engine.list_prompts()
    assert "semantic_mapping" in prompts and "final_qc" in prompts
    meta = engine.get_prompt_metadata("semantic_mapping")
    assert meta["category"] == "mapping"

def test_reload_library_does_not_throw():
    """Test that reload_library does not throw and reloads prompt list."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    engine.reload_library()
    assert "semantic_mapping" in engine.list_prompts()

def test_file_prompt_library(tmp_path):
    """Test prompt library loaded from real file in branch-root style."""
    prompt_file = tmp_path / "prompts.md"
    prompt_file.write_text(
        "## my_prompt\n> id: my_prompt\nThis is a prompt for {foo}."
    )
    engine = PSDEngine(prompt_library=str(prompt_file))
    out = engine.assemble_prompt("my_prompt", {"foo": "test"})
    assert "test" in out

def test_missing_file_raises(tmp_path):
    """Test error when referencing a missing file."""
    missing_path = tmp_path / "does_not_exist.md"
    with pytest.raises(Exception) as excinfo:
        engine = PSDEngine(prompt_library=str(missing_path))
        engine.assemble_prompt("my_prompt", {"foo": "bar"})
    # Accept either kind of error message (platform-dependent)
    err_str = str(excinfo.value)
    assert "not found" in err_str or "No such file" in err_str or "Unsupported" in err_str

def test_malformed_prompt_raises(tmp_path):
    """Test error raised for malformed prompt (unclosed variable)."""
    prompt_file = tmp_path / "bad.md"
    prompt_file.write_text("## bad\nBad {foo\n")
    engine = PSDEngine(prompt_library=str(prompt_file))
    with pytest.raises(RuntimeError) as excinfo:
        engine.assemble_prompt("bad", {"foo": "x"})
    assert "Prompt render failed" in str(excinfo.value)

def test_empty_prompt_library_is_handled(tmp_path):
    """Test error raised for empty prompt library."""
    prompt_file = tmp_path / "empty.md"
    prompt_file.write_text("")
    engine = PSDEngine(prompt_library=str(prompt_file))
    with pytest.raises(KeyError):
        engine.assemble_prompt("anything", {"x": 1})

def test_prompt_with_extra_variables():
    """Test prompt assembly with extra unused context variables."""
    prompt_lib = {
        "extra": {
            "content": "Hi {a} {b}!",
            "metadata": {},
            "raw": ""
        }
    }
    engine = PSDEngine(prompt_library=prompt_lib)
    out = engine.assemble_prompt("extra", {"a": "A", "b": "B", "c": "C"})
    assert "A" in out and "B" in out

def test_incorrect_alias_raises():
    """Test error raised for non-existent prompt/stage."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    with pytest.raises(KeyError):
        engine.assemble_prompt("not_a_real_stage", {"x": 1})

def test_yaml_prompt_library(tmp_path):
    """Test loading and assembling prompt from YAML library."""
    yaml_content = """---
prompts:
  yprompt:
    content: "YAML prompt {var}!"
    metadata: {category: test}
    raw: ""
---
"""
    prompt_file = tmp_path / "prompt.yaml"
    prompt_file.write_text(yaml_content)
    engine = PSDEngine(prompt_library=str(prompt_file))
    out = engine.assemble_prompt("yprompt", {"var": "YY"})
    assert "YY" in out

def test_custom_renderer_called():
    """Test that a custom renderer is called and its output returned."""
    called = {}
    def renderer(content, context):
        called['ok'] = True
        return "R"
    prompt_lib = {
        "c": {"content": "hi", "metadata": {}, "raw": ""}
    }
    engine = PSDEngine(prompt_library=prompt_lib, custom_renderer=renderer)
    assert engine.assemble_prompt("c", {}) == "R"
    assert called.get('ok') is True

def test_hot_reload_file_prompt_library(tmp_path):
    """Test hot reload works for disk file prompt libraries."""
    prompt_file = tmp_path / "reload.md"
    prompt_file.write_text("## reload_test\nReload {a}.")
    engine = PSDEngine(prompt_library=str(prompt_file))
    assert "X" in engine.assemble_prompt("reload_test", {"a": "X"})
    # Modify file
    prompt_file.write_text("## reload_test\nReloaded {a}!")
    engine.reload_library()
    assert "Reloaded" in engine.assemble_prompt("reload_test", {"a": "Y"})

def test_invisible_orchestration_hook():
    """Test invisible orchestration (simulate internal AAIPCPTF function call)."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    def orchestrate(stage, metadata):
        return engine.run_prompt_stage(stage, metadata)
    result = orchestrate("semantic_mapping", {"subject": "x", "tone": "y"})
    assert "semantic" in result.lower()
    assert "x" in result and "y" in result

def test_logger_fallback_and_setter(capsys):
    """Test fallback logger and explicit logger assignment."""
    import logging
    logger = logging.getLogger("PSD_ENGINE_TEST")
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    engine.set_logger(logger)
    logger.info("Test log message")
    combined_out = capsys.readouterr().out + capsys.readouterr().err
    assert "Test log message" in combined_out

def test_dynamic_context_injection():
    """Test dynamic runtime context update in prompt assembly."""
    engine = PSDEngine(prompt_library=PromptLibrarySource(PROMPT_LIB))
    meta = {"subject": "physics"}
    extra = {"tone": "witty"}
    prompt = engine.assemble_prompt("semantic_mapping", meta, extra_context=extra)
    assert "physics" in prompt and "witty" in prompt

def test_jinja2_backend_if_available():
    """Test Jinja2 rendering if Jinja2 is present (optional)."""
    try:
        from jinja2 import Template
    except ImportError:
        return  # Skip if jinja2 not installed
    prompt_lib = {
        "jinja": {
            "content": "Hello {{name}}!",
            "metadata": {},
            "raw": ""
        }
    }
    engine = PSDEngine(prompt_library=prompt_lib)
    result = engine.assemble_prompt("jinja", {"name": "World"})
    assert "Hello World!" in result
