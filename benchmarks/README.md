# LedgerLens benchmarks

Benchmarks in this directory separate three different evidence classes:

1. **Deterministic fixture checks** — parser, mapping, and policy correctness on
   public synthetic fixtures.
2. **Live infrastructure smoke measurements** — latency and health of a pinned
   DataHub OSS and official MCP deployment.
3. **Optional model-assisted phrasing measurements** — never used as the source
   of truth for factual selection or claim status.

No benchmark here independently validates a source finding or demonstrates
capability uplift. Every result remains `candidateOnly: true` and
`canClaimAGI: false`.

Run the live MCP benchmark after DataHub OSS and the MCP server are healthy:

```bash
uv run python benchmarks/live_mcp_benchmark.py \
  --output benchmarks/results/live-mcp.json
```

Run the optional bounded model transport check only when a key is explicitly
available. (`020s` / `SOPHIA_020S_KEY` is the internal codename for the
OpenAI GPT-5.6-compatible transport; the model-attribution docs name it OpenAI GPT-5.6.)

```bash
SOPHIA_020S_KEY=... uv run python benchmarks/020s_smoke.py \
  --output benchmarks/results/020s-smoke.json
```
