# Claim-level primary-PDF ledger

[`literature.claims.json`](literature.claims.json) binds 35 central novelty and
baseline claims from 26 exact arXiv PDFs to version identities, byte counts,
SHA-256 digests, pages, and sections. The mappings are paraphrases of
author-reported methods, results, or limitations; they are not independent
replications.

This closes only part of the paper-grade literature gap:

- 26 of the 70 metadata-locked papers have claim-level PDF mappings;
- the review was machine-assisted and has not been human-confirmed;
- reviewer/tool identity, prompt/protocol, and quote-level context are not yet
  preserved as publication-grade provenance;
- PDFs are not checked into Git or redistributed by this repository; and
- every substantive paper claim outside this ledger still needs the same
  page-level review before a research release.

The 26 reviewed papers cover the closest boundaries: R2E-Gym, LEC, SWE-RM,
SWE-World, EGSS, SWE-ZERO to SWE-HERO, TwinRouterBench, consequence-aware
compute allocation, To Run or Not to Run, Dockerless, Bayesian Control for
Coding Agents, SCoRE, Conformal Selective Acting, the joint selective
certificate, two controlled bug-report
studies, trajectory-guided specification refinement, version-conditioned
benchmark invalidity, SCATE's adaptive test-generation policy, test-file oracle
signals, verifier co-evolution, false-success judging, scaffold evolution,
reproduction-test generation, limits of code-only flakiness detection, and
temporal coding-agent failure analysis. The 17 papers added during the July 2026
review expansion were rendered at page level for visual review; all mappings
still require named human confirmation.

Validate ledger metadata against the exact literature lock:

```bash
python scripts/verify_claim_ledger.py
```

That command intentionally reports metadata-only partial validation. To verify
the actual PDF bytes, supply every exact file and require complete byte
coverage:

```bash
python scripts/verify_claim_ledger.py \
  --pdf 2504.07164v1=/evidence/pdfs/2504.07164v1.pdf \
  --pdf 2512.01556v3=/evidence/pdfs/2512.01556v3.pdf \
  --pdf 2512.21919v1=/evidence/pdfs/2512.21919v1.pdf \
  --pdf 2602.03419v1=/evidence/pdfs/2602.03419v1.pdf \
  --pdf 2602.05242v1=/evidence/pdfs/2602.05242v1.pdf \
  --pdf 2603.24704v1=/evidence/pdfs/2603.24704v1.pdf \
  --pdf 2604.01496v2=/evidence/pdfs/2604.01496v2.pdf \
  --pdf 2605.18859v2=/evidence/pdfs/2605.18859v2.pdf \
  --pdf 2605.20270v1=/evidence/pdfs/2605.20270v1.pdf \
  --pdf 2606.04402v1=/evidence/pdfs/2606.04402v1.pdf \
  --pdf 2606.08517v1=/evidence/pdfs/2606.08517v1.pdf \
  --pdf 2606.09863v1=/evidence/pdfs/2606.09863v1.pdf \
  --pdf 2606.18168v1=/evidence/pdfs/2606.18168v1.pdf \
  --pdf 2606.24453v1=/evidence/pdfs/2606.24453v1.pdf \
  --pdf 2606.26300v2=/evidence/pdfs/2606.26300v2.pdf \
  --pdf 2606.26978v1=/evidence/pdfs/2606.26978v1.pdf \
  --pdf 2606.28436v1=/evidence/pdfs/2606.28436v1.pdf \
  --pdf 2607.03691v1=/evidence/pdfs/2607.03691v1.pdf \
  --pdf 2607.07593v1=/evidence/pdfs/2607.07593v1.pdf \
  --pdf 2607.07882v1=/evidence/pdfs/2607.07882v1.pdf \
  --pdf 2607.08983v1=/evidence/pdfs/2607.08983v1.pdf \
  --pdf 2607.09007v1=/evidence/pdfs/2607.09007v1.pdf \
  --pdf 2607.09123v1=/evidence/pdfs/2607.09123v1.pdf \
  --pdf 2607.09345v1=/evidence/pdfs/2607.09345v1.pdf \
  --pdf 2607.09510v1=/evidence/pdfs/2607.09510v1.pdf \
  --pdf 2607.09553v1=/evidence/pdfs/2607.09553v1.pdf \
  --require-all-pdfs
```

An eventual publication bundle should preserve those exact PDFs when
redistribution is permitted, or preserve signed retrieval receipts and digests
when it is not. A named human reviewer must confirm every mapping and record any
correction without overwriting the earlier ledger version.
