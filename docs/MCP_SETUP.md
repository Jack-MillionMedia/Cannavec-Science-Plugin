# Connecting the Cannavec MCP (semantic KB + flywheel)

The five research commands (`/research`, `/ask`, `/discover`, `/verify`, `/rigor`)
work **without** this step. Connecting the Cannavec MCP adds two things on top:
**semantic/vector recall** over the curated cannabis KB, and the **chunk
flywheel** (`audit-mcp --chunks`) that turns real usage into a research backlog.

> **Authoritative source:** your Cannavec **dashboard** shows your API key and a
> copy-paste one-click command tailored to your account:
> **<https://cannavec.ai/dashboard/mcp-setup>** (log in first). The steps below are
> the standard manual setup; if the dashboard shows a different command for your
> account, prefer the dashboard's.

**Server endpoint:** `https://cannavec.ai/api/mcp` · **Transport:** HTTP ·
**Auth:** `Authorization: Bearer <token>` (your API key, or an OAuth-issued token).

---

## 1. Get your API key

1. Sign in at **<https://cannavec.ai>** (create an account / pick a plan if you
   don't have one).
2. Open **Dashboard → MCP Setup** (<https://cannavec.ai/dashboard/mcp-setup>).
3. Copy your **API key** (and, if shown, the ready-made one-click command for
   your client — that's the easiest path).

Keep the key private — it authenticates your usage. Never commit it.

---

## 2. Claude Code (the primary path for this plugin)

**Export the key in the same shell first**, so the `Bearer` header resolves —
this is the #1 gotcha (an unset variable sends an *empty* token and the server
returns **401**):

```bash
export CANNAVEC_API_KEY=<your-cannavec-key>
claude mcp add --transport http cannavec https://cannavec.ai/api/mcp \
  --header "Authorization: Bearer ${CANNAVEC_API_KEY}"
```

(Or paste your literal key in place of `${CANNAVEC_API_KEY}`.)

Confirm it connected:

```bash
claude mcp list          # 'cannavec' should be listed
```

Inside Claude Code, run `/mcp` to see connection status; once connected, the
`search_cannabis_kb` tool is available and the `/research` command will use it
automatically. If your dashboard offers an **OAuth** command instead (no manual
key), use that and authenticate in-session via `/mcp`.

> The plugin's own CLI reads your key from `~/.cannavec/credentials` (run
> `python3 -m cannavec_science setup`) — but the `claude mcp add` line above is
> evaluated by your **shell**, so the key must be exported there too.

---

## 3. Claude Desktop

Claude Desktop connects to remote MCP servers via `claude_desktop_config.json`
(Settings → Developer → Edit Config). Your **dashboard provides the exact JSON
snippet for your account** — paste that. The standard shape for a remote HTTP MCP
with a Bearer header looks like:

```json
{
  "mcpServers": {
    "cannavec": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://cannavec.ai/api/mcp",
        "--header",
        "Authorization: Bearer YOUR_CANNAVEC_API_KEY"
      ]
    }
  }
}
```

Replace `YOUR_CANNAVEC_API_KEY` with your key, save, and **restart Claude
Desktop**. (If the dashboard shows a different snippet for your account, use it.)

---

## 4. Claude.ai (web)

Add Cannavec as a **Custom Connector**: Settings → Connectors → Add custom
connector → point it at `https://cannavec.ai/api/mcp`, then authenticate (the
dashboard notes Google sign-in is supported, so no manual key is needed for the
web app). Follow the exact steps shown in your dashboard.

---

## 5. Verify it works

In Claude Code, after connecting, ask a cannabis question and confirm the model
calls `search_cannabis_kb`. Or exercise the flywheel directly (offline-safe):

```bash
python3 -m cannavec_science audit-mcp --query "CBD for epilepsy" --rigorous --no-corpus \
  --chunks '[{"doc_id":"cbd_epilepsy","h2_anchor":"Efficacy","text":"CBD is a miracle cure that is 100% effective and completely safe for all seizures.","citations":[]}]'
```

A `✗ MISLEADING` verdict means the rigorous evaluator is working.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **401 Unauthorized** | The `Bearer` token is empty or wrong. Re-`export CANNAVEC_API_KEY=…` in the same shell before `claude mcp add`, or paste the literal key. Re-copy the key from the dashboard. |
| `cannavec` not in `claude mcp list` | The add command failed — re-run it; check the endpoint is exactly `https://cannavec.ai/api/mcp`. |
| Model never calls `search_cannabis_kb` | The MCP isn't connected for this session — run `/mcp` in Claude Code and reconnect; the five commands still work without it. |
| Desktop connector doesn't load | Ensure `npx`/Node is installed; restart Claude Desktop after editing `claude_desktop_config.json`; prefer the dashboard's exact snippet. |
| Slow first live `discover` | Unrelated to the MCP — that's PubMed rate-limiting; add your free NCBI key via `python3 -m cannavec_science setup`. |

Full setup specifics for your account always live at
**<https://cannavec.ai/dashboard/mcp-setup>**.
