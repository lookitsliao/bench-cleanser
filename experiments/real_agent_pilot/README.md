# Real-agent contrastive pilot

This is the first non-synthetic integration check for the verification research
program. It pins four public OpenHands/Qwen3-Coder-30B-A3B SWE-bench Verified
candidates: two reported resolved and two reported unresolved. Patch,
evaluation report, and trajectory bytes stay in the public SWE-bench submission
bucket; `cohort.json` records their URLs, sizes, and SHA-256 identities.
The submission metadata itself declares `checked: false`; this pilot therefore
does not treat the hosted reports as independently audited semantic truth.

Run it from the repository root:

```bash
python experiments/real_agent_pilot/run_pilot.py \
  --artifact-dir /tmp/bench-cleanser-real-agent-pilot \
  --fetch \
  --output /tmp/bench-cleanser-real-agent-pilot-report.json
```

The fetch path accepts only HTTPS objects from the declared SWE-bench S3 host,
bounds each read to its pinned size, verifies the digest before publication,
and re-verifies local bytes on every analysis. No LLM/API credential is used.

## What this does and does not establish

All four trajectories end in a `task_completed=true` finish event using explicit
success language. Official execution resolves only two. This is a concrete
counterexample to using an agent's confident final narrative as a rollout
verifier. It also exercises real candidate patches through the reference-free
manifest and risk-profile code.

It is a deliberately contrastive convenience sample from one Python repository,
one scaffold/model, and one pass@1 submission. Cases were selected to include
both outcomes; they were not sampled randomly. The hosted evaluation reports are
consumed rather than independently re-executed, and labels are not blinded or
oracle-hardened. The resulting 2/4 false-accept count is therefore not a
population estimate, calibration result, execution-routing result, or evidence
for H1-H6. See `RESULTS.md` for the exact interpretation.
