# LLM Abstraction Layer (Sprint 4.4, prompt metadata extended Sprint 4.5)

This is `app/llm/` — the seam ADR 003 named ("app/llm/ ... depended on
by both engines below; depends on neither") and Sprint 4.4 fully builds
out. **It still contains no vendor SDK and no API key handling.**
Sprint 4.5 was this package's first real consumer, with each of six
reasoning modules calling `LLMReasoner.reason()` independently. Sprint
4.5.1 changed *who* calls it, not the interface itself: now exactly one
component, `ReasoningPass` (`app/analysis/reasoning_pass/batch.py`),
calls `LLMReasoner.reason()` once per analysis on behalf of all six
reasoning modules, which no longer call this package at all — see
`app/analysis/README.md`'s "Batching (Sprint 4.5.1)" section for the
full design. `ReasoningPass` is tested against a fake `LLMReasoner`
(`tests/test_reasoning_pass.py`), same as this package's own tests use
for `LLMProvider` — still no vendor SDK or real provider wired in
anywhere.

## Folder structure

```
backend/app/llm/
├── provider.py          # LLMProvider — the Protocol every vendor adapter implements
├── reasoner.py           # LLMReasoner Protocol + DefaultLLMReasoner (the pipeline)
├── prompt_loader.py       # PromptTemplate, PromptLoader — reads one prompt file
├── prompt_registry.py     # PromptRegistry — the collection, keyed by identifier
├── response_parser.py     # parse_json_response() — raw text -> dict
├── schema_validator.py    # validate_schema() — dict -> validated pydantic model
├── retry_policy.py        # RetryPolicy — bounded retry with backoff
├── timeout_policy.py      # TimeoutPolicy — hard time limit per attempt
└── errors.py              # LLMError hierarchy
```

Real prompt files do **not** live in this package. Per ADR 003 §3, those
belong to the Communication Intelligence Engine, now at
`app/analysis/reasoning_pass/prompts/analysis/` — as of Sprint 4.5.1, one
combined file, `reasoning_pass_v1.md`, covering all six reasoning
dimensions in a single prompt (replacing the six separate per-dimension
files Sprint 4.5 originally shipped), plus reserved-empty
`prompts/coaching/` and `prompts/rewrite/`. This package's own
`backend/tests/fixtures/prompts/`
files remain test fixtures only, used to prove `PromptLoader`/
`PromptRegistry` work in isolation — explicitly labeled as fixtures in
their own file headers, not real reasoning-module content. Nothing in
this package auto-registers the real prompts; a caller wanting them
available calls `PromptRegistry.discover_directory(...)` against that
real directory, same as any fixture directory in tests.

## The provider interface

`LLMProvider` (`provider.py`) is deliberately the smallest possible
surface — the same "provider does one thing, everything else lives
above it" shape as `TranscriptionProvider`
(`app/transcription/providers/base.py`, Sprint 3.4):

```python
class LLMProvider(Protocol):
    provider_name: str   # "openai", "anthropic", "ollama", ...
    model_name: str      # "gpt-4o", "claude-opus-4-8", "llama3.1", ...
    version: str         # this adapter's own version, for reproducibility
    async def generate(self, prompt: str) -> str: ...
```

No vendor is referenced anywhere in this package — not in an import, not
in a config default, not in a test (test doubles satisfy the same
Protocol without touching a real SDK). `generate()` returns plain text;
turning that into validated structured data is `response_parser.py` and
`schema_validator.py`'s job, composed by `DefaultLLMReasoner` — not the
provider's. Keeping the provider this dumb is what makes it trivial to
implement for a vendor whose SDK has no JSON mode at all.

## Prompt loading

Prompts are markdown/text files, never Python string literals:

- **`PromptLoader.load(identifier, path)`** reads one file into a
  `PromptTemplate` (`identifier`, `path`, `raw_text`, `metadata`).
  **Sprint 4.5 change:** every prompt file must now open with a JSON
  frontmatter block — `---\n{...}\n---\n` — declaring `id`, `version`,
  `type`, `expected_output`, and `model_hints`, parsed into a
  `PromptMetadata` pydantic model. JSON rather than YAML deliberately,
  to avoid a new third-party dependency for a metadata shape simple
  enough that `json.loads` plus the same pydantic validation every other
  typed shape in this codebase already uses is sufficient. A prompt file
  missing this block, or whose frontmatter is malformed JSON or fails
  `PromptMetadata` validation, raises `PromptFormatError` at load time —
  loud and immediate, not a warning or a best-effort partial load.
- **`PromptTemplate.render(variables)`** substitutes `$variable`-style
  placeholders (Python's stdlib `string.Template`), not
  `.format()`-style `{variable}` — deliberately, since every reasoning
  prompt will embed an example JSON output block full of literal `{`
  and `}` characters that `.format()` would misread as placeholders.
  `$variable` never collides with that.
- **`PromptRegistry`** is the named collection — `register(identifier,
  path)`, `discover_directory(dir, pattern="*.md")` (bulk-registers
  every matching file by its stem), `get(identifier)` (raises
  `PromptNotFoundError` if unknown), duplicate registration rejected via
  `DuplicatePromptError`. Deliberately the same shape as `ModuleRegistry`
  (`app/analysis/registry.py`, Sprint 4.2) — a named collection looked up
  by a stable id, where a collision should be loud, not silent, is the
  same problem in both places.

## The reasoning pipeline

`DefaultLLMReasoner.reason(prompt_id, context, schema)` composes every
piece above into one call:

1. Look up `prompt_id` in the `PromptRegistry` → `PromptNotFoundError` if
   unknown.
2. Render the template with `context` (a plain `dict[str, object]` of
   template variables — **not** a `TranscriptProcessingResult**. This
   package has never heard of a transcript; importing that model here
   would make `app/llm` depend on the CIE's domain models, exactly
   backwards from what ADR 003 §3 requires. A future reasoning module
   turns its `TranscriptProcessingResult` into whatever `context` dict
   its own prompt needs — that translation happens on the caller's
   side.
3. Call the provider. Each attempt is wrapped in `TimeoutPolicy` (one
   hung call can never block forever); the whole attempt sequence is
   wrapped in `RetryPolicy`, which by default retries only
   `LLMProviderError` — not a timeout, and not a schema/parsing failure
   (retrying the exact same prompt against the exact same model won't
   produce a different valid answer).
4. Parse the raw text response into JSON (`LLMInvalidResponseError` on
   failure — malformed JSON, or valid JSON that isn't an object).
5. Validate the parsed JSON against `schema`, a plain pydantic model
   (`LLMSchemaError` on failure — missing fields, wrong types).

Every exception this raises is a subclass of `LLMError` — a caller never
has to catch a raw `ValueError`, `JSONDecodeError`, or provider SDK
exception directly. Nothing is ever force-repaired or guessed at: a
malformed or schema-invalid response is always a loud, classified
failure, with the raw response preserved (never shown to an end user)
for debugging — the same principle ADR 003 §5/§7 established before this
package existed to enforce it.

## Error hierarchy

| Exception | Reason | When |
|---|---|---|
| `LLMTimeoutError` | `llm_timeout` | An attempt exceeded `TimeoutPolicy.timeout_seconds`. |
| `LLMProviderError` | `llm_provider_error` | The provider call failed outright (connection error, rate limit, any non-timeout exception), after retries are exhausted. |
| `LLMInvalidResponseError` | `llm_invalid_response` | The response wasn't valid JSON (after stripping an optional markdown fence). |
| `LLMSchemaError` | `llm_schema_error` | The response was valid JSON but didn't match the requested schema. |
| `PromptNotFoundError` | `prompt_not_found` | `reason()` was called with an unregistered `prompt_id`. |
| `NoProviderConfiguredError` | `no_provider_configured` | A `DefaultLLMReasoner` was constructed with `provider=None`. |

Every subclass fixes its own `reason` as a class attribute — a caller
can catch the specific subclass (`except LLMSchemaError:`) or the base
`LLMError` and branch on `.reason`, whichever fits.

## Future provider integration

Adding OpenAI, Anthropic, Google Gemini, Ollama, or a self-hosted local
model is, by design, a change that touches **one new file and nothing
in this package**:

1. Write a class implementing `LLMProvider` — `provider_name`,
   `model_name`, `version`, and `async def generate(prompt: str) ->
   str` that calls that vendor's SDK/API and returns the raw text
   response. It lives outside `app/llm/`, the same way
   `OpenAIWhisperProvider` lives in `app/transcription/providers/`, not
   inside the generic `app/transcription/` seam it implements.
2. Wire it up wherever provider selection happens (a future
   `app/core/dependencies.py` addition, config-driven — not built this
   sprint, since that's where an API key would first need to exist, and
   this sprint explicitly has none).
3. Nothing in `provider.py`, `reasoner.py`, `prompt_loader.py`,
   `prompt_registry.py`, `response_parser.py`, `schema_validator.py`,
   `retry_policy.py`, `timeout_policy.py`, or `errors.py` changes.
   `DefaultLLMReasoner` only ever calls `provider.generate(prompt)` —
   it has no idea, and no way to tell, whether that's OpenAI, a local
   Ollama model, or a test double.

The same applies to a provider adapter that raises its own SDK-specific
exceptions on failure: `DefaultLLMReasoner._call_provider` catches
anything that isn't already an `LLMError` and reclassifies it as
`LLMProviderError` — a provider implementation is never expected to know
about this package's own error hierarchy.

## What this layer still does not include, as of Sprint 4.5.1

Still no concrete provider (OpenAI/Anthropic/Gemini/Ollama/local), no API
keys, and no provider-selection wiring in `app/core/dependencies.py` —
`ReasoningPass` is tested exclusively against a fake `LLMReasoner`,
never a real one. The batching mechanism ADR 003 §1 required (one
combined LLM call across the six reasoning dimensions, instead of six
independent calls) is no longer missing — Sprint 4.5.1 built it, see
`app/analysis/README.md`'s "Batching (Sprint 4.5.1)" section. Wiring in
a real provider remains explicitly left for a future sprint.
