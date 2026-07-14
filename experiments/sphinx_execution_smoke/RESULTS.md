# Sphinx 8475 feasibility results

## Observed outcomes

| Variant | Role | P2P per repeat | F2P across repeats | Complete source-tree note |
|---|---|---:|---:|---|
| `baseline` | base + oracle test control | 17/17, 17/17, 17/17 | failed, failed, failed | distinct base tree |
| `gpt5` | candidate | 17/17, 17/17, 17/17 | passed, passed, passed | byte-identical to prepared gold tree |
| `kimi_k2` | candidate | 17/17, 17/17, 17/17 | passed, passed, passed | gold functional change plus four unscored root scripts |
| `claude_4_sonnet` | candidate | 17/17, 17/17, 17/17 | passed, passed, passed | gold functional change plus three unscored root scripts |
| `gold` | canonical sanity control | 17/17, 17/17, 17/17 | passed, passed, passed | byte-identical to prepared GPT-5 tree |

Across the 15 observations, 255/255 P2P checks passed. The base failed the
target 3/3 times; candidates passed 9/9 candidate-target checks; gold passed
3/3.

## What this adds

- A second repository and task family can be brought up without a container,
  using exact source, patch, test, runtime, and dependency identities.
- Complete prepared trees were hashed before and after each phase, while
  source files remained read-only.
- A network-sensitive test set exposed a real substrate decision: public egress
  and localhost fixtures needed separate proxy policies.
- Raw patch size is misleading here. The candidate patches range from 1,072 to
  25,646 bytes, but all three execute the same functional production change;
  Kimi K2 and Claude mainly add unscored scripts.

## What this does not add

This task cannot estimate a routing frontier or distinguish candidate quality:
all candidates share the gold implementation and pass. It does not compare a
semantic verifier against execution, measure costs representative of a task
population, validate an official Linux/container harness, or establish
candidate truth. This is not the official SWE-bench harness or environment
image. The three public-link P2P tests also depend on mutable network responses.

The acquisition was revised after unscored dependency, basetemp, and file-mode
bring-up failures. Those revisions are why the final record is explicitly
retrospective feasibility evidence rather than prospective evidence.
