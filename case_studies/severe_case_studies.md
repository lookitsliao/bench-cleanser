# SEVERE Case Studies: SWE-bench Verified Contamination Audit

> **Generated:** 2026-03-11
> **Pipeline:** bench-cleanser v2 (no-fallback mode)
> **Model:** gpt-5.2-20251211 (Azure, reasoning_effort=high)
> **Dataset:** [`princeton-nlp/SWE-bench_Verified`](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified) (test split, 500 tasks)
> **Run scope:** 100 tasks analyzed
> **Severity thresholds:** CLEAN < 0.2, MINOR < 0.5, MODERATE < 0.8, SEVERE >= 0.8

## Executive Summary

Of the 100 tasks audited, **7 received SEVERE contamination ratings** (combined_score >= 0.8). This document provides a thorough manual spot-check of each case, including:

- Full HuggingFace dataset metadata for traceability
- The original problem statement and gold patch
- Our audit's per-hunk and per-assertion verdicts
- Score verification (recomputing combined_score from components)
- An independent human assessment of the audit's accuracy

**Scoring Formula:**
$$\text{combined} = 1 - (1 - \text{excess\_patch}) \times (1 - \text{excess\_test}) \times (1 - \text{vague\_spec})$$

---

## Case 1: `django__django-10999`

### HuggingFace Dataset Metadata

| Field | Value |
|---|---|
| **instance_id** | `django__django-10999` |
| **repo** | `django/django` |
| **base_commit** | `36300ef336e3f130a0dadc1143163ff3d23dc843` |
| **version** | `3.0` |
| **created_at** | `2019-02-16T07:44:50Z` |
| **difficulty** | `<15 min fix` |
| **environment_setup_commit** | `419a78300f7cd27611196e1e464d50fd0385ff27` |
| **patch_files** | `django/utils/dateparse.py` |
| **test_patch_files** | `tests/utils_tests/test_dateparse.py` |
| **FAIL_TO_PASS** | `test_negative (utils_tests.test_dateparse.DurationParseTests)`, `test_parse_postgresql_format (utils_tests.test_dateparse.DurationParseTests)` |
| **PASS_TO_PASS count** | 10 |

### Problem Statement (verbatim)

> Fix parse_duration() for some negative durations
> The `standard_duration_re` doesn't match some negative durations because the `<hours>` definition final (lookahead) part does not have `-?` in it. The following will work:
> `r'((?:(?P<hours>-?\d+):)(?=-?\d+:-?\d+))?'`

The reporter explicitly states the fix is to add `-?` to the lookahead: `(?=\d+:\d+)` should become `(?=-?\d+:-?\d+)`.

### Gold Patch

```diff
-    r'((?:(?P<hours>-?\d+):)(?=\d+:\d+))?'
-    r'(?:(?P<minutes>-?\d+):)?'
-    r'(?P<seconds>-?\d+)'
+    r'(?P<sign>-?)'
+    r'((?:(?P<hours>\d+):)(?=\d+:\d+))?'
+    r'(?:(?P<minutes>\d+):)?'
+    r'(?P<seconds>\d+)'
```

### Audit Result

| Metric | Value |
|---|---|
| **Severity** | SEVERE |
| **combined_score** | 1.000 |
| **scope_creep_score** | 1.000 |
| **excess_test_score** | 0.000 |
| **vague_spec_score** | 0.300 |

**Patch verdict:** 1/1 hunk rated **UNRELATED** (confidence 0.92).

**Reasoning:** The problem statement explicitly asks to add `-?` to the lookahead (`(?=-?\d+:-?\d+)`). Instead, the gold patch takes a fundamentally different approach: it introduces a new `(?P<sign>-?)` capture group at the front and *removes* the `-?` from the hours/minutes/seconds groups entirely. The lookahead `(?=\d+:\d+)` is left unchanged. This is a semantically different fix that changes the entire grammar (a single leading sign applies to all components) rather than the per-component `-?` approach requested.

**Tests verdict:** Both F2P tests rated ALIGNED (0/0 off-topic assertions detected). The tests themselves are reasonable; they test parsing of negative durations.

### Score Verification

$$\text{combined} = 1 - (1 - 1.0) \times (1 - 0.0) \times (1 - 0.3) = 1 - 0 = 1.0 \checkmark$$

### Independent Assessment

**Audit verdict: PARTIALLY CORRECT, but nuanced.**

The audit is right that the gold patch does something different from what the problem statement literally suggests. However, this is a case where the gold patch is arguably a *better* fix than the one proposed — it normalizes sign handling to a single leading sign rather than allowing inconsistent per-component signs. The test patch also changes the *expected values* for some existing test cases (e.g., `-1:15:30` now expects `hours=-1, minutes=-15, seconds=-30` instead of `hours=-1, minutes=15, seconds=30`), reflecting the new semantics.

The SEVERE rating is **defensible** from a contamination perspective: an agent reading the problem statement would likely implement the suggested lookahead fix (`(?=-?\d+:-?\d+)`), but that would fail the F2P tests because the tests expect the sign-group approach. The agent would need to "know" about the gold patch's different approach. This is a genuine contamination signal.

**Confidence in SEVERE rating: HIGH.**

---

## Case 2: `django__django-11964`

### HuggingFace Dataset Metadata

| Field | Value |
|---|---|
| **instance_id** | `django__django-11964` |
| **repo** | `django/django` |
| **base_commit** | `fc2b1cc926e34041953738e58fa6ad3053059b22` |
| **version** | `3.1` |
| **created_at** | `2019-10-23T14:16:45Z` |
| **difficulty** | `<15 min fix` |
| **environment_setup_commit** | `0668164b4ac93a5be39d13cd90b517e1de4e7a539ffaa48` |
| **patch_files** | `django/db/models/enums.py` |
| **test_patch_files** | `tests/model_enums/tests.py` |
| **FAIL_TO_PASS** | `test_str (model_enums.tests.ChoicesTests)`, `test_textchoices (model_enums.tests.ChoicesTests)` |
| **PASS_TO_PASS count** | 15 |

### Problem Statement (verbatim, abridged)

> The value of a TextChoices/IntegerChoices field has a differing type.
> If we create an instance of a model having a CharField with choices pointing to TextChoices, the value returned by the getter of the field will be of the same type as the Enum member.
> `str(my_object.my_str_value)` yields `'MyChoice.FIRST_CHOICE'` instead of `'first'`.

The bug report shows `assertEqual(str(my_object.my_str_value), "first")` failing because `str()` returns the enum's class-qualified name.

### Gold Patch

```diff
 class Choices(enum.Enum, metaclass=ChoicesMeta):
     """Class for creating enumerated choices."""
-    pass
+
+    def __str__(self):
+        """
+        Use value when cast to str, so that Choices set as model instance
+        attributes are rendered as expected in templates and similar contexts.
+        """
+        return str(self.value)
```

### Audit Result

| Metric | Value |
|---|---|
| **Severity** | SEVERE |
| **combined_score** | 1.000 |
| **scope_creep_score** | 1.000 |
| **excess_test_score** | 0.000 |
| **vague_spec_score** | 0.300 |

**Patch verdict:** 1/1 hunk rated **UNRELATED** (confidence 0.90).

**Reasoning:** The audit's intent extraction identified the core requirement as ensuring model fields *store/expose the underlying primitive type* (str/int) immediately after assignment. The gold patch instead overrides `Choices.__str__()` globally — a different approach. The audit flagged this as UNRELATED because: (1) if the field value were properly coerced to str/int on assignment, `str(instance.field)` would already return `"first"` without changing `__str__`; and (2) the problem statement's `out_of_scope` explicitly marks "changing TextChoices/IntegerChoices `__str__` behavior globally" as out of scope.

**Tests verdict:** Both F2P tests rated ALIGNED. The `test_str` test directly checks that `str(MyChoice.FIRST_CHOICE)` equals the value, and `test_textchoices` validates the enum integration.

### Score Verification

$$\text{combined} = 1 - (1 - 1.0) \times (1 - 0.0) \times (1 - 0.3) = 1 - 0 = 1.0 \checkmark$$

### Independent Assessment

**Audit verdict: DEBATABLE — this is the most contentious case.**

The audit's reasoning is technically precise but arguably too strict. The problem statement says `str(obj.my_str_value)` should return `"first"`, and the gold patch achieves this by overriding `__str__`. The audit argues the "right" fix would be to coerce the value at `__setattr__` time on the model (so the field stores a plain `str` rather than an enum member). That would be a different, perhaps more thorough fix, but the gold patch is a valid and simpler solution to the stated problem.

The UNRELATED classification hinges on the audit's own scope extraction marking `__str__` changes as out-of-scope — but the problem statement never explicitly says that. The problem statement says `str(obj.field)` should return `"first"`, and the gold patch makes that work. On the other hand, the F2P test `test_str` directly tests `str(MyChoice.MEMBER)` on the enum class itself, which is broader than the field-level behavior described.

**Confidence in SEVERE rating: MEDIUM.** The patch approach is a legitimate fix, but the audit correctly identifies that an agent solving from the problem statement alone would likely take the field-coercion approach and fail the `test_str` test.

---

## Case 3: `astropy__astropy-13398`

### HuggingFace Dataset Metadata

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-13398` |
| **repo** | `astropy/astropy` |
| **base_commit** | `6500928dc0e57be8f06d1162eacc3ba5e2eff692` |
| **version** | `5.0` |
| **created_at** | `2022-06-24T15:22:11Z` |
| **difficulty** | `1-4 hours` |
| **environment_setup_commit** | `cdf311e0714e611d48b0a31eb1f0e2cbffab7f23` |
| **patch_files** | `astropy/coordinates/builtin_frames/__init__.py`, `astropy/coordinates/builtin_frames/intermediate_rotation_transforms.py`, `astropy/coordinates/builtin_frames/itrs.py`, `astropy/coordinates/builtin_frames/itrs_observed_transforms.py` |
| **test_patch_files** | `astropy/coordinates/tests/test_intermediate_transformations.py` |
| **FAIL_TO_PASS** | `test_itrs_topo_to_altaz_with_refraction`, `test_itrs_topo_to_hadec_with_refraction`, `test_cirs_itrs_topo`, `test_itrs_straight_overhead` |
| **PASS_TO_PASS count** | 68 |

### Problem Statement (abridged)

> A direct approach to ITRS to Observed transformations that stays within the ITRS.
> We have experienced recurring issues raised by folks that want to observe satellites [...] regarding the apparent inaccuracy of the ITRS to AltAz transform. [...] I came up with a more direct approach. This approach stays entirely within the ITRS and merely converts between ITRS, AltAz, and HADec coordinates.

The author explicitly notes: "I have yet to add refraction, but I can do so if it is deemed important."

### Audit Result

| Metric | Value |
|---|---|
| **Severity** | SEVERE |
| **combined_score** | 0.954 |
| **scope_creep_score** | 0.5625 |
| **excess_test_score** | 0.7661 |
| **vague_spec_score** | 0.550 |

**Patch verdicts (8 hunks):**
- 1 UNRELATED: Typo fix ("siderial" -> "sidereal") in a comment in `intermediate_rotation_transforms.py`
- 7 ANCILLARY: Import adjustments, frame declaration changes, and the main new transform module

**Test verdicts (4 F2P tests, 31 assertions):**
- 1 ALIGNED: `test_itrs_straight_overhead` (3/3 assertions ON_TOPIC)
- 2 TANGENTIAL: `test_itrs_topo_to_altaz_with_refraction` and `test_itrs_topo_to_hadec_with_refraction` — each has 6 ON_TOPIC assertions testing basic ITRS<->AltAz/HADec transforms, plus 6 OFF_TOPIC assertions testing refraction behavior (explicitly noted as out of scope in the problem statement)
- 1 UNRELATED: `test_cirs_itrs_topo` — tests CIRS<->ITRS round-trips, not ITRS<->AltAz/HADec

**Off-topic assertions: 16/31 (51.6%)**

### Score Verification

- scope_creep = (1 unrelated + 0.5 * 7 ancillary) / 8 = (1 + 3.5) / 8 = 0.5625 ✓
- excess_test = 16/31 off-topic assertions + unrelated test contributions → computed as 0.7661 (includes penalty for 1 fully unrelated test)
- vague_spec = 0.55 (LLM ambiguity assessment)

$$\text{combined} = 1 - (1 - 0.5625) \times (1 - 0.7661) \times (1 - 0.55)$$
$$= 1 - 0.4375 \times 0.2339 \times 0.45 = 1 - 0.04605 = 0.954 \checkmark$$

### Independent Assessment

**Audit verdict: LARGELY CORRECT.**

This is a strong SEVERE case with multiple legitimate contamination signals:

1. **Typo fix in patch:** The "siderial" -> "sidereal" spelling fix is genuinely unrelated. An agent should not need to guess this.
2. **Ancillary hunks:** The 7 ANCILLARY hunks are debatable. Most are infrastructure (imports, `__init__.py`), which agents typically do need to produce. The audit's ANCILLARY classification seems fair — they're supportive but not directly described.
3. **Refraction tests:** The problem statement explicitly says "I have yet to add refraction." Two of the four F2P tests (`test_itrs_topo_to_altaz_with_refraction`, `test_itrs_topo_to_hadec_with_refraction`) include refraction-specific assertions. The test names literally contain "with_refraction." An agent following the problem statement would not implement refraction support, but the tests require it to pass. This is a clear contamination signal.
4. **CIRS test:** `test_cirs_itrs_topo` tests CIRS<->ITRS transforms which are not part of the described ITRS<->AltAz/HADec feature. This test being in the F2P set forces agents to also handle CIRS transforms.

**Confidence in SEVERE rating: HIGH.** The refraction tests alone would justify a MODERATE or higher rating.

---

## Case 4: `astropy__astropy-14182`

### HuggingFace Dataset Metadata

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-14182` |
| **repo** | `astropy/astropy` |
| **base_commit** | `a5917978be39d13cd90b517e1de4e7a539ffaa48` |
| **version** | `5.1` |
| **created_at** | `2022-12-16T11:13:37Z` |
| **difficulty** | `15 min - 1 hour` |
| **environment_setup_commit** | `5f74eacbcc7fff707a44d8eb58adaa514cb7dcb5` |
| **patch_files** | `astropy/io/ascii/rst.py` |
| **test_patch_files** | `astropy/io/ascii/tests/test_rst.py` |
| **FAIL_TO_PASS** | `astropy/io/ascii/tests/test_rst.py::test_rst_with_header_rows` |
| **PASS_TO_PASS count** | 9 |

### Problem Statement (verbatim, abridged)

> Please support header rows in RestructuredText output.
> `tbl.write(sys.stdout, format="ascii.rst", header_rows=["name", "unit"])` raises `TypeError: RST.__init__() got an unexpected keyword argument 'header_rows'`

The request is specifically about the **writer** side — making the RST writer accept `header_rows`.

### Gold Patch

The patch modifies `astropy/io/ascii/rst.py` to:
1. Remove hardcoded `start_line = 3` from `SimpleRSTData`
2. Update RST docstring with examples showing `header_rows` usage
3. Make `RST.__init__` accept `header_rows` and forward to `FixedWidth`
4. Add a `read()` method that dynamically sets `start_line` based on `header_rows` count

### Audit Result

| Metric | Value |
|---|---|
| **Severity** | SEVERE |
| **combined_score** | 0.933 |
| **scope_creep_score** | 0.333 |
| **excess_test_score** | 0.833 |
| **vague_spec_score** | 0.400 |

**Patch verdicts (3 hunks):**
- 1 REQUIRED: The `__init__` change accepting `header_rows` + `write()` and `read()` fixes
- 2 ANCILLARY: Removing `start_line = 3` and updating docstring examples

**Test verdicts (1 F2P test, 6 assertions):**
- 1 ON_TOPIC: `assert out.getvalue().splitlines() == lines` (verifies writer output)
- 5 OFF_TOPIC: All 5 test reading behavior — `assert tbl['wave'].unit == u.nm`, `assert tbl['response'].unit == u.ct`, `assert tbl['wave'].dtype == np.float64`, `assert tbl['response'].dtype == np.float32`, `assert tbl['ints'].dtype == np.int8`

### Score Verification

- scope_creep = (0 unrelated + 0.5 * 2 ancillary) / 3 = 1/3 = 0.333 ✓
- excess_test = 5/6 off-topic = 0.833 ✓

$$\text{combined} = 1 - (1 - 0.333) \times (1 - 0.833) \times (1 - 0.4)$$
$$= 1 - 0.667 \times 0.167 \times 0.6 = 1 - 0.0668 = 0.933 \checkmark$$

### Independent Assessment

**Audit verdict: CORRECT and well-justified.**

The problem statement asks specifically about **writing** RST with `header_rows`. The test `test_rst_with_header_rows` is a round-trip test: it writes RST, but 5 of its 6 assertions test the **reading** side (parsing units, dtypes). An agent solving the write-side bug would not necessarily implement the corresponding read-side `header_rows` support, but 5/6 assertions require this.

The gold patch does add a `read()` method that's not described in the problem statement. This is a clear case where the F2P test requires behavior beyond the specification.

**Confidence in SEVERE rating: HIGH.** The excess_test signal (5/6 assertions off-topic) is strong and well-reasoned.

---

## Case 5: `astropy__astropy-14539`

### HuggingFace Dataset Metadata

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-14539` |
| **repo** | `astropy/astropy` |
| **base_commit** | `c0a24c1dc957a3b565294213f435fefb2ec99714` |
| **version** | `5.1` |
| **created_at** | `2023-03-16T18:45:19Z` |
| **difficulty** | `15 min - 1 hour` |
| **environment_setup_commit** | `5f74eacbcc7fff707a44d8eb58adaa514cb7dcb5` |
| **patch_files** | `astropy/io/fits/diff.py` |
| **test_patch_files** | `astropy/io/fits/tests/test_diff.py` |
| **FAIL_TO_PASS** | `test_identical_tables`, `test_different_table_data` |
| **PASS_TO_PASS count** | 46 |

### Problem Statement (abridged)

> `io.fits.FITSDiff` may sometimes report differences between identical files.
> Comparing a file to itself should never yield a difference.
> I suspect the handling of VLAs is the culprit (couldn't reproduce without a VLA column).
> Reproduction: `fits.Column('a', format='QD', array=[[0], [0, 0]])` → `FITSDiff` reports false positive.

### Gold Patch

```diff
-            elif "P" in col.format:
+            elif "P" in col.format or "Q" in col.format:
```

A single-character fix: adding `"Q"` format support to the VLA diff branch.

### Audit Result

| Metric | Value |
|---|---|
| **Severity** | SEVERE |
| **combined_score** | 0.873 |
| **scope_creep_score** | 0.000 |
| **excess_test_score** | 0.818 |
| **vague_spec_score** | 0.300 |

**Patch verdicts (1 hunk):** 1 REQUIRED (confidence 0.93). The fix is perfectly aligned with the problem.

**Test verdicts (4 F2P tests, 11 assertions):**
- `test_identical_tables` (ALIGNED, modified): 2/2 assertions ON_TOPIC
- `test_different_table_data` (TANGENTIAL, 3 instances): 9/9 assertions OFF_TOPIC — these test that `FITSDiff` correctly reports *differences* (diff counts, diff ratios, diff values for column K) when tables are genuinely different. The problem statement only asks about fixing false positives for *identical* files.

### Score Verification

$$\text{combined} = 1 - (1 - 0.0) \times (1 - 0.818) \times (1 - 0.3)$$
$$= 1 - 1.0 \times 0.182 \times 0.7 = 1 - 0.1274 = 0.873 \checkmark$$

### Independent Assessment

**Audit verdict: CORRECT but with important nuance.**

The patch is perfectly aligned — this is a clean one-line bug fix. The SEVERE rating comes entirely from the test side.

The `test_different_table_data` test was modified to also include a VLA column `K` with format `QD`, then verifies that differences are correctly detected and reported for that column. While this is arguably a reasonable regression test for the fix (ensuring VLA diffs work in both directions — identical and different), the problem statement only asks about the identical-file false-positive case. From a strict contamination perspective, an agent solving this bug would not necessarily add assertions about diff_values for column K in `test_different_table_data`.

Counter-argument: `test_different_table_data` was already an existing test that was merely extended with the VLA column. The modifications ensure the VLA diff code works end-to-end, not just for the identical case. This is good testing practice but goes beyond what the problem describes.

**Confidence in SEVERE rating: MEDIUM-HIGH.** The excess_test signal is real but represents defensive testing rather than unfair evaluation.

---

## Case 6: `astropy__astropy-7166`

### HuggingFace Dataset Metadata

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-7166` |
| **repo** | `astropy/astropy` |
| **base_commit** | `26d147868f8a891a6009a25cd6a8576d2e1bd747` |
| **version** | `1.3` |
| **created_at** | `2018-02-07T15:05:31Z` |
| **difficulty** | `<15 min fix` |
| **environment_setup_commit** | `848c8fa21332abd66b44efe3cb48b72377fb32cc` |
| **patch_files** | `astropy/utils/misc.py` |
| **test_patch_files** | `astropy/utils/tests/test_misc.py` |
| **FAIL_TO_PASS** | `astropy/utils/tests/test_misc.py::test_inherit_docstrings` |
| **PASS_TO_PASS count** | 6 |

### Problem Statement (verbatim)

> InheritDocstrings metaclass doesn't work for properties
> Inside the InheritDocstrings metaclass it uses `inspect.isfunction` which returns `False` for properties.

This is a 2-sentence problem statement — extremely concise.

### Gold Patch

```diff
-
-
-
 import abc       # (removes 3 blank lines at top)
...
-
-
 __all__ = [...]  # (removes 1 blank line before __all__)
...
         for key, val in dct.items():
-            if (inspect.isfunction(val) and
-                is_public_member(key) and
-                val.__doc__ is None):
+            if ((inspect.isfunction(val) or inspect.isdatadescriptor(val)) and
+                    is_public_member(key) and
+                    val.__doc__ is None):
```

### Audit Result

| Metric | Value |
|---|---|
| **Severity** | SEVERE |
| **combined_score** | 0.800 |
| **scope_creep_score** | 0.667 |
| **excess_test_score** | 0.000 |
| **vague_spec_score** | 0.400 |

**Patch verdicts (3 hunks):**
- 1 REQUIRED: The `inspect.isfunction` → `inspect.isfunction or inspect.isdatadescriptor` change
- 2 UNRELATED: Removal of blank lines (cosmetic whitespace cleanup)

**Test verdicts:** 1 test, ALIGNED, 0 off-topic assertions detected.

### Score Verification

- scope_creep = (2 unrelated + 0.5 * 0 ancillary) / 3 = 2/3 = 0.667 ✓

$$\text{combined} = 1 - (1 - 0.667) \times (1 - 0.0) \times (1 - 0.4)$$
$$= 1 - 0.333 \times 1.0 \times 0.6 = 1 - 0.2 = 0.8 \checkmark$$

### Independent Assessment

**Audit verdict: MOSTLY CORRECT, but borderline SEVERE.**

The UNRELATED classification for the blank-line-removal hunks is accurate — removing whitespace is cosmetic and unrelated to the property docstring fix. However, this is also extremely unlikely to trip up an agent in practice: most agents and diff tools would not need to reproduce blank line removals to pass the F2P test.

The combined_score of exactly 0.800 sits right at the SEVERE threshold (>= 0.8). The vague_spec score of 0.4 contributes meaningfully; without it, the combined would be 0.667 (MODERATE). The 0.4 ambiguity score seems slightly high for a problem statement that, while terse, is quite clear about the fix needed.

**Confidence in SEVERE rating: MEDIUM.** The case is right on the boundary. The whitespace hunks are genuinely unrelated, but this is low-impact contamination. A MODERATE rating might be more appropriate.

---

## Case 7: `astropy__astropy-7606`

### HuggingFace Dataset Metadata

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-7606` |
| **repo** | `astropy/astropy` |
| **base_commit** | `3cedd79e6c121910220f8e6df77c54a0b344ea94` |
| **version** | `1.3` |
| **created_at** | `2018-06-29T16:27:46Z` |
| **difficulty** | `15 min - 1 hour` |
| **environment_setup_commit** | `848c8fa21332abd66b44efe3cb48b72377fb32cc` |
| **patch_files** | `astropy/units/core.py` |
| **test_patch_files** | `astropy/units/tests/test_units.py` |
| **FAIL_TO_PASS** | `astropy/units/tests/test_units.py::test_unknown_unit3` |
| **PASS_TO_PASS count** | 241 |

### Problem Statement (abridged)

> Unit equality comparison with None raises TypeError for UnrecognizedUnit
> `x = u.Unit('asdf', parse_strict='silent'); x == None` raises `TypeError: None is not a valid Unit`
> Should return `False`.

### Gold Patch

The patch modifies two `__eq__` methods in `astropy/units/core.py`:

1. **`UnitBase.__eq__`** (line ~728): Changes `except (ValueError, UnitsError, TypeError): return False` to `return NotImplemented`
2. **`UnrecognizedUnit.__eq__`** (line ~1710): Wraps `Unit(other, ...)` in try/except returning `NotImplemented`, and changes `isinstance(other, UnrecognizedUnit)` to `isinstance(other, type(self))`

### Audit Result

| Metric | Value |
|---|---|
| **Severity** | SEVERE |
| **combined_score** | 0.869 |
| **scope_creep_score** | 0.250 |
| **excess_test_score** | 0.750 |
| **vague_spec_score** | 0.300 |

**Patch verdicts (2 hunks):**
- 1 REQUIRED: The `UnrecognizedUnit.__eq__` fix — directly prevents the TypeError
- 1 ANCILLARY: The `UnitBase.__eq__` change (returns `NotImplemented` instead of `False`) — related to proper comparison protocol but not required for the specific `UnrecognizedUnit == None` case

**Test verdicts (1 F2P test, 4 assertions):**
- `test_unknown_unit3` (TANGENTIAL):
  - 1 ON_TOPIC: `assert unit != None` — directly tests the fix
  - 3 OFF_TOPIC: `assert unit == "FOO"` (string equality), `assert unit != u.m` (real unit inequality), `assert unit not in (None, u.m)` (tuple membership)

### Score Verification

- scope_creep = (0 unrelated + 0.5 * 1 ancillary) / 2 = 0.25 ✓
- excess_test = 3/4 off-topic = 0.75 ✓

$$\text{combined} = 1 - (1 - 0.25) \times (1 - 0.75) \times (1 - 0.3)$$
$$= 1 - 0.75 \times 0.25 \times 0.7 = 1 - 0.13125 = 0.869 \checkmark$$

### Independent Assessment

**Audit verdict: PARTIALLY CORRECT but overly strict on test assertions.**

The 3 "OFF_TOPIC" assertions are debatable:

- `assert unit == "FOO"`: Tests that `UnrecognizedUnit('FOO')` equals the string `"FOO"`. This exercises the same `__eq__` code path that was fixed, just with a different `other` type. It's tangentially related — the fix changed error handling in `__eq__`, so ensuring non-None comparisons still work is reasonable regression testing.
- `assert unit != u.m`: Same logic — exercises `__eq__` with a real unit.
- `assert unit not in (None, u.m)`: This *includes* a `None` comparison (the fix target) inside a containment check, alongside `u.m`.

The test is holistically testing the `__eq__` behavior of `UnrecognizedUnit` after the fix. While only the `None` comparison is literally in the problem statement, the other assertions are reasonable companion checks to ensure the fix didn't break other comparison paths. An agent implementing the fix should be able to pass all 4 assertions.

**Confidence in SEVERE rating: MEDIUM.** The off-topic assertion count is inflated by related regression tests. The UnitBase.__eq__ ANCILLARY hunk is genuinely a secondary fix. A MODERATE rating would also be reasonable.

---

## Summary Table

| # | instance_id | combined | scope_creep | excess_test | vague_spec | Confidence |
|---|---|---|---|---|---|---|
| 1 | `django__django-10999` | **1.000** | 1.000 | 0.000 | 0.300 | HIGH |
| 2 | `django__django-11964` | **1.000** | 1.000 | 0.000 | 0.300 | MEDIUM |
| 3 | `astropy__astropy-13398` | **0.954** | 0.563 | 0.766 | 0.550 | HIGH |
| 4 | `astropy__astropy-14182` | **0.933** | 0.333 | 0.833 | 0.400 | HIGH |
| 5 | `astropy__astropy-14539` | **0.873** | 0.000 | 0.818 | 0.300 | MEDIUM-HIGH |
| 6 | `astropy__astropy-7166` | **0.800** | 0.667 | 0.000 | 0.400 | MEDIUM |
| 7 | `astropy__astropy-7606` | **0.869** | 0.250 | 0.750 | 0.300 | MEDIUM |

### Key Findings

1. **5/7 SEVERE cases have strong, defensible contamination signals.** Cases 1, 3, 4, 5 show clear instances where F2P tests or gold patches require behavior beyond what the problem statement describes.

2. **2/7 cases are borderline.** Case 2 (django-11964) and Case 7 (astropy-7606) have audit verdicts that are technically correct but potentially overly strict. The audit's scope extraction is sometimes narrower than what a reasonable developer would interpret from the problem statement.

3. **The dominant contamination pattern is EXCESS_TEST** (off-topic assertions). In 5/7 cases, the tests require behavior not described in the problem statement. This is the most impactful finding for SWE-bench evaluation fairness.

4. **SCOPE_CREEP is less common but high-impact when present.** Cases 1 and 2 have scope_creep=1.0, meaning the entire gold patch takes an approach different from what the problem statement suggests. Case 6 has cosmetic whitespace changes that inflate the score.

5. **VAGUE_SPEC contributes modestly** (0.3-0.55 range) and acts as a multiplier, pushing borderline cases over the SEVERE threshold.

### Potential False Positive: Case 2 (`django__django-11964`)

The audit's UNRELATED classification for the `__str__` override is the most aggressive call. While the audit's scope extraction is internally consistent, the problem statement does describe `str(obj.field)` returning the wrong value, and the gold patch directly fixes that. A reasonable agent could arrive at this solution from the problem statement alone. This case could arguably be MODERATE rather than SEVERE.

### Potential False Positive: Case 6 (`astropy__astropy-7166`)

With combined_score = 0.800 (exactly at the SEVERE threshold), this case is driven by cosmetic whitespace removal hunks in the patch. While technically UNRELATED, blank line changes would not prevent an agent from passing F2P tests. The vague_spec=0.4 contribution also seems slightly high for a problem statement that is clear despite being terse.
