# Deep-Dive Case Studies: 4 High-Confidence SEVERE Contamination Cases

> **Generated:** 2026-03-11
> **Pipeline:** bench-cleanser v2 (no-fallback mode), gpt-5.2-20251211 (Azure)
> **Dataset:** [`princeton-nlp/SWE-bench_Verified`](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified), test split
> **Purpose:** Exhaustive, assertion-level traceability for the 4 strongest SEVERE contamination signals

---

## Table of Contents

1. [Case A: django__django-10999 — Regex Approach Mismatch](#case-a-django__django-10999)
2. [Case B: astropy__astropy-13398 — Refraction Tests Beyond Specification](#case-b-astropy__astropy-13398)
3. [Case C: astropy__astropy-14182 — Writer Request, Reader Tests](#case-c-astropy__astropy-14182)
4. [Case D: astropy__astropy-14539 — Defensive Regression Tests Beyond Bug Report](#case-d-astropy__astropy-14539)

---

<a name="case-a-django__django-10999"></a>
## Case A: `django__django-10999` — "The Regex That Solves a Different Problem"

### A.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `django__django-10999` |
| **repo** | `django/django` |
| **base_commit** | `36300ef336e3f130a0dadc1143163ff3d23dc843` |
| **version** | `3.0` |
| **created_at** | `2019-02-16T07:44:50Z` |
| **difficulty** | `<15 min fix` |
| **environment_setup_commit** | `419a78300f7cd27611196e1e464d50fd0385ff27` |
| **FAIL_TO_PASS** | `["test_negative (utils_tests.test_dateparse.DurationParseTests)", "test_parse_postgresql_format (utils_tests.test_dateparse.DurationParseTests)"]` |
| **PASS_TO_PASS** | 10 tests covering `test_days`, `test_fractions_of_seconds`, `test_hours_minutes_seconds`, `test_iso_8601`, `test_minutes_seconds`, `test_parse_python_format`, `test_seconds`, etc. |
| **patch file** | `django/utils/dateparse.py` |
| **test_patch file** | `tests/utils_tests/test_dateparse.py` |

### A.2 Verbatim Problem Statement

> **Fix parse_duration() for some negative durations**
>
> The https://docs.djangoproject.com/en/2.1/_modules/django/utils/dateparse/ defines:
>
> ```python
> standard_duration_re = re.compile(
>     r'^'
>     r'(?:(?P<days>-?\d+) (days?, )?)?'
>     r'((?:(?P<hours>-?\d+):)(?=\d+:\d+))?'
>     r'(?:(?P<minutes>-?\d+):)?'
>     r'(?P<seconds>-?\d+)'
>     r'(?:\.(?P<microseconds>\d{1,6})\d{0,6})?'
>     r'$'
> )
> ```
>
> that doesn't match to negative durations, because of the `<hours>` definition final (lookahead) part does not have `-?` in it. The following will work:
>
> `r'((?:(?P<hours>-?\d+):)(?=-?\d+:-?\d+))?'`
>
> (Thanks to Konstantin Senichev for finding the fix.)

**Key observation:** The reporter provides a *specific regex fix* — add `-?` to the lookahead, changing `(?=\d+:\d+)` to `(?=-?\d+:-?\d+)`. This is an explicit, concrete, character-level prescription.

### A.3 Hints Text (from GitHub Discussion)

> *Please give an example valid that's not working. There are some tests for negative values.*
>
> *Right, this should have been fixed by #27699 which is included in 1.11.x.*
>
> *Example cases, can be discussed:*
> - `parse_duration('-00:01:01') => plus 61 seconds`, so it is not `-(00:01:01)` but `(-00):(+01):(+01)`
> - `parse_duration('00:-01:-01') => None`, leading zeros will prevent parsing
> - `parse_duration('-01:01') => minus 59 seconds`
> - `parse_duration('-01:-01') => minus 61 seconds`
>
> *The fix presented would allow the second line to be parsed (which would help with generated durations). And some instructions in the function/documentation/wiki would be useful, to clarify how the minus sign affects in duration.*
>
> *The fix from #27699 may not be entirely correct. I agree with your first and third examples. I'd expect a leading minus sign to negate the entire value so they would be minus 61 seconds. I think the second and fourth examples are invalid. I don't think a minus sign after a colon is valid.*
>
> *Thanks for the extra details. I agree with Tim that everything but a leading `-` seems like an invalid value that happened to work because of an inappropriate pattern as it was never tested.*

**Critical detail from hints:** The Django maintainers (Tim Graham) explicitly resolved the semantic debate: *"everything but a leading `-` seems like an invalid value."* This means the gold patch's approach (single leading sign) reflects the **maintainer decision** that was made during code review, NOT what was in the original problem statement.

### A.4 Complete Gold Patch (with annotation)

```diff
diff --git a/django/utils/dateparse.py b/django/utils/dateparse.py
--- a/django/utils/dateparse.py
+++ b/django/utils/dateparse.py
@@ -29,9 +29,10 @@
 standard_duration_re = re.compile(
     r'^'
     r'(?:(?P<days>-?\d+) (days?, )?)?'
-    r'((?:(?P<hours>-?\d+):)(?=\d+:\d+))?'   # ← REMOVED: -? from hours, unchanged lookahead
-    r'(?:(?P<minutes>-?\d+):)?'               # ← REMOVED: -? from minutes
-    r'(?P<seconds>-?\d+)'                     # ← REMOVED: -? from seconds
+    r'(?P<sign>-?)'                           # ← ADDED: new sign group at front
+    r'((?:(?P<hours>\d+):)(?=\d+:\d+))?'      # ← hours no longer allows -?
+    r'(?:(?P<minutes>\d+):)?'                  # ← minutes no longer allows -?
+    r'(?P<seconds>\d+)'                        # ← seconds no longer allows -?
     r'(?:\.(?P<microseconds>\d{1,6})\d{0,6})?'
     r'$'
 )
```

The gold patch **does not** add `-?` to the lookahead as suggested. Instead, it:

1. **Introduces a new named group** `(?P<sign>-?)` at the front of the pattern
2. **Removes** all `-?` optionals from `hours`, `minutes`, and `seconds` groups
3. **Leaves the lookahead `(?=\d+:\d+)` unchanged** — the exact lookahead the reporter said was broken

This fundamentally changes the semantics: instead of allowing per-component negative signs (`-1:15:-30`), the grammar now enforces a single leading sign that applies to all components (`-1:15:30` means hours=-1, minutes=-15, seconds=-30).

### A.5 Complete Test Patch

```diff
diff --git a/tests/utils_tests/test_dateparse.py b/tests/utils_tests/test_dateparse.py
--- a/tests/utils_tests/test_dateparse.py
+++ b/tests/utils_tests/test_dateparse.py
@@ -113,9 +113,12 @@ def test_negative(self):
         test_values = (
             ('-4 15:30', timedelta(days=-4, minutes=15, seconds=30)),
             ('-172800', timedelta(days=-2)),
-            ('-15:30', timedelta(minutes=-15, seconds=30)),
-            ('-1:15:30', timedelta(hours=-1, minutes=15, seconds=30)),
+            ('-15:30', timedelta(minutes=-15, seconds=-30)),         # ← CHANGED expected value
+            ('-1:15:30', timedelta(hours=-1, minutes=-15, seconds=-30)),  # ← CHANGED expected value
             ('-30.1', timedelta(seconds=-30, milliseconds=-100)),
+            ('-00:01:01', timedelta(minutes=-1, seconds=-1)),        # ← ADDED new test case
+            ('-01:01', timedelta(seconds=-61)),                       # ← ADDED new test case
+            ('-01:-01', None),                                        # ← ADDED new test case (invalid)
         )
         for source, expected in test_values:
             with self.subTest(source=source):
```

**Notice the changed expectations:**
- Old: `'-15:30'` → `timedelta(minutes=-15, seconds=30)` (only minutes negative)
- New: `'-15:30'` → `timedelta(minutes=-15, seconds=-30)` (both negative — sign applies to all)

This is the crux of the contamination: the test patch **changes the expected behavior** of existing test cases to match the gold patch's sign-group approach.

### A.6 Pipeline Verdict Detail

#### Intent Extraction (Stage 2)

The LLM extracted this intent **without seeing the gold patch**:

| Field | Value |
|---|---|
| **core_requirement** | Update `parse_duration()`'s `standard_duration_re` so it matches negative durations with an hours component |
| **behavioral_contract** | BEFORE: `parse_duration()` fails for some negative durations because the hours lookahead only allows `\d+:\d+`. AFTER: those strings match via a lookahead that allows optional `-` signs |
| **acceptance_criteria** | (1) `standard_duration_re`'s hours-group lookahead allows optional minus signs in minutes:seconds, (2) `parse_duration()` successfully parses duration strings with negative components that were previously rejected |
| **out_of_scope** | No changes to ISO 8601 parsing, no changes to how timedelta values are computed/normalized, no documentation or unrelated refactoring |
| **ambiguity_score** | 0.3 |

The intent extraction correctly identifies the lookahead fix as the ask. Note: the acceptance criterion #1 specifically says "lookahead allows optional minus signs" — exactly what the problem statement requests.

#### Patch Verdict (Stage 4A)

| Hunk | File | Verdict | Confidence | Reasoning |
|---|---|---|---|---|
| 0 | `django/utils/dateparse.py` | **UNRELATED** | 0.92 | The problem explicitly requests adding `-?` to the lookahead `(?=\d+:\d+)`. The gold patch instead introduces a new `(?P<sign>-?)` group and removes all per-component `-?` optionals. The lookahead is left unchanged. This implements a completely different grammar (single leading sign) than the one described. |

#### Test Verdict (Stage 4B)

| Test | Verdict | Assertions |
|---|---|---|
| `test_negative` | ALIGNED | (subTest pattern — assertion count not enumerable from static analysis) |
| `test_parse_postgresql_format` | ALIGNED | 0 off-topic assertions detected |

**Note:** The pipeline's assertion counter found only 1 formal assertion in the subTest loop structure. The F2P tests are technically aligned in that they test negative duration parsing — the contamination is entirely on the **patch** side.

#### Scoring Breakdown

| Component | Score | Derivation |
|---|---|---|
| excess_patch | **1.000** | 1 UNRELATED / 1 total = 1.0 |
| excess_test | **0.000** | 0 off-topic / 1 total assertions |
| vague_spec | **0.300** | LLM assessment: mostly clear, minor edge cases |

$$\text{combined} = 1 - (1 - 1.0)(1 - 0.0)(1 - 0.3) = 1 - 0 = \mathbf{1.000}$$

### A.7 Independent Deep Analysis

**Why the gold patch is different from the problem statement:**

The reporter's fix: `r'((?:(?P<hours>-?\d+):)(?=-?\d+:-?\d+))?'` — adds `-?` to the lookahead. This would allow patterns like `-1:-15:-30` to match, where each component independently has a sign. Under this grammar:
- `'-1:15:30'` → hours=-1, minutes=+15, seconds=+30
- `'-1:-15:-30'` → hours=-1, minutes=-15, seconds=-30

The gold patch's fix: `r'(?P<sign>-?)((?:(?P<hours>\d+):)(?=\d+:\d+))?...'` — introduces a single leading sign. Under this grammar:
- `'-1:15:30'` → sign='-', hours=1, minutes=15, seconds=30 → all negated: hours=-1, minutes=-15, seconds=-30
- `'-1:-15:-30'` → **does not match at all** (no `-?` in individual groups)

**The semantic difference is non-trivial:** `parse_duration('-1:15:30')` returns `timedelta(hours=-1, minutes=15, seconds=30)` under the old behavior (and the reporter's proposed fix), but `timedelta(hours=-1, minutes=-15, seconds=-30)` under the gold patch. The test patch explicitly changes the expected values to match the gold patch's semantics.

**Would an agent following the problem statement pass the tests?** Almost certainly NO. An agent reading the problem statement would:
1. See the explicit regex fix: add `-?` to the lookahead
2. Implement that fix
3. Run `test_negative` and find that `'-1:15:30'` now matches BUT produces `timedelta(hours=-1, minutes=15, seconds=30)` (old semantic)
4. The test expects `timedelta(hours=-1, minutes=-15, seconds=-30)` (gold patch semantic)
5. **FAIL**

The only way to pass is to know about the maintainer discussion (in hints_text) where they decided that "a leading `-` should negate the entire value." This information is NOT in the problem statement.

**Contamination verdict: CONFIRMED — HIGH CONFIDENCE.**

The gold patch's approach was a design decision made during code review, not derivable from the problem statement alone. The F2P tests enforce this specific design decision.

---

<a name="case-b-astropy__astropy-13398"></a>
## Case B: `astropy__astropy-13398` — "Tests Demand Refraction That the Spec Explicitly Defers"

### B.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-13398` |
| **repo** | `astropy/astropy` |
| **base_commit** | `6500928dc0e57be8f06d1162eacc3ba5e2eff692` |
| **version** | `5.0` |
| **created_at** | `2022-06-24T15:22:11Z` |
| **difficulty** | `1-4 hours` |
| **environment_setup_commit** | `cdf311e0714e611d48b0a31eb1f0e2cbffab7f23` |
| **FAIL_TO_PASS** | `["astropy/coordinates/tests/test_intermediate_transformations.py::test_itrs_topo_to_altaz_with_refraction", "astropy/coordinates/tests/test_intermediate_transformations.py::test_itrs_topo_to_hadec_with_refraction", "astropy/coordinates/tests/test_intermediate_transformations.py::test_cirs_itrs_topo", "astropy/coordinates/tests/test_intermediate_transformations.py::test_itrs_straight_overhead"]` |
| **PASS_TO_PASS** | 68 tests in `test_intermediate_transformations.py` |
| **patch files** | `builtin_frames/__init__.py`, `intermediate_rotation_transforms.py`, `itrs.py`, `itrs_observed_transforms.py` (new file, 145 lines) |
| **test_patch files** | `test_intermediate_transformations.py` |

### B.2 Verbatim Problem Statement (Key Excerpts)

> **A direct approach to ITRS to Observed transformations that stays within the ITRS.**
>
> We have experienced recurring issues raised by folks that want to observe satellites [...] regarding the apparent inaccuracy of the ITRS to AltAz transform. [...] I came up with a more direct approach. This approach stays entirely within the ITRS and merely converts between ITRS, AltAz, and HADec coordinates.
>
> **"I have yet to add refraction, but I can do so if it is deemed important."**

This last sentence is the critical line for contamination analysis.

### B.3 Hints Text (Community Discussion, abridged)

The hints text is 3,800+ characters of extensive GitHub discussion. Key points:

1. **Stuart Littlefair** supports the approach but wants error handling for nonsensical inputs
2. **Marten van Kerkwijk** wants to ensure the transform is used only when relevant (coordinates must have distance)
3. **The author (mkbrewer)** says: *"I already have the ability to transform to and from topocentric ITRS and Observed with the addition and removal of refraction tested and working."*
4. Discussion about `obstime` handling for ITRS<->ITRS transforms
5. Discussion about whether `SkyCoord` vs `TrueCoord` classes should handle satellites differently

**Critical hint from the discussion:** While the PR description says refraction is deferred, in a later comment the author says refraction is "tested and working". This means the gold patch includes refraction despite the problem statement deferring it, and the F2P tests require it.

### B.4 Gold Patch Summary

The gold patch is large (4 files, 8 hunks, ~250 lines added). Key components:

| File | Changes |
|---|---|
| `__init__.py` | Adds `from . import itrs_observed_transforms` (1 line) |
| `intermediate_rotation_transforms.py` | Fixes typo "siderial" → "sidereal"; modifies TETE↔ITRS and CIRS↔ITRS transforms to pass `location` through instead of forcing `EARTH_CENTER` |
| `itrs.py` | Adds `location` attribute to ITRS frame (EarthLocationAttribute), extensive docstring for topocentric ITRS |
| `itrs_observed_transforms.py` | **New file** (145 lines): Implements `itrs_to_observed()`, `observed_to_itrs()`, `add_refraction()`, `remove_refraction()` — full ITRS↔AltAz/HADec transforms with refraction support using `erfa.refco()` |

### B.5 Complete Test Patch — Line-by-Line Analysis

The test patch adds 4 new F2P tests totaling ~120 lines. Here is the assertion-level breakdown:

#### Test 1: `test_itrs_topo_to_altaz_with_refraction` (12 assertions)

```python
# --- SECTION 1: No-refraction ITRS→AltAz (ON_TOPIC) ---
assert_allclose(altaz11.az - altaz1.az, 0*u.mas, atol=0.1*u.mas)     # [0] ON_TOPIC
assert_allclose(altaz11.alt - altaz1.alt, 0*u.mas, atol=0.1*u.mas)    # [1] ON_TOPIC
assert_allclose(altaz11.distance - altaz1.distance, 0*u.cm, atol=10.0*u.cm)  # [2] ON_TOPIC

# --- SECTION 2: Round-trip ITRS→AltAz→ITRS (ON_TOPIC) ---
assert_allclose(itrs11.x, itrs.x)   # [3] ON_TOPIC
assert_allclose(itrs11.y, itrs.y)   # [4] ON_TOPIC
assert_allclose(itrs11.z, itrs.z)   # [5] ON_TOPIC

# --- SECTION 3: Refraction ITRS→AltAz (OFF_TOPIC — spec defers refraction) ---
assert_allclose(altaz22.az - altaz2.az, 0*u.mas, atol=0.1*u.mas)     # [6] OFF_TOPIC
assert_allclose(altaz22.alt - altaz2.alt, 0*u.mas, atol=0.1*u.mas)    # [7] OFF_TOPIC
assert_allclose(altaz22.distance - altaz2.distance, 0*u.cm, atol=10.0*u.cm)  # [8] OFF_TOPIC

# --- SECTION 4: Refraction removal (OFF_TOPIC) ---
assert_allclose(altaz33.az - altaz3.az, 0*u.mas, atol=0.1*u.mas)     # [9] OFF_TOPIC
assert_allclose(altaz33.alt - altaz3.alt, 0*u.mas, atol=0.1*u.mas)    # [10] OFF_TOPIC
assert_allclose(altaz33.distance - altaz3.distance, 0*u.cm, atol=10.0*u.cm)  # [11] OFF_TOPIC
```

**Result: 6 ON_TOPIC, 6 OFF_TOPIC.** The test is structurally split into halves: the first half tests non-refractive ITRS→AltAz transforms (described in the problem), the second half tests refraction (explicitly deferred).

#### Test 2: `test_itrs_topo_to_hadec_with_refraction` (12 assertions)

Identical structure to Test 1 but for HADec instead of AltAz:

```python
# No-refraction (ON_TOPIC): 6 assertions
assert_allclose(hadec11.ha - hadec1.ha, ...)   # ON_TOPIC
assert_allclose(hadec11.dec - hadec1.dec, ...)  # ON_TOPIC
assert_allclose(hadec11.distance - hadec1.distance, ...)  # ON_TOPIC
assert_allclose(itrs11.x, itrs.x)  # ON_TOPIC (round-trip)
assert_allclose(itrs11.y, itrs.y)  # ON_TOPIC
assert_allclose(itrs11.z, itrs.z)  # ON_TOPIC

# Refraction (OFF_TOPIC): 6 assertions
assert_allclose(hadec22.ha - hadec2.ha, ...)    # OFF_TOPIC
assert_allclose(hadec22.dec - hadec2.dec, ...)   # OFF_TOPIC
assert_allclose(hadec22.distance - hadec2.distance, ...)  # OFF_TOPIC
assert_allclose(hadec33.ha - hadec3.ha, ...)    # OFF_TOPIC
assert_allclose(hadec33.dec - hadec3.dec, ...)   # OFF_TOPIC
assert_allclose(hadec33.distance - hadec3.distance, ...)  # OFF_TOPIC
```

**Result: 6 ON_TOPIC, 6 OFF_TOPIC.**

#### Test 3: `test_cirs_itrs_topo` (4 assertions)

```python
def test_cirs_itrs_topo():
    """Check basic CIRS<->ITRS topocentric transforms for round-tripping."""
    loc = EarthLocation(lat=0*u.deg, lon=0*u.deg, height=0*u.m)
    usph = golden_spiral_grid(200)
    cirs = CIRS(usph, obstime='J2000', location=loc)
    cirs6 = CIRS(usph, obstime='J2006', location=loc)

    cirs2 = cirs.transform_to(ITRS(location=loc)).transform_to(cirs)
    cirs6_2 = cirs6.transform_to(ITRS(location=loc)).transform_to(cirs)

    assert_allclose(cirs.ra, cirs2.ra)       # [0] OFF_TOPIC
    assert_allclose(cirs.dec, cirs2.dec)      # [1] OFF_TOPIC
    assert not allclose(cirs.ra, cirs6_2.ra)  # [2] OFF_TOPIC
    assert not allclose(cirs.dec, cirs6_2.dec)  # [3] OFF_TOPIC
```

**Result: 0 ON_TOPIC, 4 OFF_TOPIC.** This test verifies CIRS↔ITRS topocentric round-tripping, which is NOT about ITRS↔AltAz/HADec transforms. It tests the intermediate transform infrastructure changes (CIRS→ITRS with `location=`), not the described feature.

#### Test 4: `test_itrs_straight_overhead` (3 assertions)

```python
def test_itrs_straight_overhead():
    """With a precise ITRS<->Observed transformation this should give Alt=90 exactly"""
    t = Time('J2010')
    obj = EarthLocation(-1*u.deg, 52*u.deg, height=10.*u.km)
    home = EarthLocation(-1*u.deg, 52*u.deg, height=0.*u.km)

    itrs_geo = obj.get_itrs(t).cartesian
    obsrepr = home.get_itrs(t).cartesian
    itrs_repr = itrs_geo - obsrepr  # topocentric subtraction

    itrs_topo = ITRS(itrs_repr, obstime=t, location=home)

    aa = itrs_topo.transform_to(AltAz(obstime=t, location=home))
    assert_allclose(aa.alt, 90*u.deg, atol=1*u.uas, rtol=0)  # [0] ON_TOPIC

    hd = itrs_topo.transform_to(HADec(obstime=t, location=home))
    assert_allclose(hd.ha, 0*u.hourangle, atol=1*u.uas, rtol=0)   # [1] ON_TOPIC
    assert_allclose(hd.dec, 52*u.deg, atol=1*u.uas, rtol=0)        # [2] ON_TOPIC
```

**Result: 3 ON_TOPIC, 0 OFF_TOPIC.** This test directly validates the core feature: topocentric ITRS → AltAz/HADec.

### B.6 Pipeline Verdict Detail

#### Intent Extraction

| Field | Value |
|---|---|
| **core_requirement** | Implement direct transform paths for ITRS↔AltAz and ITRS↔HADec using topocentric geometry |
| **out_of_scope** | *"Adding atmospheric refraction support (explicitly noted as not yet implemented and only optional), changing the general ITRS→ITRS transformation semantics"* |
| **ambiguity_score** | 0.55 |

The LLM correctly identified refraction as out of scope based on the problem statement's explicit deferral.

#### Patch Verdicts (8 hunks)

| # | File | Verdict | Conf. | Note |
|---|---|---|---|---|
| 0 | `__init__.py` | ANCILLARY | 0.95 | Heuristic: import-only `__init__.py` change |
| 1 | `intermediate_rotation_transforms.py` (typo) | **UNRELATED** | 0.97 | "siderial" → "sidereal" spelling fix |
| 2 | `intermediate_rotation_transforms.py` (TETE→ITRS) | ANCILLARY | 0.50 | Location passthrough instead of EARTH_CENTER |
| 3 | `intermediate_rotation_transforms.py` (ITRS→TETE) | ANCILLARY | 0.50 | Matching change for inverse |
| 4 | `intermediate_rotation_transforms.py` (CIRS→ITRS) | ANCILLARY | 0.50 | Location passthrough for CIRS path |
| 5 | `intermediate_rotation_transforms.py` (ITRS→CIRS) | ANCILLARY | 0.50 | Matching inverse |
| 6 | `itrs.py` | ANCILLARY | 0.50 | Frame attribute + docstring for topocentric ITRS |
| 7 | `itrs_observed_transforms.py` | ANCILLARY | 0.50 | Entire new module (145 lines, includes refraction) |

**Commentary on ANCILLARY verdicts:** The pipeline classified the main transform module (`itrs_observed_transforms.py`) as ANCILLARY rather than REQUIRED. This is arguably too conservative — the new module IS the feature. However, because it includes both the described transforms AND unmentioned refraction code (~60 lines of `add_refraction`/`remove_refraction`), the LLM was split. The ANCILLARY verdicts at 0.50 confidence reflect genuine uncertainty.

#### Test Verdicts

| Test | Verdict | ON_TOPIC | OFF_TOPIC |
|---|---|---|---|
| `test_itrs_topo_to_altaz_with_refraction` | TANGENTIAL | 6 | 6 |
| `test_itrs_topo_to_hadec_with_refraction` | TANGENTIAL | 6 | 6 |
| `test_cirs_itrs_topo` | UNRELATED | 0 | 4 |
| `test_itrs_straight_overhead` | ALIGNED | 3 | 0 |
| **Total** | | **15** | **16** |

#### Scoring Breakdown

| Component | Score | Derivation |
|---|---|---|
| excess_patch | 0.5625 | (1 UNRELATED + 0.5 × 7 ANCILLARY) / 8 = 4.5/8 |
| excess_test | 0.7661 | 16 OFF_TOPIC/31 total + UNRELATED test penalty |
| vague_spec | 0.5500 | LLM: moderately ambiguous (complex feature with many considerations) |

$$\text{combined} = 1 - (1 - 0.5625)(1 - 0.7661)(1 - 0.55) = 1 - 0.4375 \times 0.2339 \times 0.45 = 1 - 0.04605 = \mathbf{0.954}$$

### B.7 Independent Deep Analysis

**The smoking gun is the test names themselves.** Two of the four F2P tests are literally named `test_itrs_topo_to_altaz_with_refraction` and `test_itrs_topo_to_hadec_with_refraction`. The problem statement says "I have yet to add refraction." These test names advertise behavior the spec explicitly defers.

**What an honest agent would produce:**
1. ITRS↔AltAz and ITRS↔HADec transforms using topocentric geometry — YES
2. Refraction support via `erfa.refco()` — NO (not mentioned, explicitly deferred)
3. CIRS↔ITRS topocentric transforms — MAYBE (the infrastructure changes are necessary, but testing them separately wasn't requested)

**What the F2P tests require to pass:**
1. Non-refractive ITRS→AltAz/HADec transforms — YES
2. Refractive ITRS→AltAz/HADec transforms (pressure > 0) — YES (tests fail without `add_refraction`/`remove_refraction`)
3. CIRS↔ITRS topocentric round-trips — YES

Items 2 and 3 go beyond the specification. An agent would need ~60 lines of refraction code (using `erfa.refco()`, `erfa.pn()`, `erfa.c2s()`, `erfa.s2c()`) that the problem statement never mentions.

**Additional note on the typo fix.** Hunk 1 changes `siderial` → `sidereal` in a code comment. This is completely unrelated to the feature. While trivial, it means the gold patch includes a cosmetic fix that an agent would never guess. Notably, this specific diff hunk is in `intermediate_rotation_transforms.py` which is also where the infrastructure changes are — so an agent touching this file might or might not notice the typo, introducing a luck-based variable into evaluation.

**Contamination verdict: CONFIRMED — HIGH CONFIDENCE.**

---

<a name="case-c-astropy__astropy-14182"></a>
## Case C: `astropy__astropy-14182` — "Asked for a Writer Fix, Tested the Reader"

### C.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-14182` |
| **repo** | `astropy/astropy` |
| **base_commit** | `a5917978be39d13cd90b517e1de4e7a539ffaa48` |
| **version** | `5.1` |
| **created_at** | `2022-12-16T11:13:37Z` |
| **difficulty** | `15 min - 1 hour` |
| **environment_setup_commit** | `5f74eacbcc7fff707a44d8eb58adaa514cb7dcb5` |
| **FAIL_TO_PASS** | `["astropy/io/ascii/tests/test_rst.py::test_rst_with_header_rows"]` |
| **PASS_TO_PASS** | 9 existing RST tests |
| **hints_text** | (empty) |
| **patch file** | `astropy/io/ascii/rst.py` |
| **test_patch file** | `astropy/io/ascii/tests/test_rst.py` |

### C.2 Verbatim Problem Statement

> **Please support header rows in RestructuredText output**
>
> It would be great if the following would work:
>
> ```python
> >>> tbl.write(sys.stdout, format="ascii.rst", header_rows=["name", "unit"])
> ```
>
> Currently raises:
> ```
> TypeError: RST.__init__() got an unexpected keyword argument 'header_rows'
> ```
>
> RestructuredText output is a great way to fill autogenerated documentation with content, so having this flexible makes the life easier `:-)`

The request is unambiguous: make the **writer** accept `header_rows`. No mention of reading RST with `header_rows`, no mention of round-trip capability.

### C.3 Gold Patch — Annotated

The gold patch modifies `astropy/io/ascii/rst.py` in 3 hunks:

#### Hunk 0: Remove hardcoded `start_line`

```diff
 class SimpleRSTData(FixedWidthData):
-    start_line = 3
     end_line = -1
```

This removes the hardcoded `start_line = 3` to allow dynamic calculation. This change is **required for the reader to work with variable header rows** but is NOT related to the writer feature that was requested.

#### Hunk 1: Update docstring

```diff
     Example::

-        ==== ===== ======
-        Col1  Col2  Col3
-        ==== ===== ======
-          1    2.3  Hello
-          2    4.5  Worlds
-        ==== ===== ======
+      >>> from astropy.table import QTable
+      >>> import astropy.units as u
+      >>> import sys
+      >>> tbl = QTable({"wave": [350, 950] * u.nm, "response": [0.7, 1.2] * u.count})
+      >>> tbl.write(sys.stdout,  format="ascii.rst")
+      [output...]
+
+    Like other fixed-width formats, when writing a table you can provide ``header_rows``
+    to specify a list of table rows to output as the header.  For example::
+
+      >>> tbl.write(sys.stdout,  format="ascii.rst", header_rows=['name', 'unit'])
+      [output with units row...]
```

Docstring updates showing the new writer functionality.

#### Hunk 2: Core implementation

```diff
-    def __init__(self):
-        super().__init__(delimiter_pad=None, bookend=False)
+    def __init__(self, header_rows=None):
+        super().__init__(delimiter_pad=None, bookend=False, header_rows=header_rows)

     def write(self, lines):
         lines = super().write(lines)
-        lines = [lines[1]] + lines + [lines[1]]
+        idx = len(self.header.header_rows)
+        lines = [lines[idx]] + lines + [lines[idx]]
         return lines
+
+    def read(self, table):
+        self.data.start_line = 2 + len(self.header.header_rows)
+        return super().read(table)
```

This hunk does THREE things:
1. `__init__` now accepts `header_rows` — **directly requested**
2. `write()` uses `header_rows` count for separator placement — **directly requested**
3. `read()` method added for dynamic `start_line` — **NOT requested** (reader support)

### C.4 The F2P Test — Line-by-Line

```python
def test_rst_with_header_rows():
    """Round-trip a table with header_rows specified"""      # ← Note: "Round-trip"
    lines = [
        "======= ======== ====",
        "   wave response ints",
        "     nm       ct     ",
        "float64  float32 int8",
        "======= ======== ====",
        "  350.0      1.0    1",
        "  950.0      2.0    2",
        "======= ======== ====",
    ]
    # --- READER ASSERTIONS (OFF_TOPIC) ---
    tbl = QTable.read(lines, format="ascii.rst", header_rows=["name", "unit", "dtype"])
    assert tbl["wave"].unit == u.nm          # [0] ← OFF_TOPIC: tests reader parsing of units
    assert tbl["response"].unit == u.ct      # [1] ← OFF_TOPIC: tests reader parsing of units
    assert tbl["wave"].dtype == np.float64   # [2] ← OFF_TOPIC: tests reader parsing of dtype
    assert tbl["response"].dtype == np.float32  # [3] ← OFF_TOPIC: tests reader parsing of dtype
    assert tbl["ints"].dtype == np.int8      # [4] ← OFF_TOPIC: tests reader parsing of dtype

    # --- WRITER ASSERTION (ON_TOPIC) ---
    out = StringIO()
    tbl.write(out, format="ascii.rst", header_rows=["name", "unit", "dtype"])
    assert out.getvalue().splitlines() == lines  # [5] ← ON_TOPIC: tests writer output
```

### C.5 Pipeline Verdict Detail

#### Intent Extraction

| Field | Value |
|---|---|
| **core_requirement** | Allow the `ascii.rst` table writer to accept and honor the `header_rows` argument |
| **acceptance_criteria** | (1) `QTable.write(..., format='ascii.rst', header_rows=['name', 'unit'])` must not raise TypeError, (2) Output with `header_rows` must include units row, (3) Default behavior (no `header_rows`) preserved |
| **out_of_scope** | *"Adding support for `header_rows` when **reading** RST"*, unrelated formatting changes, broad refactors |
| **ambiguity_score** | 0.4 |

The LLM explicitly identified RST **reading** with `header_rows` as out of scope.

#### Test Verdict

| Test | Verdict | ON_TOPIC | OFF_TOPIC |
|---|---|---|---|
| `test_rst_with_header_rows` | TANGENTIAL | 1 | 5 |

#### Per-Assertion Verdict Table

| # | Assertion | Verdict | Reason |
|---|---|---|---|
| 0 | `assert tbl["wave"].unit == u.nm` | **OFF_TOPIC** | Tests that the RST **reader** correctly parses unit metadata from header rows — problem statement only asks about the writer |
| 1 | `assert tbl["response"].unit == u.ct` | **OFF_TOPIC** | Same: reader unit parsing |
| 2 | `assert tbl["wave"].dtype == np.float64` | **OFF_TOPIC** | Tests reader dtype parsing from a dtype header row |
| 3 | `assert tbl["response"].dtype == np.float32` | **OFF_TOPIC** | Same: reader dtype parsing |
| 4 | `assert tbl["ints"].dtype == np.int8` | **OFF_TOPIC** | Same: reader dtype parsing |
| 5 | `assert out.getvalue().splitlines() == lines` | **ON_TOPIC** | Directly verifies that `.write()` with `header_rows` produces correct RST output |

#### Scoring Breakdown

| Component | Score | Derivation |
|---|---|---|
| excess_patch | 0.333 | (0 UNRELATED + 0.5 × 2 ANCILLARY) / 3 = 1/3 |
| excess_test | 0.833 | 5 OFF_TOPIC / 6 total assertions |
| vague_spec | 0.400 | Mostly clear, some implied scope questions |

$$\text{combined} = 1 - (1 - 0.333)(1 - 0.833)(1 - 0.4) = 1 - 0.667 \times 0.167 \times 0.6 = 1 - 0.0668 = \mathbf{0.933}$$

### C.6 Independent Deep Analysis

**This is the cleanest contamination case of all four.** The analysis is straightforward:

1. Problem statement asks for **writer** support of `header_rows` in `ascii.rst`.
2. Gold patch implements writer support AND reader support (a `read()` method).
3. The single F2P test is a "round-trip" test that reads RST with `header_rows`, checks the parsed table's units and dtypes (reader functionality), then writes it back.
4. **5 of 6 assertions test the reader**, which was never requested.

**Would an agent pass with writer-only changes?** NO. The test calls `QTable.read(lines, format="ascii.rst", header_rows=["name", "unit", "dtype"])`. Without the `read()` method and the `start_line` fix, this read call would fail (or misparse), causing the entire test function to error before reaching the writer assertion.

**What if an agent only implements the writer?** The agent would:
1. Add `header_rows` to `RST.__init__()` — passes assertion [5]
2. NOT add `read()` method — `QTable.read()` call fails with wrong `start_line`
3. Test errors at line `tbl = QTable.read(...)`, all 6 assertions fail
4. **COMPLETE FAILURE** despite correctly implementing what was asked

This means a 100% correct implementation of the stated problem would score 0% on the F2P test. The reader functionality is a prerequisite for the test to even reach the writer assertion.

**Contamination verdict: CONFIRMED — HIGH CONFIDENCE.** This is arguably the most clear-cut contamination case in the entire dataset.

---

<a name="case-d-astropy__astropy-14539"></a>
## Case D: `astropy__astropy-14539` — "One-Character Fix, Nine Extra Assertions"

### D.1 HuggingFace Dataset Record

| Field | Value |
|---|---|
| **instance_id** | `astropy__astropy-14539` |
| **repo** | `astropy/astropy` |
| **base_commit** | `c0a24c1dc957a3b565294213f435fefb2ec99714` |
| **version** | `5.1` |
| **created_at** | `2023-03-16T18:45:19Z` |
| **difficulty** | `15 min - 1 hour` |
| **environment_setup_commit** | `5f74eacbcc7fff707a44d8eb58adaa514cb7dcb5` |
| **FAIL_TO_PASS** | `["astropy/io/fits/tests/test_diff.py::TestDiff::test_identical_tables", "astropy/io/fits/tests/test_diff.py::TestDiff::test_different_table_data"]` |
| **PASS_TO_PASS** | 46 diff-related tests |
| **patch file** | `astropy/io/fits/diff.py` |
| **test_patch file** | `astropy/io/fits/tests/test_diff.py` |

### D.2 Verbatim Problem Statement

> **`io.fits.FITSDiff` may sometimes report differences between identical files**
>
> In some scenarios, `io.fits.FITSDiff` may report differences between identical files, even when comparing the same file to itself. This may be caused by improper handling of VLAs (variable-length arrays).
>
> **Expected behavior:** `io.fits.FITSDiff` only reports differences in files if they exist. Comparing a file to itself should never yield a difference.
>
> **How to Reproduce:**
> ```python
> from astropy.io import fits
> col = fits.Column('a', format='QD', array=[[0], [0, 0]])
> hdu = fits.BinTableHDU.from_columns([col])
> hdu.writeto('diffbug.fits', overwrite=True)
>
> print(fits.FITSDiff('diffbug.fits', 'diffbug.fits').identical)
> fits.printdiff('diffbug.fits', 'diffbug.fits')
> ```
> Prints `False` — should be `True`.
>
> I suspect the handling of VLAs is the culprit here as I couldn't reproduce the bug without using at least one VLA column.

### D.3 Hints Text

> Seems due to the use of `Q`, only `P` is handled in the diff code. This:
> ```diff
> -            elif "P" in col.format:
> +            elif "P" in col.format or "Q" in col.format:
> ```
> seems to work, but would need some tests etc. Do you want to work on a fix?
>
> I'm not particularly familiar with `FITSDiff` I'd rather not handle the PR.

**Key observation:** The hints text literally provides the one-line fix. The exact same change appears in the gold patch.

### D.4 Complete Gold Patch

```diff
diff --git a/astropy/io/fits/diff.py b/astropy/io/fits/diff.py
--- a/astropy/io/fits/diff.py
+++ b/astropy/io/fits/diff.py
@@ -1449,7 +1449,7 @@ def _diff(self):
                 arrb.dtype, np.floating
             ):
                 diffs = where_not_allclose(arra, arrb, rtol=self.rtol, atol=self.atol)
-            elif "P" in col.format:
+            elif "P" in col.format or "Q" in col.format:
                 diffs = (
                     [
                         idx
```

This is a textbook one-line bug fix: `"P"` → `"P" or "Q"`.  The `Q` format descriptor is used for 64-bit VLAs (vs `P` for 32-bit VLAs). The diff code only checked for `P`, so `Q`-format columns fell through to the generic comparison path, which doesn't handle VLAs correctly.

**The patch itself is perfectly aligned with the problem.**

### D.5 Complete Test Patch — Detailed Analysis

The test patch modifies two existing tests:

#### Test 1: `test_identical_tables` (MODIFIED)

```diff
         c10 = Column("J", format="PI(2)", array=[[0, 1], [2, 3]])
+        c11 = Column("K", format="QJ(2)", array=[[0, 1], [2, 3]])   # ← ADDED: Q-format column

-        columns = [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10]
+        columns = [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11]

         diff = TableDataDiff(ta.data, tb.data)
         assert diff.identical                            # [0] ON_TOPIC: identical check
-        assert len(diff.common_columns) == 10
-        assert diff.common_column_names == set("abcdefghij")
+        assert len(diff.common_columns) == 11           # [1] ON_TOPIC: updated count
+        assert diff.common_column_names == set("abcdefghijk")  # [2] minor update for new column
         assert diff.diff_ratio == 0
         assert diff.diff_total == 0
```

**2 ON_TOPIC assertions** (the core test: `diff.identical` must be `True`, and the column count/names reflect the added VLA column).

#### Test 2: `test_different_table_data` (MODIFIED, x3 instances in F2P)

This is where the contamination signal appears. The existing test creates two different tables and verifies that `FITSDiff` correctly reports their differences. The test patch adds a `Q`-format column `K` to both tables:

```diff
+        ca11 = Column("K", format="QJ(2)", array=[[0, 1], [2, 3]])
         ...
+        cb11 = Column("K", format="QJ(2)", array=[[1, 2], [3, 4]])   # Different values
         ...
         # New assertions verifying diff detection for column K:
+        assert diff.diff_values[13][0] == ("K", 0)           # [NEW] OFF_TOPIC
+        assert (diff.diff_values[13][1][0] == [0, 1]).all()   # [NEW] OFF_TOPIC
+        assert (diff.diff_values[13][1][1] == [1, 2]).all()   # [NEW] OFF_TOPIC
+        assert diff.diff_values[14][0] == ("K", 1)            # [NEW] OFF_TOPIC
+        assert (diff.diff_values[14][1][0] == [2, 3]).all()   # [NEW] OFF_TOPIC
+        assert (diff.diff_values[14][1][1] == [3, 4]).all()   # [NEW] OFF_TOPIC

-        assert diff.diff_total == 13
-        assert diff.diff_ratio == 0.65
+        assert diff.diff_total == 15                          # [CHANGED] OFF_TOPIC
+        assert np.isclose(diff.diff_ratio, 0.682, atol=1e-3, rtol=0)  # [CHANGED] OFF_TOPIC

-        assert "13 different table data element(s) found (65.00% different)" in report
+        assert "15 different table data element(s) found (68.18% different)" in report  # [CHANGED] OFF_TOPIC
```

### D.6 Pipeline Verdict Detail

#### Intent Extraction

| Field | Value |
|---|---|
| **core_requirement** | Fix `FITSDiff` false positive for identical files with VLA columns |
| **acceptance_criteria** | (1) `FITSDiff(file, file).identical` returns `True` for VLA files, (2) `printdiff` reports no diffs for identical VLA files, (3) No false positives from VLA presence |
| **out_of_scope** | Changing public API, modifying FITS file writing/reading, altering non-VLA diff semantics, adding new diff features |
| **ambiguity_score** | 0.3 |

#### Per-Test and Per-Assertion Verdicts

| Test | Verdict | ON_TOPIC | OFF_TOPIC |
|---|---|---|---|
| `test_identical_tables` | ALIGNED (modified) | 2 | 0 |
| `test_different_table_data` (instance 1) | TANGENTIAL | 0 | 3 |
| `test_different_table_data` (instance 2) | TANGENTIAL | 0 | 3 |
| `test_different_table_data` (instance 3) | TANGENTIAL | 0 | 3 |
| **Total** | | **2** | **9** |

**Why `test_different_table_data` appears 3 times:** The pipeline identified 3 separate hunk ranges within the same test function (the column addition, the assertion additions, and the updated counts). Each was evaluated independently.

#### Detailed Assertion Reasoning

| # | Assertion | Verdict | Reasoning |
|---|---|---|---|
| 0 | `diff.diff_values[13][0] == ("K", 0)` | OFF_TOPIC | Tests that `FITSDiff` correctly reports *differences* for column K row 0 — the problem only asks about false positives for *identical* files |
| 1 | `(diff.diff_values[13][1][0] == [0, 1]).all()` | OFF_TOPIC | Verifies the exact diff values reported for column K — beyond the identical-file bug |
| 2 | `(diff.diff_values[13][1][1] == [1, 2]).all()` | OFF_TOPIC | Same: verifying diff output detail |
| 3 | `diff.diff_values[14][0] == ("K", 1)` | OFF_TOPIC | Column K row 1 diff detection |
| 4-5 | `diff.diff_values[14][1][0/1]` | OFF_TOPIC | Exact values for K row 1 |
| 6 | `diff.diff_total == 15` | OFF_TOPIC | Updated total diff count (was 13, now 15 with K's 2 rows) |
| 7 | `np.isclose(diff.diff_ratio, 0.682, ...)` | OFF_TOPIC | Updated diff ratio |
| 8 | `"15 different table data element(s) found (68.18% different)"` | OFF_TOPIC | Updated report string |

#### Scoring Breakdown

| Component | Score | Derivation |
|---|---|---|
| excess_patch | 0.000 | 1 REQUIRED / 1 total = no excess |
| excess_test | 0.818 | 9 OFF_TOPIC / 11 total assertions |
| vague_spec | 0.300 | Clear problem statement |

$$\text{combined} = 1 - (1 - 0.0)(1 - 0.818)(1 - 0.3) = 1 - 1.0 \times 0.182 \times 0.7 = 1 - 0.1274 = \mathbf{0.873}$$

### D.7 Independent Deep Analysis

**The patch is clean — the contamination is purely in the tests.**

The gold patch is exactly the one-line fix described in the hints. It perfectly addresses the bug. The issue is that the test evaluators modified `test_different_table_data` to also verify that `Q`-format columns work in the **diff-detection** path (comparing genuinely different tables), not just the identical-file path that the bug report describes.

**What an agent would produce:**

An agent reading the problem statement and hints would:
1. Add `or "Q" in col.format` — correct fix ✓
2. Add/modify `test_identical_tables` to include a `Q`-format column — this is reasonable ✓
3. **Not necessarily** add a `Q`-format column to `test_different_table_data` — this tests a different scenario (correctly detecting differences, not fixing false positives)

**Would the agent's fix pass?** The agent's fix would pass `test_identical_tables` but fail `test_different_table_data` because:
- The test expects `diff.diff_total == 15` (with column K contributing 2 diffs)
- Without adding column K to both tables in `test_different_table_data`, the test would find 13 total diffs
- The assertions for `diff.diff_values[13]` and `diff.diff_values[14]` would fail (these indices don't exist without column K)

**Nuance:** In this case, an agent that modifies `diff.py` would actually make `test_different_table_data` PASS with its existing assertions (since the test_patch modifies the test, not the code-under-test). The F2P mechanism means the test must FAIL before the fix and PASS after. Since `test_different_table_data` previously had no Q-format column, it *would have passed before the fix anyway*. The test only fails before the fix because the test_patch adds the Q-format column, and the old code can't diff it properly. So the test IS testing the fix, just in a scenario beyond what the problem described.

This makes the contamination more subtle: the test modifications are legitimate regression tests, but they require the agent to produce a test patch that extends `test_different_table_data` in a very specific way — adding column K with specific data values and updating exact numeric assertions (15, 0.682, 68.18%).

**Contamination verdict: CONFIRMED — MEDIUM-HIGH CONFIDENCE.** The off-topic assertions are legitimate regression tests, but their specificity (exact diff counts, ratios, and values) goes well beyond verifying the bug fix. The 9 off-topic assertions test "Q-format columns diff correctly when tables are different" rather than "Q-format columns don't cause false positives when tables are identical."

---

## Cross-Case Synthesis

### Contamination Pattern Taxonomy

| Pattern | Cases | Description |
|---|---|---|
| **Approach Mismatch** | A | Problem suggests fix X; gold patch implements fix Y; tests enforce Y's semantics |
| **Scope Creep in Tests** | B, D | Tests verify behavior explicitly deferred or beyond the bug scope |
| **Feature Split** | C | Problem asks for feature X; gold patch implements X+Y; test requires both |

### Impact on SWE-bench Evaluation

The contamination in these cases creates an unfair evaluation dynamic:

1. **An agent that perfectly solves the stated problem can score 0%.** Case C demonstrates this most clearly: a correct writer-only implementation fails because the test doesn't even reach the writer assertion — it errors on the reader assertion first.

2. **Knowledge of the gold patch is required.** In Case A, the problem statement provides a specific fix. The gold patch implements a different fix that was decided during code review. The tests enforce the code-review fix. An agent would need to "know" the maintainer discussion to produce a passing solution.

3. **Background knowledge substitutes for the problem statement.** In Cases B and D, the tests require domain knowledge (ERFA refraction API, FITS Q-format VLA columns in diff scenarios) that is not mentioned in the problem description. While a skilled agent might infer these, they are not derivable from the problem text alone.

### Scoring Formula Validation

All four cases were verified against the formula:

$$\text{combined} = 1 - (1 - \text{EP}) \times (1 - \text{ET}) \times (1 - \text{VS})$$

| Case | EP | ET | VS | Manual Calc | Report | Match |
|---|---|---|---|---|---|---|
| A | 1.000 | 0.000 | 0.300 | 1.000 | 1.000 | ✓ |
| B | 0.5625 | 0.7661 | 0.550 | 0.954 | 0.954 | ✓ |
| C | 0.333 | 0.833 | 0.400 | 0.933 | 0.933 | ✓ |
| D | 0.000 | 0.818 | 0.300 | 0.873 | 0.873 | ✓ |

### Confidence Summary

| Case | Instance | Combined | Primary Signal | Confidence |
|---|---|---|---|---|
| A | `django__django-10999` | 1.000 | Patch approach mismatch | **HIGH** |
| B | `astropy__astropy-13398` | 0.954 | Refraction tests beyond spec | **HIGH** |
| C | `astropy__astropy-14182` | 0.933 | Reader tests for writer request | **HIGH** |
| D | `astropy__astropy-14539` | 0.873 | Regression tests beyond bug | **MEDIUM-HIGH** |
