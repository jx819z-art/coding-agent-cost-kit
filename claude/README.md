# Claude Code on Bedrock - what each setting does

JSON has no comments, so the reasoning lives here. Docs: https://code.claude.com/docs/en/env-vars

| Setting | Value | Why |
|---|---|---|
| `ANTHROPIC_MODEL` | Sonnet 5.5 ID | The single biggest lever. On Bedrock the default is Opus 5.5. At list prices, Sonnet 5.5 is half the price of Opus for input, output and cache writes, and the same price for cache reads. This variable overrides the `model` setting; `/model opus` overrides it for one session. |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet 5.5 ID | If you don't pin it, the `sonnet` alias falls back to **Sonnet 4.5** on Bedrock, which is older and dearer per token. |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus 5.5 ID | Keeps `/model opus` on a known version. |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku ID | Background jobs such as session titles run on Haiku rather than your main model. |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES` | `""` | Turns off thinking and effort for Haiku. Fine for small background jobs. |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Sonnet 5.5 ID | Without it, subagents inherit the session model, which could be Opus. |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | `200000` | 1M-token context is on by default on Bedrock. This summarises history before the context grows huge. Use a plain integer: `200k` is read as 200. |
| `ENABLE_PROMPT_CACHING_1H` | `1` | Cache writes cost 2× input instead of 1.25×, but the cache survives meetings and reading breaks rather than rebuilding the whole context. If `/usage` shows few misses, remove it. |
| `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION` | `false` | Saves the small request Claude Code makes after every reply to suggest your next prompt. |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `DISABLE_TELEMETRY` | `1` | No effect on cost; kept from the original setup. These also block auto-updates, so check `claude --version` now and then: the cache line in `/usage` needs v2.1.251 or later. |
| `effortLevel` | `medium` | The default for Opus 5.5 and Sonnet 5.5, set explicitly so it doesn't drift upwards. Thinking is billed as output and can't be turned off on these models. |
| `skipWebFetchPreflight` | `true` | A top-level setting (not under `env`). Kept from the original setup. |

## Deliberately absent

- **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`**: setting it to `1` *turns agent teams on*. Teams use about 7× the tokens of a normal session.
- **`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`**: this strips out context management (Claude Code clearing old tool results) and MCP tool search, so sessions grow faster. Only add it back as `"1"` if requests fail with `Unexpected value(s)` on the `anthropic-beta` header or `Extra inputs are not permitted`; that means your gateway or Bedrock route needs it.

## Measuring

- **`/usage`**: session cost by model at list prices, plus a "Prompt cache" line with the hit rate, misses and the cache lifetime in use. If the cache counts stay at zero, prompt caching isn't working in your Bedrock region; every turn is then billed at full input price, so fix that first.
- **`/context`**: what is taking up the context.
- **`python3 tools/agent_cost.py claude --budget 2000`**: month-to-date spend and pace for this machine.
- **AWS Cost Explorer**: filter to Amazon Bedrock and group by usage type. This is the authoritative split.
