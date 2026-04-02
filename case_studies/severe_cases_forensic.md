# Forensic Case Study: SEVERE Classification Audit

**Generated**: 2026-03-06
**Scope**: 13 SEVERE-classified instances from bench-cleanser pipeline
**Purpose**: Comprehensive forensic analysis of each case with pipeline scores, test/patch analysis, manual verdicts, root cause identification, and new taxonomy mapping.

---

## Table of Contents

1. [Case 01: astropy__astropy-7606](#case-01-astropy__astropy-7606)
2. [Case 02: astropy__astropy-7671](#case-02-astropy__astropy-7671)
3. [Case 03: astropy__astropy-8872](#case-03-astropy__astropy-8872)
4. [Case 04: astropy__astropy-13236](#case-04-astropy__astropy-13236)
5. [Case 05: astropy__astropy-13398](#case-05-astropy__astropy-13398)
6. [Case 06: astropy__astropy-13453](#case-06-astropy__astropy-13453)
7. [Case 07: astropy__astropy-14182](#case-07-astropy__astropy-14182)
8. [Case 08: astropy__astropy-14365](#case-08-astropy__astropy-14365)
9. [Case 09: astropy__astropy-14539](#case-09-astropy__astropy-14539)
10. [Case 10: django__django-10999](#case-10-django__django-10999)
11. [Case 11: django__django-11532](#case-11-django__django-11532)
12. [Case 12: django__django-11728](#case-12-django__django-11728)
13. [Case 13: django__django-12155](#case-13-django__django-12155)

---

## Summary Statistics

| Verdict | Count | Instances |
|---------|-------|-----------|
| TRUE POSITIVE | 5 | astropy-13398, astropy-14182, astropy-7606, django-10999, django-11532 |
| BORDERLINE | 2 | astropy-13453, astropy-14539 |
| FALSE POSITIVE | 6 | astropy-7671, astropy-8872, django-11728, django-12155, astropy-13236, astropy-14365 |

**Pipeline Precision at SEVERE**: 5/13 = 38.5% (TRUE POSITIVE only), 7/13 = 53.8% (including BORDERLINE)

---

## Case 01: astropy__astropy-7606

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-7606` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 1 F2P test(s) are sneaky modifications |
| OVERPATCH | 0.25 | 1 borderline hunk(s) |
| SNEAKY_TEST_MOD | 1.00 | (no detail) |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.50 | 2/4 assertion(s) check out-of-scope behavior |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.20 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `astropy/units/tests/test_units.py::test_unknown_unit3` | SNEAKY_MODIFICATION | 0.78 | 4 | 2 | false |

**Reasoning**: The existing test `test_unknown_unit3` was modified by adding four new assertions. Two directly target the scoped bug (safe equality with `None`): `assert unit != None` and `assert unit not in (None, u.m)`, which exercise `UnrecognizedUnit.__eq__` and must no longer hit `Unit(None)` raising `TypeError`. However, the patch also adds `assert unit == "FOO"` and `assert unit != u.m`, which assert additional equality semantics against a string and a recognized unit that are not part of the problem statement/behavioral contract. Because the test pre-existed and was extended with out-of-scope assertions, this is a sneaky test modification.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/units/core.py` (hunk 0) | BORDERLINE | 0.50 | false | (no detail) |
| 2 | `astropy/units/core.py` (hunk 1) | IN_SCOPE | 0.90 | false | This hunk directly changes `UnrecognizedUnit.__eq__` to avoid propagating the TypeError raised by `Unit(None, parse_strict='silent')` during equality checks. Wrapping `Unit()` in try/except and returning `NotImplemented` ensures `x == None` safely evaluates to False via Python's fallback comparison semantics. The switch to `isinstance(other, type(self))` is a minor behavioral tweak but remains within the equality-comparison logic being fixed. |

### Manual Verdict

**TRUE POSITIVE**

**Justification**: 2/4 assertions test general equality beyond the None comparison fix described in the problem statement. The test asserts `unit == "FOO"` (string equality) and `unit != u.m` (recognized unit inequality), which go beyond the narrow scope of preventing `TypeError` when comparing with `None`. While these are reasonable behaviors to verify, they represent scope expansion in the test that could reject valid candidate patches that only fix the None comparison.

### Root Cause

The **SNEAKY_TEST_MOD** and **TEST_DESC_MISALIGN** detectors correctly identified that the existing test was modified to include broader equality semantics beyond the stated bug scope. The pipeline's detection was accurate here.

### New Taxonomy Mapping

- **Primary**: `EXCESS_TEST` -- The test asserts behaviors (string equality, cross-type inequality) not required by the problem statement.
- **Secondary**: None.

---

## Case 02: astropy__astropy-7671

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-7671` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 1 F2P test(s) are sneaky modifications |
| OVERPATCH | 0.00 | -- |
| SNEAKY_TEST_MOD | 1.00 | `astropy/utils/tests/test_introspection.py::test_minversion` existed at base_commit and was modified |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.00 | -- |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.35 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `astropy/utils/tests/test_introspection.py::test_minversion` | SNEAKY_MODIFICATION | 0.90 | 0 | 0 | true |

**Reasoning**: Task scope is to fix `astropy.utils.introspection.minversion` so version comparisons involving `dev`-tagged requested versions (e.g. `1.14dev`) do not raise `TypeError` (LooseVersion int/str segment bug) and instead return a boolean consistent with `pkg_resources.parse_version` semantics. The only test change adds `'0.12dev'` to `good_versions`, which directly exercises the reported failure mode: comparing an installed numeric patch version (`test_module.__version__ = '0.12.2'`) against a requested `...dev` version without an extra dot segment. Each assertion still only checks `minversion(...)` truthiness/falsehood and will fail if a TypeError is raised, so it is a direct regression test for the described bug and expected comparison result.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/utils/introspection.py` (hunk 0) | INFRASTRUCTURE | 0.78 | false | Adds a `re` import likely needed for upcoming version-string parsing/normalization in `minversion` to avoid `LooseVersion` TypeError with `dev` tags. The import itself doesn't implement the fix but supports the in-scope change. |
| 2 | `astropy/utils/introspection.py` (hunk 1) | IN_SCOPE | 0.78 | false | This change is inside `astropy.utils.introspection.minversion` and directly targets the reported `LooseVersion` `TypeError` when the requested version string contains non-numeric tags like `dev`/`rc` that lead to mixed int/str segment comparisons. Stripping the requested version down to its numeric dotted prefix prevents the exception and allows `minversion` to return a boolean, which is the core task requirement. |

### Manual Verdict

**FALSE POSITIVE**

**Justification**: The modification to `test_minversion` is an aligned change: it adds `'0.12dev'` to the `good_versions` list, which directly tests the exact bug being fixed (LooseVersion TypeError with dev-tagged versions). The SNEAKY_TEST_MOD detector fires solely because the test file existed at the base commit and was modified, but the modification is perfectly aligned with the task scope. There are zero misaligned assertions. This is a textbook example of a legitimate test update to cover a regression.

### Root Cause

The **SNEAKY_TEST_MOD** detector over-fires. It flags any modification to an existing test as suspicious without evaluating whether the modification is aligned with the task scope. The detector has no nuance for "aligned modification" vs. "scope-expanding modification."

### New Taxonomy Mapping

- **Primary**: None (not contaminated).
- **Pipeline Failure**: `SNEAKY_TEST_MOD` false positive due to lack of alignment analysis on the modification content.

---

## Case 03: astropy__astropy-8872

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-8872` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 1 F2P test(s) are sneaky modifications |
| OVERPATCH | 0.17 | 1 borderline hunk(s) |
| SNEAKY_TEST_MOD | 1.00 | `astropy/units/tests/test_quantity.py::test_preserve_dtype` existed at base_commit and was modified |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.00 | -- |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.30 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `astropy/units/tests/test_quantity.py::test_preserve_dtype` | SNEAKY_MODIFICATION | 0.84 | 2 | 0 | true |

**Reasoning**: The only substantive change is adding a new regression check that `u.Quantity` preserves a `np.float16` input dtype: `a3_16 = np.array(..., dtype=np.float16)` followed by `assert q3_16.dtype == a3_16.dtype`. This directly targets the reported bug (unintended float16 to float64 promotion during Quantity construction). The float32 portion is just renamed (`a3` to `a3_32`) with the same assertion, and no new expectations are added for other dtypes or unrelated behavior.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/units/quantity.py` (hunk 0) | BORDERLINE | 0.66 | false | This hunk only updates the `dtype` parameter documentation for `Quantity` construction (clarifying which inputs get coerced to float by default). It touches dtype-handling semantics, so it's plausibly meant to keep docs accurate alongside the float16-preservation fix, but it does not itself implement or directly address the reported float16 to float64 upcast bug. |
| 2 | `astropy/units/quantity.py` (hunk 1) | IN_SCOPE | 0.93 | false | This change narrows the condition that forces `dtype=float` during `Quantity` construction. The previous `np.can_cast(np.float32, value.dtype)` check incorrectly triggered for `float16` (since float32 cannot be safely cast to float16), causing `float16` inputs to be converted to Python `float`/`float64`. Switching to `value.dtype.kind in 'iu'` avoids that unintended float16 to float64 promotion while still converting integer inputs to float as intended, directly matching the task's float16 dtype-preservation requirement. |
| 3 | `astropy/units/quantity.py` (hunk 2) | IN_SCOPE | 0.78 | false | This change updates Quantity.__new__'s default "cast to float" condition so that float16 inputs are no longer treated as needing promotion. Restricting the cast to integer/unsigned/object dtypes directly addresses the reported float16 to float64 construction bug by leaving float dtypes (including float16) unchanged. |

### Manual Verdict

**FALSE POSITIVE**

**Justification**: The modification to `test_preserve_dtype` is fully aligned with the task scope. Adding a float16 dtype preservation assertion directly tests the exact bug being fixed. There are zero misaligned assertions. The SNEAKY_TEST_MOD detector fires solely because the test existed at the base commit, not because the modification introduces scope creep. The borderline OVERPATCH hunk is a documentation update that logically accompanies the code fix.

### Root Cause

The **SNEAKY_TEST_MOD** detector over-fires. Same root cause as astropy-7671: the detector flags any modification to an existing test without evaluating content alignment. With 0 misaligned assertions and a directly relevant test addition, this is a clean false positive.

### New Taxonomy Mapping

- **Primary**: None (not contaminated).
- **Pipeline Failure**: `SNEAKY_TEST_MOD` false positive due to lack of content-aware alignment analysis.

---

## Case 04: astropy__astropy-13236

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-13236` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 1 F2P test(s) misaligned with task scope; 7 F2P test(s) are sneaky modifications |
| OVERPATCH | 0.00 | -- |
| SNEAKY_TEST_MOD | 0.90 | `astropy/table/tests/test_mixin.py::test_ndarray_mixin` existed at base_commit and was modified (7 hunks) |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.375 | 3/8 assertion(s) check out-of-scope behavior |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.40 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_mixin.py::test_ndarray_mixin` (hunk 1) | SNEAKY_MODIFICATION | 0.60 | 0 | 0 | true |
| 2 | `test_mixin.py::test_ndarray_mixin` (hunk 2) | SNEAKY_MODIFICATION | 0.66 | 0 | 0 | true |
| 3 | `test_mixin.py::test_ndarray_mixin` (hunk 3) | SNEAKY_MODIFICATION | 0.50 | 0 | 0 | true |
| 4 | `test_mixin.py::test_ndarray_mixin` (hunk 4) | SNEAKY_MODIFICATION | 0.74 | 1 | 0 | true |
| 5 | `test_mixin.py::test_ndarray_mixin` (hunk 5) | SNEAKY_MODIFICATION | 0.84 | 1 | 0 | true |
| 6 | `test_mixin.py::test_ndarray_mixin` (hunk 6) | SNEAKY_MODIFICATION | 0.74 | 1 | 0 | true |
| 7 | `test_mixin.py::test_ndarray_mixin` (hunk 7) | SNEAKY_MODIFICATION | 0.74 | 1 | 0 | true |
| 8 | `test_table.py::test_structured_masked_column` | PARTIALLY_ALIGNED | 0.72 | 4 | 3 | false |

**Reasoning for test_ndarray_mixin**: All 7 modifications to `test_ndarray_mixin` are aligned with the task scope. The modifications parameterize the test over `as_ndarray_mixin=[True, False]` and update hard-coded `NdarrayMixin` expectations to use a `class_exp` variable, directly tracking the scoped behavioral change (structured ndarrays should no longer be implicitly viewed as NdarrayMixin). Zero misaligned assertions across all 7 hunks.

**Reasoning for test_structured_masked_column**: The final assertion `isinstance(t['a'], MaskedColumn)` aligns with the task. However, the first three assertions check detailed field-by-field mask propagation semantics for structured masked arrays, which are not described in the task scope (the scope focuses on column type/conversion and deprecation/warning behavior). 3/4 out-of-scope assertions.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/table/table.py` (hunk 0) | IN_SCOPE | 0.94 | false | This hunk removes the specific code path that auto-views structured NumPy ndarrays as `NdarrayMixin` when adding to a `Table`. The task explicitly requires deleting this implicit conversion. |

### Manual Verdict

**FALSE POSITIVE**

**Justification**: The 7 modifications to `test_ndarray_mixin` are all aligned with the scope -- they update the test to reflect the new expected behavior (structured ndarrays becoming regular Columns instead of NdarrayMixin). Only `test_structured_masked_column` has genuine misalignment, with 3/4 assertions testing mask propagation semantics rather than column type. However, this single partially-aligned new test with moderate misalignment would at most justify a MODERATE classification, not SEVERE. The SEVERE over-classification is driven by the 7 SNEAKY_TEST_MOD flags on `test_ndarray_mixin`, all of which are false positives.

### Root Cause

The **SNEAKY_TEST_MOD** detector over-fires on all 7 hunks of `test_ndarray_mixin`. Each hunk is analyzed independently and flagged as suspicious solely because the test file existed at the base commit. The detector does not aggregate the per-hunk alignment analysis, which would show 0 total misaligned assertions across 7 hunks. The volume of 7 flags artificially inflates the OVERTEST confidence to 1.0.

### New Taxonomy Mapping

- **Primary (minor)**: `EXCESS_TEST` -- Only `test_structured_masked_column` has 3 OOS assertions about mask propagation.
- **Severity Override**: Should be MODERATE at most, not SEVERE.
- **Pipeline Failure**: `SNEAKY_TEST_MOD` volume inflation; detector counts hunks not semantic modifications.

---

## Case 05: astropy__astropy-13398

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-13398` |
| **Severity** | SEVERE |
| **Total Confidence** | 0.9767 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 0.75 | 3 F2P test(s) misaligned with task scope |
| OVERPATCH | 0.5625 | 2/8 hunk(s) out of scope; 5 borderline hunk(s) |
| SNEAKY_TEST_MOD | 0.00 | -- |
| SCOPE_CREEP | 0.30 | Gold patch touches 4 non-test files |
| TEST_DESC_MISALIGN | 0.3226 | 10/31 assertion(s) check out-of-scope behavior |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.55 | Problem statement ambiguity score: 0.55 |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_intermediate_transformations.py::test_itrs_topo_to_altaz_with_refraction` | PARTIALLY_ALIGNED | 0.78 | 12 | 6 | false |
| 2 | `test_intermediate_transformations.py::test_itrs_topo_to_hadec_with_refraction` | PARTIALLY_ALIGNED | 0.50 | 12 | 0 | false |
| 3 | `test_intermediate_transformations.py::test_cirs_itrs_topo` | MISALIGNED | 0.92 | 4 | 4 | false |
| 4 | `test_intermediate_transformations.py::test_itrs_straight_overhead` | ALIGNED | 0.88 | 3 | 0 | false |

**Key Findings**:
- `test_cirs_itrs_topo` (4/4 misaligned): Exercises CIRS-to-ITRS-to-CIRS round-tripping, which does not involve AltAz/HADec transforms or the topocentric ITRS rotation-matrix path at all.
- `test_itrs_topo_to_altaz_with_refraction` (6/12 misaligned): Half the assertions require atmospheric refraction to be applied/removed identically through the new ITRS-to-AltAz path, but refraction support was explicitly noted as optional/undecided in the task scope.
- `test_itrs_straight_overhead` (0/3 misaligned): Fully aligned, directly tests AltAz/HADec transforms for a straight-overhead topocentric vector.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `builtin_frames/__init__.py` (hunk 0) | INFRASTRUCTURE | 0.95 | true | __init__.py hunk with only import/export changes |
| 2 | `intermediate_rotation_transforms.py` (hunk 0) | OUT_OF_SCOPE | 0.98 | false | Only fixes a spelling typo ("siderial" to "sidereal") in a comment |
| 3 | `intermediate_rotation_transforms.py` (hunk 1) | BORDERLINE | 0.50 | false | -- |
| 4 | `intermediate_rotation_transforms.py` (hunk 2) | BORDERLINE | 0.50 | false | -- |
| 5 | `intermediate_rotation_transforms.py` (hunk 3) | BORDERLINE | 0.50 | false | -- |
| 6 | `intermediate_rotation_transforms.py` (hunk 4) | OUT_OF_SCOPE | 0.82 | false | Changes ITRS-to-CIRS transform to propagate `location`, not part of ITRS-to-AltAz/HADec scope |
| 7 | `itrs.py` (hunk 0) | BORDERLINE | 0.70 | false | Adds `location` attribute to ITRS frame -- related but not required by scope |
| 8 | `itrs_observed_transforms.py` (hunk 0) | BORDERLINE | 0.72 | false | New module targeting ITRS-to-AltAz/HADec but includes refraction support and ITRS-to-ITRS sync that scope says to avoid |

### Manual Verdict

**TRUE POSITIVE**

**Justification**: Multi-signal contamination. Three tests have misalignment issues: `test_cirs_itrs_topo` is entirely misaligned (4/4 OOS assertions testing CIRS round-tripping instead of AltAz/HADec transforms), `test_itrs_topo_to_altaz_with_refraction` has 6/12 OOS assertions requiring refraction behavior the scope called optional. The patch has 2 clear out-of-scope hunks (typo fix, ITRS-to-CIRS location propagation) and 5 borderline hunks. The compound OVERPATCH+OVERTEST pattern is genuine.

### Root Cause

Multiple pipeline components contribute to a correct detection:
- **OVERTEST**: Correctly identifies 3 misaligned tests.
- **OVERPATCH**: Correctly identifies 2 OOS hunks and 5 borderline hunks.
- **AMBIGUOUS_SPEC**: The problem statement's ambiguity (0.55) contributes to the scope creep in both patch and tests.

### New Taxonomy Mapping

- **Primary**: `SCOPE_CREEP` -- Typo fix and ITRS-to-CIRS location propagation are unrelated to the ITRS-to-AltAz/HADec implementation.
- **Secondary**: `EXCESS_TEST` -- `test_cirs_itrs_topo` tests entirely different transform path; refraction assertions go beyond stated scope.
- **Tertiary**: `VAGUE_SPEC` -- Ambiguous scope boundaries around refraction support and which transforms are in scope.

---

## Case 06: astropy__astropy-13453

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-13453` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 1 F2P test(s) misaligned with task scope |
| OVERPATCH | 0.00 | -- |
| SNEAKY_TEST_MOD | 0.00 | -- |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 1.00 | 1/1 assertion(s) check out-of-scope behavior |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.25 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `astropy/io/ascii/tests/test_html.py::test_write_table_formatted_columns` | PARTIALLY_ALIGNED | 0.76 | 1 | 1 | false |

**Reasoning**: The new test exercises the exact reported bug path by calling `Table.write(..., format='html', formats=formats)` and expecting formatted cell values. However, the sole assertion `assert out == expected.strip()` hard-codes and enforces the entire pretty-printed HTML document (meta tags, tag layout, internal whitespace/indentation), which goes beyond the problem statement's requirement of "apply formats to values" and can fail on unrelated HTML-serialization changes.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/io/ascii/html.py` (hunk 0) | IN_SCOPE | 0.92 | false | The task is to ensure the HTML ASCII writer honors the existing `formats` argument. Setting `self.data.cols = cols` and calling `self.data._set_col_formats()` mirrors the initialization done in other ASCII writers. Minimal, directly relevant change. |

### Manual Verdict

**BORDERLINE**

**Justification**: The test does assert the correct behavior (formatted cell values in HTML output), and it is the natural way to test HTML writer output (comparing full output strings). The concern is real but pragmatic: asserting exact HTML format goes beyond "values are formatted" and could reject patches that produce correct values with slightly different HTML structure. However, classifying this as SEVERE is harsh -- the test fundamentally tests the right thing, just with overly strict output comparison. The patch itself is clean (single IN_SCOPE hunk). This is more of a test brittleness issue than a contamination issue.

### Root Cause

The **TEST_DESC_MISALIGN** detector's 1/1 ratio creates a perfect 1.0 confidence score, but the misalignment is a matter of test granularity (whole-output comparison) rather than scope violation. The detector does not distinguish between structural over-assertion (brittle but aligned) and semantic over-assertion (testing unrelated behavior).

### New Taxonomy Mapping

- **Primary (weak)**: `EXCESS_TEST` -- The test over-constrains the HTML structure beyond what the fix requires.
- **Severity Override**: BORDERLINE rather than SEVERE. The core behavior being tested is correct.

---

## Case 07: astropy__astropy-14182

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-14182` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 1 F2P test(s) misaligned with task scope |
| OVERPATCH | 0.3333 | 2 borderline hunk(s) |
| SNEAKY_TEST_MOD | 0.00 | -- |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.8333 | 5/6 assertion(s) check out-of-scope behavior |
| CIRCULAR_DEPENDENCY | 0.98 | `test_rst_with_header_rows` exercises 2 OOS hunk(s) |
| AMBIGUOUS_SPEC | 0.45 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `astropy/io/ascii/tests/test_rst.py::test_rst_with_header_rows` | PARTIALLY_ALIGNED | 0.74 | 6 | 5 | false |

**Reasoning**: The task scope is specifically about *writing* ReStructuredText with `header_rows=[...]` (the write must not raise `TypeError` and must emit the requested extra header lines like units). The test's final assertion exercises the RST writer and verifies multi-row header output, which is in-scope. However, the first five assertions validate *reader* behavior (`QTable.read(..., header_rows=...)` populating units and dtypes), which the problem statement did not request and could fail independently of the writer fix.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/io/ascii/rst.py` (hunk 0) | BORDERLINE | 0.66 | false | Removing hard-coded `start_line = 3` in `SimpleRSTData` affects the reader-side data start position, not directly the writer API. |
| 2 | `astropy/io/ascii/rst.py` (hunk 1) | BORDERLINE | 0.66 | false | Updates the RST writer class docstring/example to demonstrate `header_rows`. Related but not required for the fix. |
| 3 | `astropy/io/ascii/rst.py` (hunk 2) | IN_SCOPE | 0.86 | false | Updates the RST writer class to accept `header_rows` kwarg (preventing TypeError) and forwards it to FixedWidth base. Core fix implementation. |

### Manual Verdict

**TRUE POSITIVE**

**Justification**: 5 out of 6 assertions test reader behavior (`QTable.read(...)` with `header_rows`) when the problem statement only asks for writer support (`tbl.write(..., format='ascii.rst', header_rows=...)`). Additionally, the CIRCULAR_DEPENDENCY pattern is confirmed: the test exercises reader-side hunks (hunk 0: `start_line` removal) that are only needed because the test itself validates reader behavior. This creates a self-referential loop where the patch includes reader changes to satisfy a test that goes beyond the stated scope.

### Root Cause

The **TEST_DESC_MISALIGN** detector correctly identifies 5/6 OOS assertions. The **CIRCULAR_DEPENDENCY** detector correctly identifies that the test exercises the 2 borderline hunks (reader-side changes), establishing a circular justification pattern. Both components performed well on this case.

### New Taxonomy Mapping

- **Primary**: `EXCESS_TEST` -- 5/6 assertions test reader behavior not required by the problem statement.
- **Secondary**: `SCOPE_CREEP` -- Reader-side hunks (hunk 0, hunk 1) exist to support the excess test assertions.
- **Compound**: `CIRCULAR_DEPENDENCY` -- The excess test assertions justify the excess patch hunks, and vice versa.

---

## Case 08: astropy__astropy-14365

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-14365` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 2 F2P test(s) misaligned with task scope; 1 F2P test(s) are sneaky modifications |
| OVERPATCH | 0.25 | 1 borderline hunk(s) |
| SNEAKY_TEST_MOD | 0.90 | `astropy/io/ascii/tests/test_qdp.py::test_roundtrip` existed at base_commit and was modified |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 1.00 | 12/1 assertion(s) check out-of-scope behavior |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.20 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_qdp.py::test_roundtrip` (MODIFIED) | SNEAKY_MODIFICATION | 0.90 | 0 | 7 | true |
| 2 | `test_qdp.py::test_roundtrip` (NEW) | PARTIALLY_ALIGNED | 0.60 | 0 | 5 | false |
| 3 | `test_qdp.py::test_roundtrip` (UNKNOWN) | PARTIALLY_ALIGNED | 0.50 | 0 | 0 | false |

**Key Findings**: The task scope is specifically: QDP command parsing must be case-insensitive so lines like `read serr 1 2` are accepted. The post-patch `test_roundtrip` never includes any lowercase/mixed-case command tokens: its embedded QDP content uses only uppercase directives (`READ TERR 1`, `READ SERR 2`), so it cannot fail on the reported bug or verify the requested fix. All assertions check unrelated behavior (warning about multiple command blocks, round-trip numerical equality/masking/NaN handling, specific parsed error values for uppercase `READ TERR`, and presence of metadata keys).

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/io/ascii/qdp.py` (hunk 0) | IN_SCOPE | 0.95 | false | Adding `re.IGNORECASE` to the compiled regex directly enables recognition of command keywords regardless of case. Core fix. |
| 2 | `astropy/io/ascii/qdp.py` (hunk 1) | BORDERLINE | 0.72 | false | Makes the special missing-data token "NO" case-insensitive. Aligns with general case-insensitivity goal but not directly about command keyword parsing. |

### Manual Verdict

**TRUE POSITIVE**

**Justification**: The modified test does not actually test the fix described in the problem statement. The test uses only uppercase QDP directives, meaning it cannot verify case-insensitive parsing. The 12 misaligned assertions (across reports) test broader QDP roundtrip behavior (warnings, numerical equality, metadata keys) that are unrelated to case-insensitive command parsing. A candidate patch that correctly handles lowercase commands but differs in other roundtrip behavior would fail this test incorrectly.

### Root Cause

The **TEST_DESC_MISALIGN** detector correctly identifies that the test assertions do not match the task scope. The **SNEAKY_TEST_MOD** detector correctly flags the modification of an existing test. In this case, unlike astropy-7671 and astropy-8872, the sneaky modification genuinely introduces misalignment: the parameterization adds a `lowercase` parameter but the test body's assertions remain focused on unrelated roundtrip behavior.

### New Taxonomy Mapping

- **Primary**: `EXCESS_TEST` -- Assertions test general QDP roundtrip behavior (warnings, NaN handling, metadata) not required by the case-insensitive parsing fix.
- **Note**: The test also has a coverage gap -- it does not directly assert case-insensitive parsing with lowercase tokens, which is the core task.

---

## Case 09: astropy__astropy-14539

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `astropy__astropy-14539` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 1.00 | 1 F2P test(s) misaligned with task scope; 3 F2P test(s) are sneaky modifications |
| OVERPATCH | 0.00 | -- |
| SNEAKY_TEST_MOD | 0.90 | `test_diff.py::test_identical_tables` modified; `test_diff.py::test_different_table_data` modified (2x) |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 1.00 | 27/11 assertion(s) check out-of-scope behavior |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.35 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_diff.py::test_identical_tables` (MODIFIED) | SNEAKY_MODIFICATION | 0.80 | 2 | 0 | true |
| 2 | `test_diff.py::test_different_table_data` (UNKNOWN) | MISALIGNED | 0.72 | 0 | 27 | false |
| 3 | `test_diff.py::test_different_table_data` (MODIFIED) | SNEAKY_MODIFICATION | 0.50 | 0 | 0 | true |
| 4 | `test_diff.py::test_different_table_data` (MODIFIED) | SNEAKY_MODIFICATION | 0.50 | 9 | 0 | true |

**Key Findings**:
- `test_identical_tables`: Modification is aligned -- adds a VLA column using `Q` descriptor and updates expected counts. Zero misaligned assertions. Directly tests the bug fix (identical VLA data should not produce false-positive diffs).
- `test_different_table_data`: 27 misaligned assertions. This test validates true-positive diff enumeration/report formatting for many non-VLA formats and a `PI(2)` VLA column, not the required behavior of suppressing spurious diffs for identical VLA contents. The test does not exercise `FITSDiff` or `fits.printdiff` on identical files.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `astropy/io/fits/diff.py` (hunk 0) | IN_SCOPE | 0.95 | false | Extends the VLA comparison condition to include `Q` descriptor in addition to `P`. Directly addresses the VLA false-positive diff bug. |

### Manual Verdict

**BORDERLINE**

**Justification**: The case has a split personality. `test_identical_tables` is directly relevant and correctly tests the fix (adding a `Q` VLA column to verify identical comparison). The patch is a clean, single IN_SCOPE hunk. However, `test_different_table_data` has 27 out-of-scope assertions that test diff enumeration for *different* data across many column types, which is a separate concern from the false-positive fix for identical VLA data. This creates real contamination risk for candidate patches, but the core test (`test_identical_tables`) is valid and the patch is minimal. SEVERE is harsh; the issue is confined to one of the two test functions.

### Root Cause

The **TEST_DESC_MISALIGN** detector correctly identifies 27 OOS assertions in `test_different_table_data`. However, the **SNEAKY_TEST_MOD** detector's flagging of `test_identical_tables` is a false positive (the modification is aligned). The aggregate effect inflates the severity.

### New Taxonomy Mapping

- **Primary**: `EXCESS_TEST` -- `test_different_table_data` tests diff enumeration behavior unrelated to the identical-VLA false-positive fix.
- **Severity Override**: BORDERLINE. `test_identical_tables` is aligned, patch is clean. Only `test_different_table_data` is problematic.

---

## Case 10: django__django-10999

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `django__django-10999` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 0.00 | -- |
| OVERPATCH | 1.00 | 1/1 hunk(s) out of scope |
| SNEAKY_TEST_MOD | 0.00 | -- |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.00 | -- |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.15 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_negative (DurationParseTests)` | ALIGNED | 0.30 | 0 | 0 | false |
| 2 | `test_parse_postgresql_format (DurationParseTests)` | ALIGNED | 0.30 | 0 | 0 | false |

**Reasoning**: Both F2P tests were not modified (no matching hunk in test_patch). They exercise new behavior from the gold patch. Tests themselves are aligned.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `django/utils/dateparse.py` (hunk 0) | OUT_OF_SCOPE | 0.95 | false | Task scope requires only adjusting the hours-group lookahead in `standard_duration_re` from `(?=\d+:\d+)` to allow optional `-` on minutes/seconds (i.e., `(?=-?\d+:-?\d+)`) without changing supported formats. This hunk instead introduces a new `sign` group, removes `-?` from `hours`, `minutes`, and `seconds` (changing semantics to disallow per-component negatives), and leaves the lookahead as `(?=\d+:\d+)`. It's a broader regex redesign rather than the targeted lookahead fix. |

### Manual Verdict

**TRUE POSITIVE**

**Justification**: The gold patch performs a broader regex redesign instead of the targeted lookahead fix described in the problem statement. The problem statement clearly specifies adding optional `-` to the lookahead pattern, but the patch instead restructures the entire regex by adding a top-level `sign` group and removing per-component sign support. This changes the semantics of duration parsing (disallowing per-component negatives like `-1:2:-3`) in ways not required or described by the task. A candidate that implements the targeted lookahead fix would produce different parsed results for edge cases.

### Root Cause

The **OVERPATCH** detector correctly identifies the single hunk as out-of-scope with 0.95 confidence. The detection is straightforward: the patch's regex restructuring does not match the problem statement's described fix (lookahead adjustment).

### New Taxonomy Mapping

- **Primary**: `SCOPE_CREEP` -- The regex redesign goes beyond the targeted lookahead fix, changing semantics of per-component sign handling.
- **Note**: The tests remain aligned but exercise the redesigned behavior, meaning they will reject the simpler targeted fix described in the problem statement.

---

## Case 11: django__django-11532

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `django__django-11532` |
| **Severity** | SEVERE |
| **Total Confidence** | 0.8125 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 0.00 | -- |
| OVERPATCH | 0.5455 | 6/11 hunk(s) out of scope |
| SNEAKY_TEST_MOD | 0.00 | -- |
| SCOPE_CREEP | 0.45 | Gold patch touches 5 non-test files |
| TEST_DESC_MISALIGN | 0.00 | -- |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.25 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_non_ascii_dns_non_unicode_email (mail.tests.MailTests)` | ALIGNED | 0.30 | 0 | 0 | false |

**Reasoning**: F2P test was not modified. Exercises new behavior from the gold patch. Test itself is aligned with the Message-ID punycode fix.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `django/core/mail/message.py` (hunk 0) | INFRASTRUCTURE | 0.90 | false | Import of `punycode` needed for the fix |
| 2 | `django/core/mail/message.py` (hunk 1) | INFRASTRUCTURE | 0.72 | false | Changes `sanitize_address()` to use punycode() helper -- refactor for consistency, not directly about Message-ID |
| 3 | `django/core/mail/utils.py` (hunk 0) | INFRASTRUCTURE | 0.78 | false | Import supporting the in-scope change |
| 4 | `django/core/mail/utils.py` (hunk 1) | IN_SCOPE | 0.90 | false | Updates `get_fqdn()` to return punycoded hostname -- core fix |
| 5 | `django/core/validators.py` (hunk 0) | OUT_OF_SCOPE | 0.90 | false | Adds `punycode` import in validators -- unrelated to Message-ID |
| 6 | `django/core/validators.py` (hunk 1) | OUT_OF_SCOPE | 0.84 | false | Changes URL validation netloc encoding -- unrelated to email Message-ID |
| 7 | `django/core/validators.py` (hunk 2) | OUT_OF_SCOPE | 0.86 | false | Changes email/domain validation IDNA handling -- unrelated to Message-ID crash |
| 8 | `django/utils/encoding.py` (hunk 0) | INFRASTRUCTURE | 0.72 | false | Adds reusable `punycode()` helper function |
| 9 | `django/utils/html.py` (hunk 0) | OUT_OF_SCOPE | 0.91 | false | Adds `punycode` import in html utilities -- unrelated to Message-ID |
| 10 | `django/utils/html.py` (hunk 1) | OUT_OF_SCOPE | 0.90 | false | Changes URL netloc handling in html utilities -- unrelated |
| 11 | `django/utils/html.py` (hunk 2) | OUT_OF_SCOPE | 0.78 | false | Changes `is_email_simple()` mailto URL generation -- unrelated |

### Manual Verdict

**TRUE POSITIVE**

**Justification**: The task is narrowly about making the Message-ID domain ASCII-safe (punycode the hostname) to avoid UnicodeEncodeError during email generation. The patch correctly implements this (via `get_fqdn()` returning punycoded hostname) but also refactors 6 out of 11 hunks across `django/core/validators.py` and `django/utils/html.py` to use the new `punycode()` helper. These changes affect URL validation, email validation, and HTML mailto generation -- none of which are related to the Message-ID crash. A candidate patch that only fixes the Message-ID hostname encoding would not produce these validator/HTML changes and would be rejected if tests depend on the refactored behavior.

### Root Cause

The **OVERPATCH** detector correctly identifies 6/11 hunks as out-of-scope. The **SCOPE_CREEP** detector correctly flags that the patch touches 5 non-test files. Both components performed well. This is a classic case of "while I'm at it" refactoring bundled with a targeted bug fix.

### New Taxonomy Mapping

- **Primary**: `SCOPE_CREEP` -- 6/11 hunks are validator/HTML refactoring unrelated to the email Message-ID fix.
- **Secondary**: `SCOPE_CREEP` -- The patch opportunistically refactors all IDNA handling across Django to use a common helper, well beyond the stated task.

---

## Case 12: django__django-11728

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `django__django-11728` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 0.00 | -- |
| OVERPATCH | 1.00 | 6/6 hunk(s) out of scope |
| SNEAKY_TEST_MOD | 0.00 | -- |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.00 | -- |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.25 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_simplify_regex (AdminDocViewFunctionsTests)` | ALIGNED | 0.30 | 0 | 0 | false |
| 2 | `test_app_not_found (TestModelDetailView)` | ALIGNED | 0.30 | 0 | 0 | false |

**Reasoning**: Both F2P tests were not modified and are aligned with the task scope.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `django/contrib/admindocs/utils.py` (hunk 0) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 2 | `django/contrib/admindocs/utils.py` (hunk 1) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 3 | `django/contrib/admindocs/utils.py` (hunk 2) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 4 | `django/contrib/admindocs/utils.py` (hunk 3) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 5 | `django/contrib/admindocs/utils.py` (hunk 4) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 6 | `django/contrib/admindocs/utils.py` (hunk 5) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |

**Critical Note**: All 6 hunks are classified OUT_OF_SCOPE via **heuristic** (`is_heuristic: true`), with the reasoning "Change in documentation/changelog file". The file path is `django/contrib/admindocs/utils.py`, which is **not** a documentation or changelog file -- it is a Python utility module under the `admindocs` contrib app. The heuristic misidentifies `admindocs/` as a documentation directory.

### Manual Verdict

**FALSE POSITIVE**

**Justification**: The `is_doc_file` heuristic bug causes `django/contrib/admindocs/utils.py` to be misidentified as a documentation file. The path contains `admindocs/` which the heuristic incorrectly matches as a docs directory. All 6 hunks are real Python code changes in the admindocs utility module, not documentation changes. The entire SEVERE classification rests on this single heuristic error producing 6/6 OUT_OF_SCOPE verdicts.

### Root Cause

The **is_doc_file heuristic** in the OVERPATCH detector has a path-matching bug. It matches `admindocs/` as a documentation directory, causing all hunks in `django/contrib/admindocs/utils.py` to be classified as OUT_OF_SCOPE with the incorrect reasoning "Change in documentation/changelog file." This is a pure false positive driven by a single faulty heuristic rule.

### New Taxonomy Mapping

- **Primary**: None (not contaminated).
- **Pipeline Failure**: `is_doc_file` heuristic false positive. The regex/glob pattern matching documentation paths should exclude `admindocs/` or any path under `contrib/`.

---

## Case 13: django__django-12155

### Case Header

| Field | Value |
|-------|-------|
| **Instance ID** | `django__django-12155` |
| **Severity** | SEVERE |
| **Total Confidence** | 1.0 |

### Pipeline Scores

| Category | Confidence | Evidence |
|----------|------------|----------|
| OVERTEST | 0.00 | -- |
| OVERPATCH | 1.00 | 4/4 hunk(s) out of scope |
| SNEAKY_TEST_MOD | 0.00 | -- |
| SCOPE_CREEP | 0.00 | -- |
| TEST_DESC_MISALIGN | 0.00 | -- |
| CIRCULAR_DEPENDENCY | 0.00 | -- |
| AMBIGUOUS_SPEC | 0.25 | -- |

### F2P Test Analysis

| # | Test ID | Classification | Confidence | Assertion Count | Misaligned Assertions | Is Modified Existing |
|---|---------|---------------|------------|-----------------|----------------------|---------------------|
| 1 | `test_parse_rst_with_docstring_no_leading_line_feed (admin_docs.test_utils.TestUtils)` | ALIGNED | 0.30 | 0 | 0 | false |

**Reasoning**: F2P test was not modified and is aligned with the task scope.

### Patch Hunk Analysis

| # | File Path | Classification | Confidence | Is Heuristic | Reasoning |
|---|-----------|---------------|------------|-------------|-----------|
| 1 | `django/contrib/admindocs/utils.py` (hunk 0) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 2 | `django/contrib/admindocs/utils.py` (hunk 1) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 3 | `django/contrib/admindocs/views.py` (hunk 0) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |
| 4 | `django/contrib/admindocs/views.py` (hunk 1) | OUT_OF_SCOPE | 0.90 | **true** | Change in documentation/changelog file |

**Critical Note**: Same `is_doc_file` heuristic bug as django-11728. Both `admindocs/utils.py` and `admindocs/views.py` are Python source files in the admindocs contrib app, not documentation files. All 4 hunks are heuristically misclassified.

### Manual Verdict

**FALSE POSITIVE**

**Justification**: Identical root cause to django-11728. The `is_doc_file` heuristic misidentifies `django/contrib/admindocs/utils.py` and `django/contrib/admindocs/views.py` as documentation files because the path contains `admindocs/`. All 4 hunks are real Python code changes. The entire SEVERE classification is driven by this heuristic bug.

### Root Cause

The **is_doc_file heuristic** path-matching bug (same as django-11728). The pattern incorrectly matches `admindocs/` as a documentation directory. This affects two files in this case (`utils.py` and `views.py`), both under `django/contrib/admindocs/`.

### New Taxonomy Mapping

- **Primary**: None (not contaminated).
- **Pipeline Failure**: `is_doc_file` heuristic false positive (identical to django-11728).

---

## Cross-Case Analysis

### Pipeline Component Failure Summary

| Component | True Positive Cases | False Positive Cases | Notes |
|-----------|-------------------|---------------------|-------|
| SNEAKY_TEST_MOD | astropy-14365, astropy-7606 | astropy-7671, astropy-8872, astropy-13236 | Over-fires on aligned modifications; no content-aware alignment check |
| OVERPATCH | django-10999, django-11532, astropy-13398 | django-11728, django-12155 | `is_doc_file` heuristic bug on `admindocs/` paths |
| TEST_DESC_MISALIGN | astropy-14182, astropy-14365, astropy-13398, astropy-7606 | astropy-13453 (borderline) | Generally reliable; struggles with structural vs semantic over-assertion |
| CIRCULAR_DEPENDENCY | astropy-14182 | -- | Performed well when triggered |
| OVERTEST | astropy-13398, astropy-14365, astropy-7606 | astropy-7671, astropy-8872, astropy-13236 | Inherits SNEAKY_TEST_MOD false positives |

### Root Cause Distribution

| Root Cause | Count | Affected Cases |
|-----------|-------|----------------|
| SNEAKY_TEST_MOD over-fires on aligned modifications | 3 | astropy-7671, astropy-8872, astropy-13236 |
| is_doc_file heuristic bug (admindocs/ path) | 2 | django-11728, django-12155 |
| Genuine SCOPE_CREEP | 3 | django-10999, django-11532, astropy-13398 |
| Genuine EXCESS_TEST | 4 | astropy-7606, astropy-14182, astropy-14365, astropy-13398 |
| Severity over-classification (should be MODERATE/BORDERLINE) | 2 | astropy-13453, astropy-14539 |

### New Taxonomy Distribution

| Taxonomy Category | Cases |
|------------------|-------|
| SCOPE_CREEP | django-10999, django-11532, astropy-13398, astropy-14182 (secondary) |
| EXCESS_TEST | astropy-7606, astropy-13398, astropy-14182, astropy-14365, astropy-14539 |
| VAGUE_SPEC | astropy-13398 (tertiary) |
| CIRCULAR_DEPENDENCY | astropy-14182 |
| Not contaminated (FP) | astropy-7671, astropy-8872, django-11728, django-12155 |
| Reduced severity (BORDERLINE, not SEVERE) | astropy-13453, astropy-14539, astropy-13236 |

---

## Recommendations

### High Priority Fixes

1. **SNEAKY_TEST_MOD alignment analysis**: The detector must analyze the *content* of test modifications, not just whether the test file existed at the base commit. When all modified assertions have 0 misaligned assertions, the SNEAKY_TEST_MOD flag should be suppressed or downgraded. This would resolve 3 false positives (astropy-7671, astropy-8872, astropy-13236).

2. **is_doc_file heuristic fix**: The documentation path pattern must exclude `admindocs/` (and similar Django contrib app paths like `admin/`, `admindocs/`). A simple fix: require that the `docs` directory segment is a top-level or second-level directory, not a substring of a package name. This would resolve 2 false positives (django-11728, django-12155).

### Medium Priority Fixes

3. **Severity calibration**: Cases with split signals (some aligned tests + some misaligned tests, or a clean patch with test issues) should be classified as MODERATE rather than SEVERE. A SEVERE classification should require *multiple* independent contamination signals or a high ratio of misalignment across all tests/hunks.

4. **TEST_DESC_MISALIGN granularity**: The detector should distinguish between structural over-assertion (e.g., full HTML string comparison in astropy-13453) and semantic over-assertion (e.g., testing reader behavior in a writer task in astropy-14182). Structural over-assertion should be weighted lower.

### Low Priority Fixes

5. **SNEAKY_TEST_MOD hunk counting**: When a single test function has multiple hunks, the detector should aggregate them as one modification, not count each hunk separately. This inflated astropy-13236's signal from the 7 separate hunks to `test_ndarray_mixin`.

---

## Appendix: Evidence Summary Table

| Instance ID | Total Confidence | OVERTEST | OVERPATCH | SNEAKY | SCOPE_CREEP | TEST_MISALIGN | CIRCULAR | AMBIGUOUS | Verdict |
|-------------|-----------------|----------|-----------|--------|-------------|--------------|----------|-----------|---------|
| astropy-7606 | 1.00 | 1.00 | 0.25 | 1.00 | 0.00 | 0.50 | 0.00 | 0.20 | TRUE POSITIVE |
| astropy-7671 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.35 | FALSE POSITIVE |
| astropy-8872 | 1.00 | 1.00 | 0.17 | 1.00 | 0.00 | 0.00 | 0.00 | 0.30 | FALSE POSITIVE |
| astropy-13236 | 1.00 | 1.00 | 0.00 | 0.90 | 0.00 | 0.375 | 0.00 | 0.40 | FALSE POSITIVE |
| astropy-13398 | 0.98 | 0.75 | 0.56 | 0.00 | 0.30 | 0.32 | 0.00 | 0.55 | TRUE POSITIVE |
| astropy-13453 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 0.25 | BORDERLINE |
| astropy-14182 | 1.00 | 1.00 | 0.33 | 0.00 | 0.00 | 0.83 | 0.98 | 0.45 | TRUE POSITIVE |
| astropy-14365 | 1.00 | 1.00 | 0.25 | 0.90 | 0.00 | 1.00 | 0.00 | 0.20 | TRUE POSITIVE |
| astropy-14539 | 1.00 | 1.00 | 0.00 | 0.90 | 0.00 | 1.00 | 0.00 | 0.35 | BORDERLINE |
| django-10999 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.15 | TRUE POSITIVE |
| django-11532 | 0.81 | 0.00 | 0.55 | 0.00 | 0.45 | 0.00 | 0.00 | 0.25 | TRUE POSITIVE |
| django-11728 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 | FALSE POSITIVE |
| django-12155 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 | FALSE POSITIVE |
