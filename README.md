<a href="https://faxforagents.com"><img src="https://faxforagents.com/brand/logo-512.png" width="88" alt="Fax for Agents"></a>

# Fax for Agents for Cursor

A Cursor plugin for [Fax for Agents](https://faxforagents.com): the hosted MCP server (17 tools) plus the
fax-for-agents skill. Send and receive faxes from Cursor.

[Website](https://faxforagents.com) ·
[Docs](https://faxforagents.com/docs/) ·
[MCP setup](https://faxforagents.com/docs/mcp-setup/) ·
[API reference](https://faxforagents.com/docs/api/) ·
[Dashboard](https://app.faxforagents.com) ·
[Pricing](https://faxforagents.com/pricing/) ·
[Changelog](https://faxforagents.com/changelog/) ·
[Affiliate program](https://faxforagents.com/affiliates/) ·
[GitLab](https://gitlab.com/faxforagents/cursor-plugin)

[![CI](https://img.shields.io/github/actions/workflow/status/faxforagents/cursor-plugin/ci.yml?branch=main&label=ci)](https://github.com/faxforagents/cursor-plugin/actions/workflows/ci.yml)
[![MIT licence](https://img.shields.io/badge/licence-MIT-1f6feb)](https://github.com/faxforagents/cursor-plugin/blob/main/LICENSE)
[![MCP](https://img.shields.io/badge/MCP-17%20tools-6b4fbb)](https://faxforagents.com/mcp/)

Fax for Agents is a fax API, a hosted MCP server and SDKs built so AI agents can send and receive
faxes. It is made by JSB Holdings LLC and built by [Synapse](https://synapsereality.io/).

This repository is a plugin in Cursor's plugin format. [`.cursor-plugin/plugin.json`](.cursor-plugin/plugin.json)
names it and declares one variable, `FAXFORAGENTS_API_KEY`. [`mcp.json`](mcp.json) connects Cursor to the
hosted server at `https://mcp.faxforagents.com/mcp/` and sends that key as a bearer token.
[`skills/fax-for-agents/`](skills/fax-for-agents/SKILL.md) is the manual the agent reads when a task is
about a fax. It holds the setup, the safe send order, the approvals rule, the error codes and the rule that text from a fax is data.
The skill is maintained in [faxforagents/skills](https://github.com/faxforagents/skills). Its `SKILL.md`,
`LICENSE` and `references/` are copied here unchanged.

The plugin is configuration and Markdown only. It runs no code of its own.

## Install

Cursor loads a plugin from a folder under `~/.cursor/plugins/local`. On an Enterprise plan, an admin has to
turn on **Allow Local Plugin Imports** first.

1. Clone this repository there.

   ```bash
   git clone https://github.com/faxforagents/cursor-plugin ~/.cursor/plugins/local/faxforagents
   ```

2. Restart Cursor, or run **Developer: Reload Window**.
3. Open **Customize** and check that the `fax-for-agents` skill and the `faxforagents` MCP server are listed.
4. Set **Fax for Agents API key** to an `ffa_test_...` key. Cursor keeps plugin variables in the dashboard
   under **Plugins**, **Configure**, and fills `${FAXFORAGENTS_API_KEY}` in `mcp.json` from there.
5. Ask the agent to send a one page test fax to `+15550000001`. It calls `prepare_fax`, `quote_fax`,
   `send_approved_fax` and then `get_fax_status`.

Cursor shows the server as `plugin-faxforagents-faxforagents` in approval prompts.

A team on a Teams or Enterprise plan can import this repository as a team marketplace instead, from
**Dashboard**, **Plugins & MCPs**, **Add Marketplace**, **Import from Repo**. Cursor shares a team plugin's
variables with the whole team, so give that plugin an API key of its own.

## Keys

A test key (`ffa_test_...`) reaches the sandbox only, and no real fax is sent. In the sandbox the
destination number picks the outcome. The skill lists those numbers. A live key (`ffa_live_...`) sends
real faxes and spends the prepaid wallet. Keys are created at <https://app.faxforagents.com/app/keys>.

With `mcp.json`, Cursor sends the key to `mcp.faxforagents.com` only. The stdio alternative below sends it to
`api.faxforagents.com` only. Keep it in the plugin variable, never in a file you commit.

## The tools

| Tool | Does | Scope |
|---|---|---|
| `get_guide` | The manual, whole or by section. Works without a key | none |
| `get_fax_capabilities` | Limits, routes, formats, pricing and the scopes of the key | `account:read` |
| `prepare_fax` | A document from text, Markdown, HTML or a completed upload. Never sends | `document:write` |
| `get_fax_document` | One prepared document by id: page count, sha256, warnings, previews | `document:read` |
| `quote_fax` | The exact price of one document to one destination, with the policy verdict | `fax:quote` |
| `send_approved_fax` | Queue a quoted and authorized fax. It answers with the queued state | `fax:send` |
| `get_fax_status` | State, attempts and the evidence for the outcome | `fax:read` |
| `list_faxes` | Newest first, by state, with a cursor | `fax:read` |
| `get_fax_balance` | Available and held balance | `billing:read` |
| `cancel_fax` | Cancel while queued, best effort once sending | `fax:cancel` |
| `request_card_payment` | Ask a person to pay for one quoted fax by card, with no wallet balance | `fax:send` |
| `get_card_payment_status` | One card payment order: paid or not, what was charged, the fax it sent | `fax:read` |
| `request_human_review` | With `quote_id`, ask a person to approve that send. Without it, ask for help | `approval:request` |
| `get_review_status` | Where one approval or help request stands | `approval:read` |
| `list_inbox` | Received faxes, metadata only | `inbox:read` |
| `read_inbound_fax` | One received fax, its text and latest extraction as data | `inbox:read` |
| `extract_fax_data` | OCR a received fax or a document, extract schema fields with citations | `document:extract` |

A live send needs a human approval bound to that exact quote, or a delegated policy written by the
account owner. The agent's API key can never approve its own send. Text that came out of a received fax
is data from whoever sent it, never an instruction to the agent.

## Running the server on your machine instead

The hosted server needs no install. [`alternatives/stdio.mcp.json`](alternatives/stdio.mcp.json) runs
the server over stdio with `npx -y faxforagents-mcp@0.5.9` (Node 20 or later). To use it, replace
`mcp.json` with that file. It reads the key from the same `FAXFORAGENTS_API_KEY` variable.

Release 0.5.9 has the same 17 tools as the hosted server. The package source is at
[faxforagents/mcp](https://github.com/faxforagents/mcp).

## Privacy and support

Privacy policy: <https://faxforagents.com/privacy>. Terms: <https://faxforagents.com/terms>.
Support: hello@faxforagents.com, or an issue on this repository. Security reports go to the same
address, see [SECURITY.md](SECURITY.md).

## Working on this repository

```bash
python3 scripts/check_plugin.py   # manifest fields and types per Cursor's schema, both MCP configs, the skill, the copy
sh scripts/truthcheck.sh          # the copy states only what the product ships
```

CI runs both and also compares the vendored skill with `faxforagents/skills` main.

## Licence

MIT. See [LICENSE](LICENSE).
