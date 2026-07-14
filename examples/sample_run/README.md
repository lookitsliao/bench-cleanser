# Sample run

This directory contains three hand-picked reports from an earlier
`bench-cleanser` run against SWE-bench Pro plus the aggregate statistics from
that source run. It lets a new reader inspect report JSON without spending LLM
tokens or configuring an OpenAI-compatible endpoint.

```
sample_run/
├── reports/                       3 extracted ContaminationReport JSONs
└── summary_stats.json             aggregate distribution from the source run
```

All three extracted reports are `MINOR` weak-coverage examples. They are useful
for inspecting evidence fields, not for comparing severity classes.

See [Outputs](../../README.md#outputs--what-comes-out-of-a-run) in the top-level
README for the current report shape.

> These artifacts predate the current provenance envelope and are illustrative
> only. They do not establish benchmark-wide prevalence, classifier accuracy,
> or reproducibility. Publication-grade samples must be regenerated with the
> repaired alpha and accompanied by dataset/model/prompt/environment identity.
