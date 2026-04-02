# Smoking Gun Case Study: ansible/ansible iptables Chain Management

## Instance Identification

| Field | Value |
|---|---|
| Instance ID | `instance_ansible__ansible-3889ddeb4b780ab4bac9ca2e75f8c1991bcabe83-v0f01c69f1e2528b935359cfe578530722bca2c59` |
| Repository | `ansible/ansible` |
| Language | Python |
| Pipeline Version | v5 (with requirements+interface parsing) |
| Severity | **SEVERE** |
| Labels | `wide_tests` (0.94), `test_mutation` (0.96), `approach_lock` (0.86) |
| V4 Severity | SEVERE (confirmed across pipeline versions) |

---

## 1. Problem Statement (Agent-Visible)

> **iptables - added a chain_management parameter to control chain**
>
> I'm managing custom IPtables chains with Ansible-core from the devel branch on GitHub. Implementing chain creation and deletion would be helpful for users of Ansible-core as there's currently no direct support for managing user-defined chains in the iptables module. This would simplify automating advanced firewall setups and ensure idempotency in playbooks.
>
> Currently, the iptables module lacks built-in support for creating or deleting user-defined chains, making manual shell commands or complex playbooks necessary for chain management.

**Scope implied:** Add a `chain_management` boolean parameter. When true + `state=present`, create the chain. When true + `state=absent`, delete empty chains. Default is false -- existing behavior unchanged.

---

## 2. Requirements (Evaluation-Only, Withheld from Agent)

The requirements elaborate the chain management semantics:

- New boolean `chain_management` parameter, default `false`
- `chain_management=true` + `state=present` -> create chain if not exists
- `chain_management=true` + `state=absent` + only `chain`/`table` -> delete if exists and empty
- Idempotent: don't recreate existing chains
- Distinguish chain existence from rule presence
- Check mode support

**Key observation:** Requirements are strictly about chain creation/deletion behavior. No mention of modifying existing append/insert test behavior or internal subprocess call counts.

---

## 3. Interface (Evaluation-Only, Withheld from Agent)

New public interface:

- `check_rule_present(iptables_path, module, params)` -> `bool`
  - Checks whether a specific iptables rule exists in the given chain/table
- `push_arguments(iptables_path, action, params, make_rule)` -> `list`
  - Constructs the argument list for an iptables invocation similar to `construct_rule` but does not apply it

**Key observation:** Interfaces relate to the chain management feature. No mention of changing existing rule append/insert internals.

---

## 4. The F2P Test Suite: The Test Mutation Pattern

The F2P suite contains **14 tests**. The critical contamination is in the modified pre-existing tests:

### New Tests (Chain Management) -- ALIGNED
| Test | Purpose | Alignment |
|---|---|---|
| `test_chain_creation` | Create chain when `chain_management=true` | ALIGNED |
| `test_chain_creation_check_mode` | Check mode for chain creation | ALIGNED |
| `test_chain_deletion` | Delete chain when `chain_management=true`, `state=absent` | ALIGNED |
| `test_chain_deletion_check_mode` | Check mode for chain deletion | ALIGNED |
| `test_chain_deletion_chain_not_exist` | Delete non-existent chain | ALIGNED |
| `test_chain_deletion_non_empty` | Refuse to delete non-empty chain | ALIGNED |

These 6 new tests are directly related to the stated problem. They would pass with any correct implementation of chain management.

### Modified Pre-Existing Tests -- MISALIGNED (Test Mutations)
| Test | Original Purpose | Added Assertion | Problem |
|---|---|---|---|
| `test_append_rule` | Verify `-A` rule append | `assertEqual(run_command.call_count, 3)` | Enforces specific subprocess count |
| `test_append_rule_check_mode` | Verify append in check mode | `assertEqual(run_command.call_count, 2)` | Enforces specific subprocess count |
| `test_insert_rule` | Verify `-I` rule insert | `assertEqual(run_command.call_count, 3)` + `call_args_list[2]` | Enforces exact call sequence |
| `test_insert_rule_check_mode` | Verify insert in check mode | `assertEqual(run_command.call_count, 2)` | Enforces specific subprocess count |
| `test_remove_rule` | Verify `-D` rule removal | Modified assertions | Enforces internal details |
| ... | (additional modified tests) | | |

---

## 5. The Core Contamination: Implementation-Specific Assertions

The sneaky edits add assertions on `run_command.call_count` and `run_command.call_args_list[2]` to pre-existing tests. These assertions enforce the gold patch's **internal implementation details**:

### What the gold patch does internally
The gold patch adds a chain-existence check (`-L <chain>`) before every append/insert operation, even when `chain_management=false`. This changes the internal subprocess call count from 2 to 3 for standard rule operations.

### What the modified tests enforce
```python
# test_append_rule (pre-existing, MODIFIED)
self.assertEqual(run_command.call_count, 3)  # was 2 before PR
# The extra call is the chain-existence check added by the gold patch
```

### Why this is approach lock
The problem statement says `chain_management` defaults to `false` and existing behavior should be unchanged. But the gold patch's implementation choice -- always checking chain existence -- is an internal detail that alternative correct implementations may not share.

A valid alternative implementation could:
- Only check chain existence when `chain_management=true`
- Use a different check mechanism (parsing iptables output vs. running `-L`)
- Batch subprocess calls differently

Any of these would satisfy the stated requirements but **fail the modified pre-existing tests** because the subprocess call count would differ.

---

## 6. Approach Lock Evidence: Cross-Implementation Failure

Consider two correct implementations:

**Implementation A (Gold Patch Style):**
```
append_rule() -> [check_chain_exists, check_rule_exists, append_rule] = 3 calls
```

**Implementation B (Equally Valid):**
```
append_rule() -> [check_rule_exists, append_rule] = 2 calls
# Only checks chain existence when chain_management=true
```

Implementation B correctly adds `chain_management` support, creates/deletes chains when requested, and leaves existing behavior unchanged when `chain_management=false`. It satisfies every stated requirement and acceptance criterion.

But `test_append_rule` asserts `run_command.call_count == 3`, so Implementation B fails.

This is textbook approach lock: the tests enforce one valid implementation and reject others.

---

## 7. Contamination Diagnosis

This task exhibits the **test_mutation + approach_lock** compound pattern:

1. **6 new tests are legitimate** -- they test the requested chain management feature
2. **8 pre-existing tests were silently modified** to assert on internal implementation details
3. **The modifications enforce the gold patch's call sequence**, not the feature's observable behavior
4. **Alternative correct implementations will fail** because the tests lock the internal approach

The pipeline correctly identifies this as SEVERE because:
- `test_mutation` (0.96): Pre-existing tests modified with misaligned assertions
- `approach_lock` (0.86): Tests enforce implementation details, not behavior
- `wide_tests` (0.94): Modified tests assert beyond stated scope

---

## 8. V4 vs V5 Comparison

| Metric | V4 (no requirements/interface) | V5 (with requirements/interface) |
|---|---|---|
| Severity | SEVERE | SEVERE |
| wide_tests | 0.97 | 0.94 |
| test_mutation | 0.94 | 0.96 |
| approach_lock | 0.75 | 0.86 |

The SEVERE classification is **confirmed and strengthened** across pipeline versions. With full requirements context, the pipeline has higher confidence in `approach_lock` because it can confirm that no requirement asks for changes to existing append/insert behavior.

---

## 9. Conclusion

**Classification: GENUINE SEVERE CONTAMINATION**

This task contains a well-hidden contamination pattern. The 6 new chain-management tests are fair and correctly test the feature. But 8 pre-existing tests were silently modified to assert on the gold patch's internal subprocess call count -- an implementation detail not specified anywhere in the problem, requirements, or interface. An agent that correctly implements chain management using a different internal approach will pass the new tests but fail the modified ones.

The sneaky edit pattern makes this particularly insidious: the modified tests look like pre-existing regression tests, masking the fact that they now enforce gold-patch-specific behavior.
