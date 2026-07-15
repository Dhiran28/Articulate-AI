"""
Tests for PromptLoader and PromptRegistry (Sprint 4.4).

See tests/README.md for how this file fits into the overall suite.
Fixture prompt files live under tests/fixtures/prompts/ — see that
directory's files for why they aren't real reasoning-module prompts.
"""

from pathlib import Path

import pytest

from app.llm.errors import PromptNotFoundError
from app.llm.prompt_loader import PromptFormatError, PromptLoader, PromptMetadata, PromptTemplate
from app.llm.prompt_registry import DuplicatePromptError, PromptRegistry

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "prompts"


class TestPromptLoader:
    def test_loads_a_prompt_file(self) -> None:
        loader = PromptLoader()
        template = loader.load("structure_v1", FIXTURES_DIR / "structure_v1.md")

        assert isinstance(template, PromptTemplate)
        assert template.identifier == "structure_v1"
        assert "$transcript" in template.raw_text

    def test_raises_for_a_missing_file(self, tmp_path: Path) -> None:
        loader = PromptLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("does_not_exist", tmp_path / "nope.md")


class TestPromptMetadata:
    """Sprint 4.5: every real prompt file must declare structured metadata."""

    def test_a_loaded_prompt_exposes_its_metadata(self) -> None:
        template = PromptLoader().load("structure_v1", FIXTURES_DIR / "structure_v1.md")

        assert isinstance(template.metadata, PromptMetadata)
        assert template.metadata.id == "structure_v1"
        assert template.metadata.version == "1.0.0"
        assert template.metadata.type == "analysis"
        assert template.metadata.expected_output == "ReasoningResult"
        assert template.metadata.model_hints == {"temperature": 0.2}

    def test_raw_text_excludes_the_frontmatter_block(self) -> None:
        template = PromptLoader().load("structure_v1", FIXTURES_DIR / "structure_v1.md")

        assert not template.raw_text.startswith("---")
        assert '"id": "structure_v1"' not in template.raw_text
        assert "$transcript" in template.raw_text

    def test_missing_frontmatter_raises_prompt_format_error(self, tmp_path: Path) -> None:
        path = tmp_path / "no_metadata.md"
        path.write_text("Just a prompt body with $transcript, no frontmatter at all.")

        with pytest.raises(PromptFormatError):
            PromptLoader().load("no_metadata", path)

    def test_malformed_json_frontmatter_raises_prompt_format_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad_json.md"
        path.write_text("---\n{not valid json\n---\nBody: $transcript")

        with pytest.raises(PromptFormatError):
            PromptLoader().load("bad_json", path)

    def test_incomplete_frontmatter_raises_prompt_format_error(self, tmp_path: Path) -> None:
        # Valid JSON, but missing required fields (version, expected_output, ...).
        path = tmp_path / "incomplete.md"
        path.write_text('---\n{"id": "x", "type": "analysis"}\n---\nBody: $transcript')

        with pytest.raises(PromptFormatError):
            PromptLoader().load("incomplete", path)


class TestPromptTemplateRender:
    def test_substitutes_variables(self) -> None:
        template = PromptTemplate(identifier="x", path=Path("x.md"), raw_text="Hello $name, review: $transcript")
        rendered = template.render({"name": "Coach", "transcript": "we should ship it"})
        assert rendered == "Hello Coach, review: we should ship it"

    def test_missing_variable_raises_a_clear_error(self) -> None:
        template = PromptTemplate(identifier="x", path=Path("x.md"), raw_text="Review: $transcript")
        with pytest.raises(ValueError, match="x"):
            template.render({})

    def test_literal_braces_are_not_treated_as_placeholders(self) -> None:
        # The whole reason for $variable syntax over .format()-style
        # {variable}: prompts routinely embed example JSON output, full
        # of literal braces that must survive untouched.
        template = PromptTemplate(
            identifier="x",
            path=Path("x.md"),
            raw_text='Return JSON like {"label": "x"}. Transcript: $transcript',
        )
        rendered = template.render({"transcript": "hi"})
        assert rendered == 'Return JSON like {"label": "x"}. Transcript: hi'


class TestPromptRegistry:
    def test_register_and_get(self) -> None:
        registry = PromptRegistry()
        registry.register("structure_v1", FIXTURES_DIR / "structure_v1.md")

        template = registry.get("structure_v1")
        assert template.identifier == "structure_v1"
        assert "structure_v1" in registry
        assert len(registry) == 1

    def test_get_raises_prompt_not_found_for_unknown_identifier(self) -> None:
        registry = PromptRegistry()
        with pytest.raises(PromptNotFoundError):
            registry.get("does_not_exist")

    def test_duplicate_registration_is_rejected(self) -> None:
        registry = PromptRegistry()
        registry.register("structure_v1", FIXTURES_DIR / "structure_v1.md")

        with pytest.raises(DuplicatePromptError):
            registry.register("structure_v1", FIXTURES_DIR / "clarity_v1.md")

    def test_a_rejected_duplicate_does_not_replace_the_original(self) -> None:
        registry = PromptRegistry()
        registry.register("structure_v1", FIXTURES_DIR / "structure_v1.md")
        original = registry.get("structure_v1")

        with pytest.raises(DuplicatePromptError):
            registry.register("structure_v1", FIXTURES_DIR / "clarity_v1.md")

        assert registry.get("structure_v1") is original

    def test_discover_directory_registers_every_matching_file_by_stem(self) -> None:
        registry = PromptRegistry()
        identifiers = registry.discover_directory(FIXTURES_DIR)

        assert set(identifiers) == {"structure_v1", "clarity_v1", "topic_drift_v1"}
        assert len(registry) == 3
        assert registry.get("clarity_v1").identifier == "clarity_v1"

    def test_discover_respects_a_custom_pattern(self, tmp_path: Path) -> None:
        frontmatter = (
            '---\n{"id": "a", "version": "1.0.0", "type": "analysis", '
            '"expected_output": "ReasoningResult", "model_hints": {}}\n---\n'
        )
        (tmp_path / "a.txt").write_text(frontmatter + "hello $x")
        (tmp_path / "b.md").write_text(frontmatter + "hello $x")

        registry = PromptRegistry()
        identifiers = registry.discover_directory(tmp_path, pattern="*.txt")

        assert identifiers == ["a"]

    def test_clear_removes_every_registered_prompt(self) -> None:
        registry = PromptRegistry()
        registry.discover_directory(FIXTURES_DIR)

        registry.clear()

        assert len(registry) == 0
        assert registry.discover() == []
