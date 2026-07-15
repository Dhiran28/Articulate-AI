# LLM Abstraction Layer (Sprint 4.4, prompt metadata extended Sprint 4.5, provider adapters added Milestone 5.1)

This is `app/llm/` — the seam ADR 003 named ("app/llm/ ... depended on
by both engines below; depends on neither") and Sprint 4.4 fully builds
out. Sprint 4.5 was this package's first real consumer, with each of six
reasoning modules calling `LLMReasoner.reason()` independently. Sprint
4.5.1 changed *who* calls it, not the interface itself: now exactly one
component, `ReasoningPass` (`app/analysis/reasoning_pass/batch.py`),
calls `LLMReasoner.reason()` once per analysis on behalf of all six
reasoning modules, which no longer call this package at all — see
`app/analysis/README.md`'s "Batching (Sprint 4.5.1)" section for the
full design.

**Milestone 5.1 fills in the one gap this file used to describe as
still-open:** four real `LLMProvider` adapters now exist, in the new
`app/llm/providers/` subpackage, exactly where "Future provider
integration" below always said they'd go — nothing in `provider.py`,
`reasoner.py`, or any other file listed in "Folder structure" changed to
make that possible. `ReasoningPass` and `CoachingEngine` are still
tested against a fake `LLMReasoner` (`tests/test_reasoning_pass.py`,
`tests/test_coaching.py`); the four adapters get their own tests
(`tests/test_llm_providers.py`), each with the vendor SDK's one
network-calling method monkeypatched out — see that file's own docstring.

## Folder structure

```
backend/app/llm/
├── provider.py          # LLMProvider — the Protocol every vendor adapter implements
├── reasoner.py           # LLMReasoner Protocol + DefaultLLMReasoner (the pipeline; owns call logging)
├── prompt_loader.py       # PromptTemplate, PromptLoader — reads one prompt file
├── prompt_registry.py     # PromptRegistry — the collection, keyed by identifier
├── response_parser.py     # parse_json_response() — raw text -> dict
├── schema_validator.py    # validate_schema() — dict -> validated pydantic model
├── retry_policy.py        # RetryPolicy — bounded retry with backoff
├── timeout_policy.py      # TimeoutPolicy — hard time limit per attempt
├── errors.py              # LLMError hierarchy
└── providers/             # Milestone 5.1 — the four concrete LLMProvider adapters
    ├── openai_provider.py     # OpenAI Chat Completions
    ├── anthropic_provider.py  # Anthropic Messages API
    ├── gemini_provider.py     # Google Gemini (google-genai SDK)
    ├── ollama_provider.py     # Local/self-hosted Ollama, plain HTTP (no SDK dependency)
    └── factory.py             # build_provider(settings) — selects one from Settings.llm_provider
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

## Provider adapters and selection (Milestone 5.1)

Each of the four adapters in `providers/` is exactly what "Future
provider integration" below used to ask for: a class implementing
`LLMProvider` — `provider_name`, `model_name`, `version`, and
`async def generate(prompt: str) -> str` — that calls one vendor's
SDK/API and returns the raw text response. Nothing in `provider.py`,
`reasoner.py`, `prompt_loader.py`, `prompt_registry.py`,
`response_parser.py`, `schema_validator.py`, `retry_policy.py`,
`timeout_policy.py`, or `errors.py` changed to add any of them.
`DefaultLLMReasoner` still only ever calls `provider.generate(prompt)` —
it has no idea, and no way to tell, whether that's OpenAI, a local
Ollama model, or a test double.

`providers/factory.py`'s `build_provider(settings)` is where selection
happens: it reads `Settings.llm_provider` (`app/core/config.py` —
`LLM_PROVIDER` in the environment) and constructs the matching adapter,
or returns `None` if nothing is configured or the selected vendor's
credential is missing. `app/core/dependencies.py`'s `get_llm_provider()`
calls it once per process (cached) — see that file's own "Milestone 5"
section header for the full degraded-path story. An unrecognized
`LLM_PROVIDER` value raises `UnknownProviderError` immediately, rather
than silently behaving like nothing was configured — a real
configuration mistake, not a legitimate empty state.

Each adapter also exposes a non-Protocol, diagnostic-only
`last_usage: dict | None` attribute (`{"prompt_tokens", "completion_tokens",
"total_tokens"}`, normalized from that vendor's own response shape) —
`DefaultLLMReasoner.reason()` reads it immediately after each call for
its one consolidated log line (see `reasoner.py`'s own docstring for
the full field list: session id, provider, model, prompt id/version,
latency, token usage, and errors — everything Milestone 5.1's logging
requirement asked for, logged once per call, in the one place every
current LLM caller already goes through).

The same applies to a provider adapter that raises its own SDK-specific
exceptions on failure: `DefaultLLMReasoner._call_provider` catches
anything that isn't already an `LLMError` and reclassifies it as
`LLMProviderError` — a provider implementation is never expected to know
about this package's own error hierarchy.

## What this layer still does not include, as of Milestone 5.1

No persistence of raw provider responses or logs beyond process stdout,
no per-request/per-user rate limiting above whatever each vendor's own
API enforces, and no streaming (`generate()` returns one complete
string, never a partial/streamed response) — the same "one call, one
validated result" shape this package has held since Sprint 4.4. Adding
a fifth vendor still only requires one new file in `providers/` plus one
new branch in `factory.py`'s `build_provider()` — nothing else in this
package.
