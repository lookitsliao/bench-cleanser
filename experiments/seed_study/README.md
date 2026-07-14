# Synthetic evidence-acquisition seed study

This pilot exercises the complete local acquisition path against eight known
JavaScript candidates. It intentionally contains a weak targeted test, a stronger
inherited suite, and an oracle-hardening suite so failures of “execution equals
truth” are observable. Full execution is repeated in separate acquisitions.

It is an **integration experiment, not empirical validation of the research
thesis**. The candidates are hand-authored, the task is synthetic, and truth is
specification-derived rather than blinded expert adjudication. Its purpose is to
catch plumbing, provenance, isolation, replicate, and metric defects before
spending Docker/LLM budget on a real candidate corpus.

Local run:

```bash
python experiments/seed_study/run_seed_study.py \
  --runtime local \
  --output-dir /tmp/bench-cleanser-seed-local
```

Containerized run using an already-pulled image and explicit daemon URI:

```bash
python experiments/seed_study/run_seed_study.py \
  --runtime docker \
  --docker-host unix:///path/to/docker.sock \
  --image node:18 \
  --output-dir /tmp/bench-cleanser-seed-docker
```

The Docker path uses `--pull never`, disables networking, mounts each candidate
read-only, uses a read-only container filesystem plus bounded `/tmp`, drops
capabilities, enables `no-new-privileges`, and bounds processes, memory, and CPU.
The acquisition runner itself is not a sandbox; the isolation comes from this
explicit Docker invocation.

`report.json` contains the raw `EvidenceObservation` records, measured local
costs, fixture digest, runtime/image identity, modality confusion counts, and
prominent limitations. Acquisition artifacts are stored beside it. Do not commit
those machine-local artifacts as publication evidence.
