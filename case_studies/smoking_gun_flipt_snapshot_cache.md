# Smoking Gun Case Study: flipt-io/flipt Snapshot Cache Deletion

## Instance Identification

| Field | Value |
|---|---|
| Instance ID | `instance_flipt-io__flipt-86906cbfc3a5d3629a583f98e6301142f5f14bdb-v6bea0cc3a6fc532d7da914314f2944fc1cd04dee` |
| Repository | `flipt-io/flipt` |
| Language | Go |
| Pipeline Version | v5 (with requirements+interface parsing) |
| Severity | **SEVERE** |
| Labels | `wide_tests` (0.95), `test_mutation` (0.92), `scope_creep` (0.98), `approach_lock` (0.78) |
| V4 Severity | SEVERE (confirmed across pipeline versions) |

---

## 1. Problem Statement (Agent-Visible)

The agent receives ONLY this narrow description:

> Snapshot cache does not allow controlled deletion of references
>
> The snapshot cache lacked a way to remove references explicitly. This caused non-fixed references to remain even when no longer needed, and made it impossible to distinguish between removable and protected references.
>
> **Expected behavior:** Fixed references cannot be deleted and remain accessible. Non-fixed references can be deleted and are no longer accessible after removal.
>
> **Current behavior:** All references remain in the cache indefinitely, with no way to remove them selectively.

**Scope implied by problem statement:** Add a Delete method to the snapshot cache that distinguishes fixed from non-fixed references. Nothing about configuration schemas, CSRF, HTTP routing, or analytics.

---

## 2. Requirements (Evaluation-Only, Withheld from Agent)

The requirements field elaborates the cache deletion semantics:

- Maintain fixed vs non-fixed reference distinction
- Public Delete operation: fixed references return error containing `"cannot be deleted"`
- Non-fixed references: delete succeeds, lookup returns absent
- Garbage collection: only remove underlying snapshot when no other reference maps to it
- Thread safety for concurrent access
- `listRemoteRefs` method to enumerate remote branches/tags

**Key observation:** Requirements are coherent with the problem statement -- they describe cache deletion and remote ref listing. No mention of CSRF, config schema, or HTTP middleware.

---

## 3. Interface (Evaluation-Only, Withheld from Agent)

New public interface specified:

- `listRemoteRefs` method on `*SnapshotStore` in `internal/storage/fs/git/store.go`
- Returns `map[string]struct{}` of branch/tag short names from origin remote

**Key observation:** Interface is scoped to the git store layer. No configuration or CSRF interfaces.

---

## 4. The F2P Test Suite: Where Contamination Lives

The F2P test suite contains **21 tests**. Here is the critical mismatch:

### Tests Related to Stated Problem (cache deletion + remote refs)
None of the 21 F2P test names relate to snapshot cache deletion or remote ref listing.

### Tests Actually in F2P Suite
| Test | Domain | Relation to Problem |
|---|---|---|
| `TestAnalyticsClickhouseConfiguration` | Analytics config | UNRELATED |
| `TestAnalyticsPrometheusConfiguration` | Analytics config | UNRELATED |
| `TestAuditEnabled` | Audit config | UNRELATED |
| `TestWithForwardPrefix` | HTTP routing | UNRELATED |
| `TestRequiresDatabase` | DB config | UNRELATED |
| `TestJSONSchema` | Config schema validation | UNRELATED |
| `TestScheme` | Config | UNRELATED |
| `TestCacheBackend` | Cache config | TANGENTIAL |
| `TestTracingExporter` | Tracing config | UNRELATED |
| `TestDatabaseProtocol` | DB config | UNRELATED |
| `TestLogEncoding` | Logging config | UNRELATED |
| `TestLoad` | Config loading | UNRELATED (modified) |
| `TestServeHTTP` | HTTP/CSRF | UNRELATED |
| `TestMarshalYAML` | Config serialization | UNRELATED |
| `Test_mustBindEnv` | Env binding | UNRELATED |
| `TestGetConfigFile` | Config file resolution | UNRELATED (modified) |
| `TestStructTags` | Config struct tags | UNRELATED (modified) |
| `TestDefaultDatabaseRoot` | DB config | UNRELATED |
| `TestFindDatabaseRoot` | DB config | UNRELATED |
| `TestStorageConfigInfo` | Storage config | UNRELATED |
| `TestIsReadOnly` | Storage config | UNRELATED |

**Zero of the 21 F2P tests directly test cache deletion or remote ref listing.** Every single F2P test targets configuration/schema behavior from a different part of the same PR.

---

## 5. Gold Patch Analysis: Scope Expansion

The gold patch modifies files across two unrelated domains:

### Domain 1: Cache Deletion (Requested)
- `internal/storage/fs/cache.go` -- Delete method on SnapshotCache
- `internal/storage/fs/git/store.go` -- listRemoteRefs implementation

### Domain 2: CSRF/Config (Not Requested)
- `config/flipt.schema.cue` -- Adds `secure` boolean under CSRF
- `internal/cmd/http.go` -- Changes HTTP CSRF handling
- `internal/config/authentication.go` -- Adds CSRF `Secure` config field
- `internal/config/config.go` -- Sets `Secure: true` default

The pipeline marks the CSRF/config hunks as UNRELATED with 0.98 confidence. These are behavioral changes -- not imports or whitespace.

---

## 6. Test Mutation: Pre-Existing Tests Modified

Three pre-existing configuration tests were silently modified in the same PR:

| Test | Modification | Alignment |
|---|---|---|
| `TestLoad` | Added assertion for `Secure: true` config field | MISALIGNED -- tests CSRF config, not cache deletion |
| `TestGetConfigFile` | Modified expectations | MISALIGNED |
| `TestStructTags` | Modified struct tag assertions | MISALIGNED |

These tests existed before the PR. The PR author added assertions for the new CSRF `Secure` field into these existing tests, making them fail-to-pass for the benchmark. This is the textbook `test_mutation` pattern: a legitimate-looking test is repurposed to enforce out-of-scope behavior.

---

## 7. Approach Lock: Circular Test-Patch Dependency

Cross-reference analysis detected **18 circular dependencies**:

```
F2P test "TestServeHTTP" -> exercises UNRELATED hunk in internal/cmd/http.go (CSRF)
F2P test "TestJSONSchema" -> exercises UNRELATED hunk in config/flipt.schema.cue
F2P test "TestLoad" -> exercises UNRELATED hunk in internal/config/config.go
F2P test "TestStorageConfigInfo" -> exercises UNRELATED hunks
F2P test "TestIsReadOnly" -> exercises UNRELATED hunks
...
```

An agent that perfectly implements cache deletion and remote ref listing will **still fail** all 21 F2P tests unless it ALSO reproduces the unrelated CSRF/config changes from the gold patch. The tests are coupled to out-of-scope code, creating a circular dependency.

---

## 8. Contamination Diagnosis

This task exhibits a **compound contamination pattern**:

1. **The PR bundled two unrelated features** -- cache deletion AND CSRF config changes
2. **SWE-bench Pro extracted the narrow problem** (cache deletion only) but kept the **full PR's test suite** as F2P
3. **The F2P tests don't test the stated problem at all** -- they test the CSRF/config changes
4. **Pre-existing tests were modified** to enforce the new CSRF behavior

An agent can only pass by either:
- Memorizing the gold patch (including CSRF changes it has no reason to make)
- Getting lucky with implementation side effects

This is not a borderline case. The problem asks about cache deletion; the tests check CSRF configuration. The mismatch is total.

---

## 9. V4 vs V5 Comparison

| Metric | V4 (no requirements/interface) | V5 (with requirements/interface) |
|---|---|---|
| Severity | SEVERE | SEVERE |
| approach_lock | 0.98 | 0.78 |
| wide_tests | 0.95 | 0.95 |
| test_mutation | 0.90 | 0.92 |
| scope_creep | 0.99 | 0.98 |
| weak_coverage | 0.96 | -- (dropped) |

The SEVERE classification is **confirmed across both pipeline versions**. Adding requirements/interface context actually *removed* the `weak_coverage` label (the task IS well-specified; the tests just don't test what it specifies). The core finding is unchanged: the F2P suite tests CSRF config, not cache deletion.

---

## 10. Conclusion

**Classification: GENUINE SEVERE CONTAMINATION**

This task is unfairly evaluable. A correct solution to the stated problem will fail 100% of F2P tests because every test targets unrelated CSRF/configuration behavior from the same PR. The only path to passing is reproducing the gold patch's out-of-scope changes -- which requires either memorization or leakage.
