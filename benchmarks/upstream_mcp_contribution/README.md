# Upstream MCP contribution reproduction

This holds an on-demand reproduction of the checks behind the open-source bonus
contribution: upstream [Issue #159](https://github.com/acryldata/mcp-server-datahub/issues/159)
and [PR #160](https://github.com/acryldata/mcp-server-datahub/pull/160) in
`acryldata/mcp-server-datahub` (evidence **E-11** / **E-18**).

## Generate the receipt

```bash
make reproduce-upstream-mcp-pr
```

This clones the public fork branch at the pinned commit
`fe49bac7aac3f226ca680f88167e0bb48a7ba651`, verifies the branch HEAD still matches it,
then runs the PR's own `pytest`, `ruff check`, scoped `ruff format --check`, and `mypy`
gates, writing `pr-160-reproduction-receipt.json` here.

The receipt is **not committed by default**: it requires cloning and executing an
external, mutable repository over the network, so it is generated on demand rather than
wired into `make judge-check` or CI.

## What it does and does not establish

It records only that the pinned commit's own checks reproduce on a fresh clone at
reproduction time. It is **not** upstream CI, **not** maintainer review, and **not** a
merge or acceptance claim. **PR #160 remains open and unmerged.**
