# coding-agent-cost-kit

Settings and a log-based cost estimator to keep **Claude Code** (on Amazon Bedrock) and
**Codex CLI** inside a monthly token budget.

Written 2026-10-12 against the Claude Code docs (v2.1.29x) and Codex CLI 0.153.4.
Setting names change between releases: re-check the linked docs after upgrading.

| Path | What |
|---|---|
| `claude/settings.json` | Template for `~/.claude/settings.json` ([notes](claude/README.md)) |
| `codex/config.toml` | Template to merge into `~/.codex/config.toml` ([notes](codex/README.md)) |
| `tools/agent_cost.py` | Estimates spend from local session logs; no network, standard library only |
| `tools/prices.json` | $/1M-token rates the estimator uses - **replace with your provider's rates** |

## Quick start

1. **Measure.** Put your Bedrock rates in `tools/prices.json`, then:
   ```bash
   python3 tools/agent_cost.py claude --budget 2000
   python3 tools/agent_cost.py codex
   ```
   This covers one machine only. The authoritative figure is AWS Cost Explorer: filter to Amazon Bedrock and group by usage type to see input, output, cache-write and cache-read separately.
2. **Apply.** Back up your current files first:
   - Copy `claude/settings.json` over `~/.claude/settings.json`, keeping your own AWS lines (`AWS_REGION`, `AWS_PROFILE`, `awsAuthRefresh`) and `permissions`.
   - Merge `codex/config.toml` into `~/.codex/config.toml`, keeping your provider, auth and MCP sections.
   - Fill in the `<...>` placeholders.
3. **Verify.**
   - Claude: `/status` shows the model and provider. After a few turns, the "Prompt cache" line in `/usage` should say `1h TTL`.
   - Codex: `/status` shows the model and token usage.

## Where the money goes

- **Every turn re-sends the whole conversation.** Cached re-reads are cheap per token, but they scale with context size × number of turns, so a long session gets more expensive with every message.
- **Every new token is written to the cache once.** That costs 1.25× the input price with a 5-minute cache lifetime, or 2× with a 1-hour lifetime.
- **After an idle gap longer than the cache lifetime, the next turn rewrites the entire context.** On Bedrock the default lifetime is 5 minutes, so a meeting or a reading break triggers this.
- **Thinking and reasoning tokens are billed as output**, the most expensive token type.

Example from one heavy-use machine (Claude Code, October, at list prices):

| Part of the bill | Share |
|---|---|
| Cache writes | 57 % |
| Cache reads | 31 % |
| Output | 12 % |

71 % of the cache-write spend came from just 15 full-context rebuilds after idle gaps or compactions.

Anthropic's docs put the enterprise average at about $13 per developer per active day ($150-250 a month), with 90 % of users under $30 a day. If you're well above that, look at configuration first.

## Levers, biggest first

| # | Lever | Claude Code | Codex |
|---|---|---|---|
| 1 | Default to the mid-tier model; switch up per session | `ANTHROPIC_MODEL` = Sonnet 5.5, `/model opus` when needed | `model` = cheaper model, `/model` when needed |
| 2 | Fresh session per task and after breaks | `/clear` | `/new` |
| 3 | Cap context growth | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000` | `model_auto_compact_token_limit = 150000` |
| 4 | Don't pay a rebuild after every break | `ENABLE_PROMPT_CACHING_1H=1` | caching is provider-managed |
| 5 | Reasoning depth and answer length | `effortLevel: medium` | `model_reasoning_effort = "medium"`, `model_verbosity = "low"` |
| 6 | Helper agents | `CLAUDE_CODE_SUBAGENT_MODEL`, no agent teams | `[agents]` cap of 2, subagent effort `low` |
| 7 | Fixed overhead | CLAUDE.md under 200 lines, unused MCP servers off | small AGENTS.md, `apps = false` if unused |

## Habits

- **One task per session.** It's cheaper, and the results are easier to reproduce.
- **Don't resume a big session after a meeting.** Start fresh with a short brief instead.
- **Switch models at the start of a session.** The cache is tied to the model, so switching mid-session rebuilds it.
- **Convert PDFs to text once** (`pdftotext -layout`) and have the agent search the sections it needs.
- **Stop the agent early** (Esc) when it heads the wrong way. Wasted turns are the most expensive ones.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Sources

- Claude Code costs: https://code.claude.com/docs/en/costs
- Claude Code on Bedrock: https://code.claude.com/docs/en/amazon-bedrock
- Claude Code environment variables: https://code.claude.com/docs/en/env-vars
- Codex config reference: https://developers.openai.com/codex/config-reference
- Codex slash commands: https://developers.openai.com/codex/cli/slash-commands
- Bedrock pricing: https://aws.amazon.com/bedrock/pricing/
