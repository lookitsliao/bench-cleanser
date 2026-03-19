# Case Study: `django__django-11964` — Two Agents, Two Approaches, One Trap

> **Purpose:** A comprehensive single-case forensic study of the most contaminated task in SWE-bench Verified (combined score: 1.0000). We examine the problem, the gold patch, why they diverge, and then trace two real agent trajectories — one that passes and one that fails — to understand what separates success from failure when the benchmark itself is misleading.

---

## Table of Contents

1. [The Bug Report: What Was Actually Reported](#1-the-bug-report)
2. [The Gold Patch: What Django Maintainers Actually Did](#2-the-gold-patch)
3. [The Gap: Why Problem and Patch Don't Align](#3-the-gap)
4. [The Tests: How the F2P Gate Locks In One Approach](#4-the-tests)
5. [Python's Enum MRO: The Technical Pivot Point](#5-python-enum-mro)
6. [Agent A — The `__str__` Override (PASS)](#6-agent-a)
7. [Agent B — The Field-Level Coercion (FAIL)](#7-agent-b)
8. [Comparative Analysis: What Separated Success from Failure](#8-comparative-analysis)
9. [What Incentivizes the `__str__` Override Approach?](#9-what-incentivizes-override)
10. [Contamination Verdict](#10-contamination-verdict)

---

## 1. The Bug Report: What Was Actually Reported {#1-the-bug-report}

### Problem Statement (verbatim, abridged)

> The value of a TextChoices/IntegerChoices field has a **differing type**.
>
> If we create an instance of a model having a CharField with choices pointing to TextChoices, the value returned by the getter of the field will be of the same type as the Enum member.

The reporter provides a model:

```python
class MyChoice(models.TextChoices):
    FIRST_CHOICE = "first", _("The first choice, it is")
    SECOND_CHOICE = "second", _("The second choice, it is")

class MyObject(models.Model):
    my_str_value = models.CharField(max_length=10, choices=MyChoice.choices)
```

And a test that fails:

```python
def test_created_object_is_str(self):
    my_object = self.my_object
    self.assertIsInstance(my_object.my_str_value, str)
    self.assertEqual(str(my_object.my_str_value), "first")
    #               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #  AssertionError: 'MyChoice.FIRST_CHOICE' != 'first'
```

The second test (`test_retrieved_object_is_str`) — fetching from DB — passes fine. The asymmetry is the core complaint.

### The Django Maintainer's Response (hints)

> "Clearly the expected behaviour is that `test_created_object_is_str` should pass. It's interesting that the **underlying `__dict__` values differ**, which explains all I guess:
>
> Created: `{'my_str_value': <MyChoice.FIRST_CHOICE: 'first'>}`
> Retrieved: `{'my_str_value': 'first'}`"

### What a Reader Takes Away

Both the reporter and the maintainer frame this as a **type/storage inconsistency**:

| Scenario | `instance.__dict__['my_str_value']` | `str(instance.my_str_value)` |
|---|---|---|
| **Freshly created** | `<MyChoice.FIRST_CHOICE: 'first'>` (Enum member) | `'MyChoice.FIRST_CHOICE'` |
| **Retrieved from DB** | `'first'` (plain `str`) | `'first'` |

The natural reading is: *Django should store the primitive value, not the Enum member, when the field is assigned.* This points toward fixing the model field machinery — `Model.__init__`, `DeferredAttribute.__set__`, `Field.get_prep_value`, etc.

---

## 2. The Gold Patch: What Django Maintainers Actually Did {#2-the-gold-patch}

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

**6 lines.** One method added to the `Choices` base class. No changes to any model field, descriptor, or `__init__` code.

The patch doesn't fix the type inconsistency at all. After this patch:
- `instance.__dict__['my_str_value']` still stores `<MyChoice.FIRST_CHOICE: 'first'>` (the Enum member)
- But `str(instance.my_str_value)` now returns `'first'` instead of `'MyChoice.FIRST_CHOICE'`

It's a **symptom fix**, not a root cause fix. It papers over the `__dict__` mismatch by changing what `str()` returns globally for all `Choices` enum members everywhere in the codebase.

---

## 3. The Gap: Why Problem and Patch Don't Align {#3-the-gap}

This is the contamination signal. The v3 pipeline classified this task with four labels:

| Label | Confidence | What's wrong |
|---|---|---|
| **`mispatch_approach_mismatch`** | 0.90 | Problem implies field-level coercion; gold patch uses global `__str__` override |
| **`mispatch_overpatch`** | 0.75 | `__str__` change affects all Choices members everywhere, not just model field values |
| **`mistest_overtest`** | 0.60 | `test_str` tests raw enum behavior with no model involvement |
| **`desc_misleading`** | 0.50 | Problem mixes type-storage issue with `str()` output issue |

### The Two Conceptual Fix Strategies

**Strategy 1: Field-Level Coercion (what the problem implies)**

Modify Django's model initialization to detect when an assigned value is a `Choices` enum member and coerce it to the primitive value. After this fix:
- `instance.__dict__['my_str_value']` stores `'first'` (plain str)
- `str(instance.my_str_value)` returns `'first'` naturally
- `isinstance(instance.my_str_value, str)` returns `True` (it's a real str)
- The created vs. retrieved asymmetry is **eliminated at the root**

This is where most of the code exploration leads: `DeferredAttribute`, `Model.__init__`, `Field.get_prep_value`.

**Strategy 2: Enum `__str__` Override (what the gold patch does)**

Override `Choices.__str__()` to return `str(self.value)`. After this fix:
- `instance.__dict__['my_str_value']` STILL stores `<MyChoice.FIRST_CHOICE: 'first'>`
- `str(instance.my_str_value)` returns `'first'` (because `__str__` was overridden)
- `isinstance(instance.my_str_value, str)` returns `True` (because `TextChoices` inherits from `str`)
- The `__dict__` asymmetry **persists** but the `str()` symptom is masked

### The Pipeline's Intent Extraction

The pipeline extracted this as the core requirement:

> *"Ensure that model fields using TextChoices/IntegerChoices return the underlying primitive value type (str/int) rather than the Enum member object when an instance is freshly created/assigned."*

And explicitly marked as **out of scope**:

> *"Changing Python Enum/TextChoices/IntegerChoices `__str__` behavior globally."*

The gold patch does exactly what was flagged as out of scope. This is the approach mismatch.

---

## 4. The Tests: How the F2P Gate Locks In One Approach {#4-the-tests}

Two tests must go from FAIL to PASS:

### Test 1: `test_str` (newly added)

```python
def test_str(self):
    for test in [Gender, Suit, YearInSchool, Vehicle]:
        for member in test:
            with self.subTest(member=member):
                self.assertEqual(str(test[member.name]), str(member.value))
```

This tests **raw enum `__str__` behavior** with no model instance involved. It asserts:
- `str(Gender.MALE)` equals `str(Gender.MALE.value)` — i.e., `'M'` not `'Gender.MALE'`

An agent who implemented field-level coercion (Strategy 1) would **fail this test**. The field-level fix doesn't touch `Enum.__str__`, so `str(Gender.MALE)` would still return `'Gender.MALE'`.

### Test 2: `test_textchoices` (pre-existing, unmodified)

This existing test becomes FAIL_TO_PASS as a **side effect** of the global `__str__` change. Before the patch, it expected `str(YearInSchool.FRESHMAN)` to return `'YearInSchool.FRESHMAN'`. After the patch, it expects `'FR'`. A field-level fix would not change this test's behavior at all — so the F2P harness would mark it as **FAIL**.

### The Lock-In Effect

Both F2P tests specifically require the `__str__` override approach. Any alternative fix strategy — no matter how correct, no matter how much more thorough — is **guaranteed to fail the benchmark**.

This is the strongest contamination signal: the tests don't validate the reported behavior (model field type consistency), they validate a specific implementation choice (`Choices.__str__` override).

---

## 5. Python's Enum MRO: The Technical Pivot Point {#5-python-enum-mro}

Understanding *why* `str()` returns the wrong thing requires understanding Python's Method Resolution Order for `TextChoices`:

```
TextChoices(str, Choices)
    └── Choices(enum.Enum)
```

MRO: `TextChoices → str → Choices → Enum → object`

You might expect that since `str` appears before `Enum` in the MRO, `str.__str__` would be used. But Python's `Enum.__str__` **explicitly overrides** `str.__str__`:

```python
# In Python's enum.py (simplified):
class Enum:
    def __str__(self):
        return '%s.%s' % (self.__class__.__name__, self._name_)
```

Even though `TextChoices` inherits from `str`, `Enum.__str__` wins because `Enum` sets `__str__` explicitly in its class body, overriding the inherited `str.__str__`. This is the key insight that separates the two agent trajectories.

When an agent discovers this, the fix becomes obvious: add `__str__` to `Choices` (or its subclasses) to return `str(self.value)` instead of `'ClassName.MEMBER_NAME'`.

---

## 6. Agent A — The `__str__` Override (PASS) {#6-agent-a}

### Trajectory Summary

Agent A is a top-performing SWE-bench agent that successfully produces a patch matching the gold patch.

### Step-by-Step Exploration

1. **Read the problem statement.** Identifies the `str()` inconsistency between created and retrieved instances.

2. **Explore `django/db/models/enums.py`.** Reads the `Choices`, `IntegerChoices`, and `TextChoices` class definitions. Notes the inheritance hierarchy: `TextChoices(str, Choices)`, `Choices(enum.Enum)`.

3. **Explore model field machinery.** Reads `django/db/models/query_utils.py` to understand `DeferredAttribute` (the descriptor). Notes it has `__get__` but no `__set__` — so values pass through to `instance.__dict__` unmodified.

4. **Explore `Model.__init__`.** Reads `django/db/models/base.py` lines 405-520. Sees that `_setattr(self, field.attname, val)` stores values as-is. No coercion happens here.

5. **Discovers the MRO insight.** While examining the inheritance chain, the agent realizes that `Enum.__str__` overrides `str.__str__`. This is the pivotal discovery — the agent doesn't just see the symptom (`str()` returns wrong thing), it understands *why*: Python's `Enum` explicitly installs its own `__str__` that returns `'ClassName.MEMBER_NAME'`.

6. **Implements the fix.** Adds `__str__` methods to both `IntegerChoices` and `TextChoices`:
   ```python
   def __str__(self):
       return str(self.value)
   ```

7. **Runs existing tests.** 14 of 16 pass. The 2 failures (`test_integerchoices_functional_api`, `test_textchoices_functional_api`) are pre-existing Python 3.11 compatibility issues (`boundary` parameter), unrelated to the fix.

8. **Creates and submits the patch.**

### Why Agent A Succeeded

Agent A followed the problem description honestly — it explored the full stack from enums to fields to model init. But at step 5, it made a critical pivot: instead of trying to fix *where* the value is stored (field-level coercion), it asked *why does `str()` return the wrong thing?* This question led to the MRO insight, which led directly to the gold patch.

The agent's reasoning chain:
```
Problem: str(instance.field) returns wrong value
  → Why? Because Enum.__str__ returns 'ClassName.MEMBER_NAME'
    → Why does Enum.__str__ win? Because it overrides str.__str__ in the MRO
      → Fix: Override __str__ in Choices to return self.value
```

### Contamination Assessment

**Verdict: `agent_passed_genuine` (integrity: 1.0)**

The trajectory shows progressive exploration with no shortcuts:
- No evidence of gold patch leakage or test awareness
- Solution derived from first-principles MRO analysis
- The pivot from "storage inconsistency" to "str override" shows genuine problem-solving

However, there is a question of **luck**: the agent happened to investigate the `__str__` mechanism, which happened to lead to the gold patch. A different agent asking "where should I coerce the value?" instead of "why does str() return this?" would arrive at a completely different fix — and fail.

---

## 7. Agent B — The Field-Level Coercion (FAIL) {#7-agent-b}

### Trajectory Summary

Agent B is also a capable SWE-bench agent. It implements a thorough, arguably more correct fix — but one that fails the F2P tests.

### Step-by-Step Exploration

1. **Read the problem statement.** Same starting point. Identifies the type inconsistency.

2. **Explore `django/db/models/enums.py`.** Reads the class hierarchy, same as Agent A.

3. **Explore model fields.** Reads `django/db/models/fields/__init__.py`. Examines `CharField.to_python()`, `Field.get_prep_value()`, `IntegerField.get_prep_value()`. Notes that none of these handle Enum members.

4. **Deep investigation into storage mechanism.** Traces the full insertion path:
   - `Model.__init__` → `_setattr(self, field.attname, val)` — stores as-is
   - `DeferredAttribute.__get__` — returns `instance.__dict__[field_name]` as-is
   - `DeferredAttribute` has no `__set__` — so the descriptor doesn't intercept assignment at all
   - `Field.get_prep_value` — doesn't coerce Enum members, passes them through

5. **Traces the database path.** Verifies that SQLite receives the Enum member but adapts it correctly (because `TextChoices` inherits from `str`, the DB adapter uses its string value). Confirms the DB stores `'first'` correctly.

6. **Identifies the root cause — correctly.** The agent determines that the inconsistency happens because:
   - On creation: `Model.__init__` stores the raw Enum member in `__dict__`
   - On retrieval: the DB returns a plain string, which gets stored in `__dict__`
   - No coercion happens at assignment time

7. **Implements a comprehensive fix** in two locations:

   **Fix 1: `DeferredAttribute.__set__`** (new method in `query_utils.py`):
   ```python
   def __set__(self, instance, value):
       if isinstance(value, enum.Enum):
           value = value.value
       instance.__dict__[self.field.attname] = value
   ```

   **Fix 2: `Field.get_prep_value`** (in `fields/__init__.py`):
   ```python
   def get_prep_value(self, value):
       if isinstance(value, Promise):
           value = value._proxy____cast()
       if isinstance(value, enum.Enum):
           value = value.value
       return value
   ```

   **Fix 3: `DeferredAttribute.__delete__`** (to preserve existing delete behavior):
   ```python
   def __delete__(self, instance):
       instance.__dict__.pop(self.field.attname, self)
   ```

8. **Extensive testing.** Runs the exact test case from the PR description — both `test_created_object_is_str` and `test_retrieved_object_is_str` pass. Runs `model_fields.test_charfield` (11 tests OK), `model_fields.test_integerfield` (45 tests OK), `get_or_create` (45 tests OK), `queries` (376 tests OK), `update` (16 tests OK), `basic` (57 tests OK including the `test_delete_and_access_field` that originally broke).

9. **Generates and submits the patch.**

### Where Agent B's Fix Is Arguably Superior

| Property | Agent A's Fix (`__str__`) | Agent B's Fix (field coercion) |
|---|---|---|
| Stored value in `__dict__` | Still an Enum member | Primitive (`str`/`int`) |
| `str(instance.field)` | Returns value via `__str__` | Returns value naturally |
| `isinstance(instance.field, str)` | `True` (via MRO inheritance) | `True` (it's actually a `str`) |
| Created vs. retrieved `__dict__` | **Still different** | **Made consistent** |
| Scope of change | Global — all Choices everywhere | Targeted — only model fields |
| `repr(instance.field)` | Still shows Enum repr | Shows plain str/int repr |
| Serialization (JSON, etc.) | Enum member may cause issues | Plain primitive serializes cleanly |

Agent B's fix actually resolves the root cause described in the problem statement and the maintainer's hints. The `__dict__` mismatch — the very thing the maintainer called out — is eliminated.

### Why Agent B Failed the Benchmark

Despite being arguably more correct, Agent B's patch **fails both F2P tests**:

1. **`test_str`** asserts `str(Gender.MALE) == str(Gender.MALE.value)`. Agent B's fix doesn't touch `Enum.__str__`, so `str(Gender.MALE)` still returns `'Gender.MALE'`. **FAIL.**

2. **`test_textchoices`** expects the new `__str__` behavior. Agent B's fix doesn't change `__str__`, so the pre-existing assertions about `str()` output on raw enum members don't match. **FAIL.**

The irony is stark: Agent B's fix passes all the tests from the actual bug report (the reporter's `test_created_object_is_str` and `test_retrieved_object_is_str`), but fails the benchmark's synthetic F2P tests that validate a different fix approach.

---

## 8. Comparative Analysis: What Separated Success from Failure {#8-comparative-analysis}

### The Decision Fork

Both agents followed the problem description faithfully down the same investigative path. They diverged at a single decision point:

```
Both agents: "str(instance.field) returns 'MyChoice.FIRST_CHOICE' instead of 'first'"
                                    |
                   +----------------+-----------------+
                   |                                  |
              Agent A asks:                      Agent B asks:
    "WHY does str() return               "WHERE is the value stored
     the wrong thing?"                    incorrectly?"
              |                                  |
    Discovers Enum.__str__               Discovers __dict__ stores
    overrides str.__str__                Enum member, not primitive
              |                                  |
    Fix: Override __str__                Fix: Coerce at assignment
    to return self.value                 to store primitive value
              |                                  |
          PASS (matches                      FAIL (doesn't match
          gold patch)                        F2P tests)
```

### The Paradox

| | Agent A | Agent B |
|---|---|---|
| **Fixes the described symptom** (`str()` returns wrong value) | Yes | Yes |
| **Fixes the described root cause** (`__dict__` type mismatch) | No | Yes |
| **Fixes all tests in the bug report** | Yes | Yes |
| **Passes F2P tests** | Yes | **No** |
| **Benchmark result** | PASS | **FAIL** |

Agent B implemented a more thorough fix that addresses the actual root cause described by both the reporter and the maintainer — yet it fails the benchmark. Agent A implemented a narrower fix that addresses only the symptom — and passes.

### Trajectory Characteristics

| Characteristic | Agent A | Agent B |
|---|---|---|
| **Total bash commands** | ~15 | ~55+ |
| **Files explored** | 4-5 | 8+ |
| **Reproduction scripts** | 1 | 6+ |
| **Test suites validated** | 1 (model_enums) | 7 (model_enums, model_fields, basic, queries, update, get_or_create) |
| **Lines of fix code** | 3 (one `__str__` method) | 12 (two new methods + import) |
| **Fix correctness** | Symptom fix | Root cause fix |
| **Benchmark result** | PASS | FAIL |

Agent B was more thorough in every measurable way — more exploration, more validation, more comprehensive fix. It was punished for doing more work, more correctly.

---

## 9. What Incentivizes the `__str__` Override Approach? {#9-what-incentivizes-override}

This is the key question: *What would lead an agent toward overriding `__str__` instead of fixing the field machinery?*

### 9.1 The `str()` Framing in the Problem Statement

The failing assertion in the bug report is:
```python
self.assertEqual(str(my_object.my_str_value), "first")
#                ^^^^                          ^^^^^^^
#                str() is the operation        "first" is the expected value
```

An agent that focuses tightly on `str()` as the operation in question — rather than on the type of the stored value — might ask: "What controls what `str()` returns for this object?" That question leads directly to `__str__`.

Agent A made this framing choice. Agent B instead focused on the underlying type: "Why is an Enum member stored where a string should be?"

### 9.2 Simplicity Bias

The `__str__` fix is 3 lines in 1 file. The field-coercion fix is 12+ lines across 2 files, requires adding a `__delete__` method to avoid breaking existing behavior, and touches the descriptor protocol. An agent with a simplicity heuristic ("prefer the smallest change that fixes the symptom") would gravitate toward `__str__`.

### 9.3 The MRO Discovery as a Natural Rabbit Hole

When an agent explores `TextChoices(str, Choices)` and sees that `str` is in the MRO, a natural question arises: *"If this is a `str` subclass, why does `str()` not return the string value?"* This is a genuinely interesting Python question, and investigating it leads to the `Enum.__str__` override discovery. Once you see that `Enum.__str__` explicitly returns `'ClassName.MEMBER_NAME'`, the fix is obvious and elegant.

This is why Agent A's trajectory looks like genuine problem-solving rather than memorization — the MRO investigation is a natural curiosity-driven exploration.

### 9.4 Template Rendering Context

The gold patch's docstring hints at a real-world motivation:

> "Use value when cast to str, so that Choices set as model instance attributes are rendered as expected in **templates** and similar contexts."

Django templates heavily use `str()` for rendering. A developer thinking about template rendering would naturally gravitate toward `__str__` customization — it's the Django-idiomatic way to control how objects display in templates.

An agent wouldn't have this template-rendering intuition unless it has deep Django domain knowledge or has seen this pattern before.

### 9.5 The `__str__` Override Pattern in Django Culture

Django has a strong cultural convention of overriding `__str__` on model classes to control display behavior. Every Django tutorial teaches `def __str__(self): return self.name`. An agent steeped in Django conventions might naturally think: "The display is wrong, so override `__str__`."

This is a **domain-specific heuristic** that wouldn't be available to a general-purpose coding agent. It's one reason why Django-specialized agents might outperform on this task.

### 9.6 What Does NOT Incentivize It

- **The problem statement itself.** It describes a type mismatch, not a display issue.
- **The maintainer's hints.** The hints explicitly highlight the `__dict__` value difference, pointing toward storage-level fixes.
- **The acceptance criteria** (as extracted by the pipeline). They focus on `instance.field` being a primitive type.
- **General software engineering principles.** "Fix the root cause, not the symptom" would lead to field coercion.

The `__str__` override is incentivized by:
1. Tight focus on the `str()` operation in the failing assertion
2. Simplicity/minimality bias
3. MRO curiosity during exploration
4. Django-specific cultural knowledge about `__str__` overrides

None of these are illegitimate — but none are what the problem statement asks for either.

---

## 10. Contamination Verdict {#10-contamination-verdict}

### Scoring

| Component | Score | Derivation |
|---|---|---|
| EXCESS_PATCH (EP) | 1.0000 | 0 REQUIRED + 0 ANCILLARY + 1 UNRELATED of 1 total hunk |
| EXCESS_TEST (ET) | 0.0000 | Pipeline failed to decompose loop assertions |
| VAGUE_SPEC (VS) | 0.3000 | LLM ambiguity assessment |

$$\text{combined} = 1 - (1 - 1.0)(1 - 0.0)(1 - 0.3) = 1 - (0)(1)(0.7) = 1.0000$$

**Severity: SEVERE** (combined >= 0.8)

### The Contamination Signal

The contamination is **real but nuanced**:

**FOR contamination:**
- The F2P tests enforce the specific `__str__` override approach. Any alternative — no matter how correct — fails.
- `test_str` tests raw enum `__str__` behavior with no model involvement. An agent solving the model-field problem would not write this test and would not produce a fix that passes it.
- `test_textchoices` is a pre-existing test that only enters FAIL_TO_PASS because of the global `__str__` change. A field-level fix would leave it unaffected.
- The problem statement, the hints, and the acceptance criteria all point toward field-level coercion, not `__str__` override.

**AGAINST contamination:**
- A skilled agent CAN arrive at the `__str__` fix through legitimate reasoning (MRO investigation).
- The `__str__` fix is a valid, simpler solution to the described symptom.
- `TextChoices` inherits from `str`, so `isinstance()` checks pass regardless of approach.

### Net Assessment

**CONFIRMED — Medium-High Confidence**

The benchmark disadvantages agents that follow the problem description faithfully and implement the root-cause fix. It rewards agents that — through luck, MRO curiosity, simplicity bias, or Django cultural knowledge — happen to arrive at the specific `__str__` override that the Django maintainers chose.

Agent A passed because it asked "why does str() return the wrong thing?" instead of "why is the wrong type stored?" — a framing choice that happened to align with the gold patch.

Agent B failed because it followed the problem description more literally, fixed the actual root cause, ran 7 test suites, and produced a more thorough patch — but the F2P tests don't test for the root cause fix. They test for the symptom fix.

This is a textbook case of **approach mismatch contamination**: the problem leads toward Strategy 1 (field coercion), the tests lock in Strategy 2 (`__str__` override), and the gap between them is where capable agents go to die.

---

## Appendix A: The Actual Code Under Discussion

### `django/db/models/enums.py` (before and after gold patch)

**Before:**
```python
class Choices(enum.Enum, metaclass=ChoicesMeta):
    """Class for creating enumerated choices."""
    pass


class IntegerChoices(int, Choices):
    """Class for creating enumerated integer choices."""
    pass


class TextChoices(str, Choices):
    """Class for creating enumerated string choices."""

    def _generate_next_value_(name, start, count, last_values):
        return name
```

**After (gold patch):**
```python
class Choices(enum.Enum, metaclass=ChoicesMeta):
    """Class for creating enumerated choices."""

    def __str__(self):
        """
        Use value when cast to str, so that Choices set as model instance
        attributes are rendered as expected in templates and similar contexts.
        """
        return str(self.value)
```

### `DeferredAttribute` (the descriptor, unchanged by gold patch)

```python
class DeferredAttribute:
    def __init__(self, field):
        self.field = field

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        data = instance.__dict__
        field_name = self.field.attname
        if data.get(field_name, self) is self:
            val = self._check_parent_chain(instance)
            if val is None:
                instance.refresh_from_db(fields=[field_name])
                val = getattr(instance, field_name)
            data[field_name] = val
        return data[field_name]

    # Note: no __set__ method — assignments go directly to __dict__
```

### Agent B's Fix (field-level coercion, not the gold patch)

**`django/db/models/query_utils.py`** — Added to `DeferredAttribute`:
```python
import enum

class DeferredAttribute:
    # ... existing __get__ ...

    def __set__(self, instance, value):
        if isinstance(value, enum.Enum):
            value = value.value
        instance.__dict__[self.field.attname] = value

    def __delete__(self, instance):
        instance.__dict__.pop(self.field.attname, self)
```

**`django/db/models/fields/__init__.py`** — Modified `Field.get_prep_value`:
```python
import enum

class Field:
    def get_prep_value(self, value):
        if isinstance(value, Promise):
            value = value._proxy____cast()
        if isinstance(value, enum.Enum):
            value = value.value
        return value
```

---

## Appendix B: F2P Test Details

### `test_str` (newly added by test patch)

```python
def test_str(self):
    for test in [Gender, Suit, YearInSchool, Vehicle]:
        for member in test:
            with self.subTest(member=member):
                self.assertEqual(str(test[member.name]), str(member.value))
```

- Tests raw enum `__str__` — no model, no field, no instance
- Only passes if `Choices.__str__` returns the value
- Agent B's fix: **FAIL** (str(Gender.MALE) still returns 'Gender.MALE')
- Agent A's fix: **PASS** (str(Gender.MALE) now returns 'M')

### `test_textchoices` (pre-existing, not modified)

- Contains assertions about `str()` output on `TextChoices` members
- Before gold patch: expected `'YearInSchool.FRESHMAN'`
- After gold patch: expects `'FR'`
- Becomes FAIL_TO_PASS purely as a side effect of the `__str__` change
- Agent B's fix: **FAIL** (doesn't change str() on raw enums)
- Agent A's fix: **PASS** (str() now returns value)
