# Codex CLI - what each setting does

Docs: https://developers.openai.com/codex/config-reference. `config.toml` carries short comments as well.
**Merge** it into `~/.codex/config.toml` rather than replacing that file: your provider, auth, MCP and project sections stay as they are.

| Setting | Value | Why |
|---|---|---|
| `model` | your everyday model | Use the cheapest model that does the job; switch per session with `/model`. |
| `model_reasoning_effort` | `"medium"` | Reasoning tokens are billed as output. Raise it per session for hard problems rather than by default. |
| `plan_mode_reasoning_effort` | `"high"` | Spends the deeper thinking on planning only. |
| `model_verbosity` | `"low"` | Shorter answers mean fewer output tokens. If your model rejects it, remove it. |
| `model_auto_compact_token_limit` | `150000` | Summarises history before the context grows huge, since every turn re-sends all of it. Lower it if your model's context window is smaller. |
| `[agents] max_concurrent_threads_per_session` | `2` | Multi-agent is on by default, and each spawned agent carries its own context. |
| `[agents] default_subagent_reasoning_effort` | `"low"` | Helper agents rarely need deep reasoning. |

## Optional (commented out in the template)

- **`web_search = "disabled"`**: removes the search tool and its results from context.
- **`[agents] default_subagent_model`**: a cheaper model for spawned agents.
- **`[features] goals = false`**: stops automatic goal continuation, which can run turns you didn't ask for.
- **`[features] apps = false`**: turns off app/connector integrations you don't use.
- **Bedrock provider**: Codex has a built-in `amazon-bedrock` provider. Set `model_provider = "amazon-bedrock"` plus `[model_providers.amazon-bedrock.aws]` with `profile` and `region`.

## Avoid

- **`service_tier = "fast"`** and the `/fast` toggle: fast maps to the priority tier, billed at a premium, and `/fast` saves the choice.

## Commands

| Command | What it does |
|---|---|
| `/new` | Fresh chat; use it between tasks and after breaks |
| `/compact` | Summarise the history now |
| `/status` | Model, settings and current token usage |
| `/usage` | Account token activity; needs a ChatGPT/Codex account sign-in, so it isn't available on a Bedrock provider |
| `python3 tools/agent_cost.py codex` | Token totals per model from `~/.codex/sessions`; add your rates to `tools/prices.json` to get dollar figures |
