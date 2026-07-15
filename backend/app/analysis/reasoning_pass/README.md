# `app/analysis/reasoning_pass/`

Home of the Communication Intelligence Engine's prompt library, per ADR
003 §3. This package holds no Python logic of its own — the six
reasoning modules that consume these prompts live in
`app/analysis/modules/` (`structure.py`, `clarity.py`, `logical_flow.py`,
`topic_drift.py`, `confidence.py`, `conciseness.py`), each pointing at
one prompt identifier here by name.

## Layout

```
reasoning_pass/
  prompts/
    analysis/     six real prompts backing this sprint's reasoning modules
    coaching/     reserved — empty until the Coaching Engine exists (ADR 003 §2)
    rewrite/      reserved — empty until a "rewrite my answer" module exists
```

Prompts are grouped by *what kind of output they produce*, not by which
module uses them: `analysis/` prompts always resolve to a
`ReasoningResult` (label/explanation/evidence, no scores, no coaching
language — this sprint's whole output contract). `coaching/` prompts
will eventually resolve to actionable recommendations once the separate
Coaching Engine (ADR 003 §2) is built against the CIE's `AnalysisReport`
output. `rewrite/` prompts will eventually resolve to rewritten text
(e.g. "say this more concisely") — a distinct output shape from both of
the above, and out of scope for both the CIE and the Coaching Engine as
currently designed.

## Metadata

Every prompt file under `prompts/` opens with a JSON frontmatter block
(id, version, type, expected_output, model_hints) before its body — see
`app/llm/prompt_loader.py`'s `PromptMetadata` for the enforced shape.
`type` here matches the folder it lives in (`"analysis"`, `"coaching"`,
`"rewrite"`) by convention, not because `PromptLoader` or
`PromptRegistry` enforce that correspondence — nothing currently checks
that a file under `prompts/analysis/` actually declares `"type":
"analysis"`. Keeping them in sync is left to whoever adds a prompt.

## Registering these prompts

Nothing in this package registers itself automatically yet. A caller
that wants these prompts available to a `DefaultLLMReasoner` calls
`PromptRegistry.discover_directory(path_to_prompts_analysis_dir)`
explicitly (see `app/llm/prompt_registry.py`) — the same manual wiring
this sprint's reasoning-module tests use with a fixtures directory
instead of this real one. A future sprint that wires reasoning modules
into `AnalysisEngine` for real will do this registration once, at
application startup, alongside `MODULE_REGISTRY`'s own module
registration (see `app/analysis/registry.py`).
