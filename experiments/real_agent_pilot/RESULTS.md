# Real-agent contrastive pilot results

**Status:** source-locked integration result, not research validation.

The pinned cohort contains four public OpenHands/Qwen3-Coder-30B-A3B patches
for Astropy from the SWE-bench Verified submission. The public trajectory for
every candidate ends with `task_completed=true` and success/fix language. The
hosted SWE-bench evaluation reports resolve two candidates and reject two:

| Instance | Official outcome | F2P success/failure | P2P success/failure | Patch-derived profile |
|---|---:|---:|---:|---|
| `astropy__astropy-12907` | resolved | 2 / 0 | 13 / 0 | 1 file, 2 changed lines, no test path |
| `astropy__astropy-13033` | unresolved | 0 / 1 | 20 / 0 | 9 files, 416 changed lines, test paths |
| `astropy__astropy-13453` | resolved | 1 / 0 | 9 / 0 | 4 files, 209 changed lines, test paths |
| `astropy__astropy-13977` | unresolved | 12 / 8 | 318 / 4 | 4 files, 256 changed lines, test paths |

Under the intentionally naive policy “accept a rollout when its own terminal
narrative says it completed successfully,” all four are accepted and two are
false accepts: **2 / 4 (50%) in this selected cohort**. The denominator must stay
attached. It is not a claim that agent self-reports have a 50% error rate in any
target population.

The useful observation is qualitative: execution distinguishes confident
rollouts here, but even that evidence is structured. One failure is obvious at
the sole target test; the other passes twelve target tests and hundreds of
regression tests while still failing eight target and four regression cases.
“The agent ran tests” and “many tests passed” are not terminal correctness
oracles.

## Limits

- Four contrastively selected cases, one repository, one model/scaffold.
- Reports were digest-verified but not independently re-executed, and the
  submission metadata declares `checked: false`.
- No semantic reward model, randomized acquisition, blinded adjudication,
  alternative-correct analysis, repeated execution, or hardened oracle.
- The reference-free risk profile is descriptive here; no routing threshold was
  fit or evaluated.
- This pilot supports the need for the study. It supports none of H1-H6 and no
  downstream SFT/RL/evaluation claim.
