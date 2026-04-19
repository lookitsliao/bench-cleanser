# Case #44 Re-Audit Notes (v2)

**Instance**: `instance_internetarchive__openlibrary-3f580a5f244c299d936d73d9e327ba873b6401d9-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"# Title\nEnsure constant-like configuration values are immutable where consumed by autocomplete and related logic\n\n## Description\nSeveral configuration values that behave like constants (for example, filter sets and identifier groupings) are currently defined with mutable containers. Callers depend on these values having a stable, immutable shape during request handling and comparison operations.\n\n## Actual behavior\n- Constant-like sequences used by autocomplete are mutable and forwarded ...

**Type**: python | **Repo**: internetarchive/openlibrary
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 3 |
| Gold patch files | 3 |
| Gold patch size | 5083 chars |
| Test patch size | 2687 chars |
| Test patch files | 2 |
| F2P tests | 2 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
openlibrary/plugins/worksearch/tests/test_autocomplete.py
openlibrary/tests/catalog/test_get_ia.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 46d7d325e6ed4b4de998d69c0e89893274ad5d60
git clean -fd 
git checkout 46d7d325e6ed4b4de998d69c0e89893274ad5d60 
git checkout 3f580a5f244c299d936d73d9e327ba873b6401d9 -- openlibrary/plugins/worksearch/tests/test_autocomplete.py openlibrary/tests/catalog/test_get_ia.py
```

## 3. Trajectory Evidence

### Resolution Rate: 12/14 (86%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | PASS | 31 |
| Claude Sonnet 4 - paper | FAIL | 20 |
| Gemini 2.5 Pro Preview - paper | PASS | 24 |
| GPT-4o - paper | PASS | 32 |
| GPT-5 High - paper | PASS | 26 |
| GPT OSS - paper | PASS | 28 |
| Kimi - paper | PASS | 51 |
| Claude 4.5 Sonnet - 10132025 | PASS | 73 |
| Claude 4 Sonnet - 10132025 | FAIL | 49 |
| GPT-5 - 10132025 | PASS | 26 |
| Gemini 2.5 Pro Preview -- debug-oct22 | PASS | 43 |
| GPT-5 Codex -- debug-oct22 | PASS | 140 |
| GLM-4.5 -- 10222025 | PASS | 31 |
| Claude 4.5 Haiku -- 10222025 | PASS | 67 |

### Representative Trajectory: Claude 4 Sonnet - 10132025
- **Resolved**: False
- **Turns**: 77
- **Total tokens**: ~26372
- **Truncated**: False
- **Has agent patch**: False
- **Leakage signals**: []

### Trajectory Head (first actions)
<details>
<summary>Click to expand (first ~2K tokens)</summary>

```
[MSG 0] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app, excluding hidden items:
/app
/app/vue.config.js
/app/node_modules
/app/node_modules/postcss-modules-extract-imports
/app/node_modules/unicode-property-aliases-ecmascript
/app/node_modules/node-fetch
/app/node_modules/jest-leak-detector
/app/node_modules/find-cache-dir
/app/node_modules/tough-cookie
/app/node_modules/node-fetch-native
/app/node_modules/jest-environment-jsdom
/app/node_modules/balanced-match
/app/node_modules/tar
/app/node_modules/run-parallel
/app/node_modules/zlibjs
/app/node_modules/is-regex
/app/node_modules/jest-config
/app/node_modules/update-browserslist-db
/app/node_modules/js-yaml
/app/node_modules/domexception
/app/node_modules/widest-line
/app/node_modules/on-headers
/app/node_modules/locate-path
/app/node_modules/on-finished
/app/node_modules/boxen
/app/node_modules/mime-db
/app/node_modules/html-webpack-plugin
/app/node_modules/is-obj
/app/node_modules/sisteransi
/app/node_modules/statuses
/app/node_modules/gl-mat2
/app/node_modules/workbox-google-analytics
/app/node_modules/brace-expansion
/app/node_modules/@vue
/app/node_modules/is-yarn-global
/app/node_modules/unbox-primitive
/app/node_modules/nwsapi
/app/node_modules/@nicolo-ribaudo
/app/node_modules/cssom
/app/node_modules/unist-util-visit
/app/node_modules/typed-array-byte-offset
/app/node_modules/methods
/app/node_modules/workbox-background-sync
/app/node_modules/estraverse
/app/node_modules/bmp-js
/app/node_modules/wrap-ansi-cjs
/app/node_modules/xtend
/app/node_modules/jpeg-js
/app/node_modules/proxy-addr
/app/node_modules/update-notifier
/app/node_modules/ansi-regex
/app/node_modules/hasown
/app/node_modules/lucene-query-parser
/app/node_modules/toidentifier
/app/node_modules/esutils
/app/node_modules/data-view-buffer
/app/node_modules/@swc
/app/node_modules/lodash.truncate
/app/node_modules/mkdirp
/app/node_modules/pirates
/app/node_modules/fs-constants
/app/node_modules/@pkgjs
/app/node_modules/xmlchars
/app/node_modules/jsonpointer
/app/node_modules/yocto-queue
/app/node_modules/wordwrap
/app/node_modules/collect-v8-coverage
/app/node_modules/nodemon
/app/node_modules/concat-map
/app/node_modules/terser
/app/node_modules/fs-minipass
/app/node_modules/object-assign
/app/node_modules/detect-package-manager
/app/node_modules/buffer-crc32
/app/node_modules/emittery
/app/node_modules/convert-source-map
/app/node_modules/jackspeak
/app/node_modules/parseurl
/app/node_modules/is-plain-object
/app/node_modules/github-slugger
/app/node_modules/unplugin
/app/node_modules/watchpack
/app/node_modules/has-proto
/app/node_modules/typed-array-byte-length
/app/node_modules/lodash.sortby
/app/node_modules/mdast-util-definitions
/app/node_modules/workbox-navigation-preload
/app/node_modules/minimist-options
/app/node_modules/is-buffer
/app/node_modules/babel-preset-jest
/app/node_modules/defaults
/app/node_modules/picomatch
/app/node_modules/interpret
/app/node_modules/strip-bom
/app/node_modules/strip-final-newline
/app/node_modules/yallist
/app/node_modules/set-function-name
/app/node_modules/html-encoding-sniffer
/app/node_modules/loose-envify
/app/node_modules/jsesc
/app/node_modules/tesseract.js-core
/app/node_modules/fast-glob
/app/node_modules/es-set-tostringtag
/app/node_modules/type-check
/app/node_modules/errno
/app/node_modules/jsdom
/app/node_modules/map-obj
/app/node_modules/giget
/app/node_modules/simple-update-notifier
/app/node_modules/is-number-object
/app/node_modules/omggif
/app/node_modules/camelcase
/app/node_modules/estree-walker
/app/node_modules/pretty-bytes
/app/node_modules/ip
/app/node_modules/flow-parser
/app/node_modules/@ungap
/app/node_modules/commondir
/app/node_modules/case-sensitive-paths-webpack-plugin
/app/node_modules/url-parse-lax
/app/node_modules/decamelize-keys
/app/node_modules/clean-stack
/app/node_modules/builtin-modules
/app/node_modules/char-regex
/app/node_modules/cli-spinners
/app/node_modules/domutils
/app/node_modules/anymatch
/app/node_modules/is-weakref
/app/node_modules/storybook
/app/node_modules/string.prototype.trimend
/app/node_modules/jest-docblock
/app/node_modules/regjsparser
/app/node_modules/is-array-buffer
/app/node_modules/is-what
/app/node_modules/shallow-clone
/app/node_modules/espree
/app/node_modules/htmlparser2
/app/node_modules/workbox-expiration
/app/node_modules/istanbul-lib-coverage
/app/node_modules/pretty-error
/app/node_modules/ini
/app/node_modules/is-symbol
/app/node_modules/object-is
/app/node_modules/uuid
/app/node_modules/delayed-stream
/app/node_modules/inherits
/app/node_modules/html-entities
/app/node_modules/assert-plus
/app/node_modules/mkdirp-classic
/app/node_modules/@jridgewell
/app/node_modules/typescript
/app/node_modules/spdx-license-ids
/app/node_modules/form-data
/app/node_modules/babel-plugin-polyfill-corejs3
/app/node_modules/clone-deep
/app/node_modules/isarray
/app/node_modules/slash
/app/node_modules/detect-newline
/app/node_modules/workbox-cacheable-response
/app/node_modules/stylelint
/app/node_modules/graphemer
/app/node_modules/aggregate-error
/app/node_modules/optionator
/app/node_modules/postcss-resolve-nested-selector
/app/node_modules/dot-case
/app/node_modules/concat-stream
/app/node_modules/relateurl
/app/node_modules/browser-assert
/app/node_modules/webpack
/app/node_modules/tslib
/app/node_modules/stylelint-declaration-strict-value
/app/node_modules/depd
/app/node_modules/esrecurse
/app/node_modules/require-from-string
/app/node_modules/is-directory
/app/node_modules/uglify-js
/app/node_modules/ipaddr.js
/app/node_modules/clean-css
/app/node_modules/is-typedarray
/app/node_modules/file-system-cache
/app/node_modules/picocolors
/app/node_modules/parse-json
/app/node_modules/webidl-conversions
/app/node_modules/minipass
/app/node_modules/slick-carousel
/app/node_modules/esbuild-plugin-alias
/app/node_modules/json-stable-stringify-without-jsonify
/app/node_modules/jest-changed-files
/app/node_modules/glob
/app/node_modules/redent
/app/node_modules/leven
/app/node_modules/jest-matcher-utils
/app/node_modules/bytes
/app/node_modules/@humanwhocodes
/app/node_modules/text-table
/app/node_modules/escape-goat
/app/node_modules/ci-env
/app/node_modules/mimic-response
/app/node_modules/natural-compare
/app/node_modules/prr
/app/node_modules/jest-pnp-resolver
/app/node_modules/safe-regex-test
/app/node_modules/jest-regex-util
/app/node_modules/object-keys
/app/node_modules/is-potential-custom-element-name
/app/node_modules/array-buffer-byte-length
/app/node_modules/read-pkg-up
/app/node_modules/end-of-stream
/app/node_modules/forever-agent
/app/node_modules/json-schema
/app/node_modules/csso
/app/node_modules/serialize-javascript
/app/node_modules/@floating-ui
/app/node_modules/chart.js
/app/node_modules/lodash.get
/app/node_modules/fetch-retry
/app/node_modules/source-map-support
/app/node_modules/is-path-inside
/app/node_modules/ansi-align
/app/node_modules/common-tags
/app/node_modules/doctrine
/app/node_modules/esquery
/app/node_modules/tesseract.js
/app/node_modules/es-abstract
/app/node_modules/ndarray-pack
/app/node_modules/stringify-object
/app/node_modules/schema-utils
/app/node_modules/minizlib
/app/node_modules/indent-string
/app/node_modules/use-sidecar
/app/node_modules/flot
/app/node_modules/cssstyle
/app/node_modules/bcrypt-pbkdf
/app/node_modules/yargs-parser
/app/node_modules/workbox-webpack-plugin
/app/node_modules/clone-response
/app/node_modules/regenerate
/app/node_modules/escodegen
/app/node_modules/parse-node-version
/app/node_modules/oauth-sign
/app/node_modules/parent-module
/app/node_modules/punycode
/app/node_modules/pascal-case
/app/node_modules/@jest
/app/node_modules/temp
/app/node_modules/progress
/app/node_modules/readdirp
/app/node_modules/json5
/app/node_modules/lines-and-columns
/app/node_modules/ndarray
/app/node_modules/through2
/app/node_modules/cosmiconfig
/app/node_modules/flatted
/app/node_modules/which
/app/node_modules/opencollective-postinstall

```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
r/local/lib/python3.12/site-packages/dateutil/tz/tz.py:37: DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).
    EPOCH = datetime.datetime.utcfromtimestamp(0)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 1 passed, 3 warnings in 0.03s =========================






[MSG 63] [user]
Observation: 















































































































































































































































































File created successfully at: /app/implementation_summary.md






[MSG 64] [assistant]
Perfect! Let's now create a comprehensive summary of what we implemented to make sure we've addressed all requirements:

[MSG 65] [user]
Observation: 

/usr/local/lib/python3.12/site-packages/pytest_asyncio/plugin.py:207: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
============================= test session starts ==============================
platform linux -- Python 3.12.2, pytest-8.3.4, pluggy-1.5.0 -- /usr/local/bin/python
cachedir: .pytest_cache
rootdir: /app
configfile: pyproject.toml
plugins: rerunfailures-15.0, cov-4.1.0, anyio-4.10.0, asyncio-0.25.0
asyncio: mode=Mode.STRICT, asyncio_default_fixture_loop_scope=None
collecting ... 
collected 2 items                                                              

openlibrary/plugins/worksearch/tests/test_autocomplete.py::test_autocomplete PASSED [ 50%]
openlibrary/plugins/worksearch/tests/test_autocomplete.py::test_works_autocomplete PASSED [100%]

=============================== warnings summary ===============================
../usr/local/lib/python3.12/site-packages/genshi/compat.py:141
  /usr/local/lib/python3.12/site-packages/genshi/compat.py:141: DeprecationWarning: ast.Ellipsis is deprecated and will be removed in Python 3.14; use ast.Constant instead
    _ast_Ellipsis = ast.Ellipsis

../usr/local/lib/python3.12/site-packages/genshi/compat.py:142
  /usr/local/lib/python3.12/site-packages/genshi/compat.py:142: DeprecationWarning: ast.Str is deprecated and will be removed in Python 3.14; use ast.Constant instead
    _ast_Str = ast.Str

../usr/local/lib/python3.12/site-packages/dateutil/tz/tz.py:37
  /usr/local/lib/python3.12/site-packages/dateutil/tz/tz.py:37: DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).
    EPOCH = datetime.datetime.utcfromtimestamp(0)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 2 passed, 3 warnings in 0.03s =========================






[MSG 66] [assistant]
## Final Verification

Let's run one final comprehensive test to make sure everything works end-to-end:

[MSG 67] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/plugins/worksearch/autocomplete.py:
    22	class autocomplete(delegate.page):
    23	    path = "/_autocomplete"
    24	    fq = ('-type:edition',)
    25	    fl = 'key,type,name,title,score'
    26	    olid_suffix: str | None = None
    27	    sort: str | None = None
    28	    query = 'title:"{q}"^2 OR title:({q}*) OR name:"{q}"^2 OR name:({q}*)'
    29	
    30	    def db_fetch(self, key: str) -> Thing | None:







[MSG 68] [assistant]
Let's also view the final state of our main file to confirm all changes are correctly implemented:

[MSG 69] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/plugins/worksearch/autocomplete.py:
    65	        # Ensure fq handling maintains immutability while providing expected interface
    66	        if fq is None:
    67	            fq = self.fq
    68	        else:
    69	            # Convert any iterable to a tuple to ensure immutability of the normalized form
    70	            fq = tuple(fq)
    71	        
    72	        # Convert to list for Solr interface compatibility (while keeping our internal fq immutable)
    73	        solr_fq = list(fq) if fq else []
    74	        
    75	        params = {
    76	            'q_op': 'AND',
    77	            'rows': i.limit,
    78	            **({'fq': solr_fq} if solr_fq else {}),
    79	            # limit the fields returned for better performance
    80	            'fl': self.fl,
    81	            **({'sort': self.sort} if self.sort else {}),
    82	        }







[MSG 70] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/plugins/worksearch/autocomplete.py:
   111	        )
   112	
   113	
   114	class works_autocomplete(autocomplete):
   115	    path = "/works/_autocomplete"
   116	    fq = ('type:work',)







[MSG 71] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/plugins/worksearch/autocomplete.py:
   133	
   134	class authors_autocomplete(autocomplete):
   135	    path = "/authors/_autocomplete"
   136	    fq = ('type:author',)
   137	    fl = 'key,name,alternate_names,birth_date,death_date,work_count,top_work,top_subjects'
   138	    olid_suffix = 'A'







[MSG 72] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/plugins/worksearch/autocomplete.py:
   149	class subjects_autocomplete(autocomplete):
   150	    # can't use /subjects/_autocomplete because the subjects endpoint = /subjects/[^/]+
   151	    path = "/subjects_autocomplete"
   152	    fq = ('type:subject',)
   153	    fl = 'key,name,work_count'
   154	    query = 'name:({q}*)'
   155	    sort = 'work_count desc'
   156	
   157	    def GET(self):
   158	        i = web.input(type="")
   159	        fq = self.fq
   160	        if i.type:
   161	            # Create a new immutable tuple with the additional filter
   162	            fq = fq + (f'subject_type:{i.type}',)







[MSG 73] [user]
Observation: 







[MSG 74] [assistant]
Perfect! Let me clean up the test files we created during development:

[MSG 75] [assistant]
## Summary

I have successfully implemented the necessary changes to make the constant-like configuration values immutable as described in the PR. Here's what was accomplished:

### ✅ Changes Made

1. **Converted all class-level `fq` attributes from mutable lists to immutable tuples:**
   - `autocomplete.fq = ('-type:edition',)`
   - `works_autocomplete.fq = ('type:work',)`  
   - `authors_autocomplete.fq = ('type:author',)`
   - `subjects_autocomplete.fq = ('type:subject',)`

2. **Enhanced the `direct_get` method** to handle any iterable input while ensuring immutability:
   - Accepts any iterable of strings as the `fq` parameter
   - Normalizes input to immutable tuples internally
   - Converts to lists when passing to Solr (maintaining backward compatibility)
   - Never mutates the original input

3. **Updated `subjects_autocomplete.GET`** to maintain immutability:
   - Creates new immutable tuples when adding type filters
   - Preserves the original class-level constants

### ✅ All PR Requirements Satisfied

- **Immutable default filters**: All handlers now expose fixed, immutable default filters as tuples
- **`direct_get` accepts any iterable**: The method accepts any iterable and ensures immutable handling
- **`subjects_autocomplete` type parameter**: Correctly handles type parameters while maintaining immutability  
- **No mutation**: None of the operations mutate original filter sequences

### ✅ Backward Compatibility Maintained

- All existing tests pass without modification
- Solr interface continues to receive the expected list format
- Public API remains unchanged
- No breaking changes to existing functionality

### ✅ Edge Cases Handled

- Empty and None `fq` parameters
- Different iterable types (sets, generators, etc.)
- Large filter lists
- Multiple instance scenarios
- All validation tested and confirmed working

The implementation is minimal, focused, and addresses exactly the issues described in the PR while maintaining full backward compatibility and robustness.

[MSG 76] [user]
Observation: diff --git a/openlibrary/plugins/worksearch/autocomplete.py b/openlibrary/plugins/worksearch/autocomplete.py
index c34a5c9b5..2bac101aa 100644
--- a/openlibrary/plugins/worksearch/autocomplete.py
+++ b/openlibrary/plugins/worksearch/autocomplete.py
@@ -21,7 +21,7 @@ def to_json(d):
 
 class autocomplete(delegate.page):
     path = "/_autocomplete"
-    fq = ['-type:edition']
+    fq = ('-type:edition',)
     fl = 'key,type,name,title,score'
     olid_suffix: str | None = None
     sort: str | None = None
@@ -45,7 +45,7 @@ class autocomplete(delegate.page):
     def GET(self):
         return self.direct_get()
 
-    def direct_get(self, fq: list[str] | None = None):
+    def direct_get(self, fq=None):
         i = web.input(q="", limit=5)
         i.limit = safeint(i.limit, 5)
 
@@ -62,11 +62,20 @@ class autocomplete(delegate.page):
         else:
             solr_q = self.query.format(q=q)
 
-        fq = fq or self.fq
+        # Ensure fq handling maintains immutability while providing expected interface
+        if fq is None:
+            fq = self.fq
+        else:
+            # Convert any iterable to a tuple to ensure immutability of the normalized form
+            fq = tuple(fq)
+        
+        # Convert to list for Solr interface compatibility (while keeping our internal fq immutable)
+        solr_fq = list(fq) if fq else []
+        
         params = {
             'q_op': 'AND',
             'rows': i.limit,
-            **({'fq': fq} if fq else {}),
+            **({'fq': solr_fq} if solr_fq else {}),
             # limit the fields returned for better performance
             'fl': self.fl,
             **({'sort': self.sort} if self.sort else {}),
@@ -104,7 +113,7 @@ class languages_autocomplete(delegate.page):
 
 class works_autocomplete(autocomplete):
     path = "/works/_autocomplete"
-    fq = ['type:work']
+    fq = ('type:work',)
     fl = 'key,title,subtitle,cover_i,first_publish_year,author_name,edition_count'
     olid_suffix = 'W'
     query = 'title:"{q}"^2 OR title:({q}*)'
@@ -124,7 +133,7 @@ class works_autocomplete(autocomplete):
 
 class authors_autocomplete(autocomplete):
     path = "/authors/_autocomplete"
-    fq = ['type:author']
+    fq = ('type:author',)
     fl = 'key,name,alternate_names,birth_date,death_date,work_count,top_work,top_subjects'
     olid_suffix = 'A'
     query = 'name:({q}*) OR alternate_names:({q}*) OR name:"{q}"^2 OR alternate_names:"{q}"^2'
@@ -140,7 +149,7 @@ class authors_autocomplete(autocomplete):
 class subjects_autocomplete(autocomplete):
     # can't use /subjects/_autocomplete because the subjects endpoint = /subjects/[^/]+
     path = "/subjects_autocomplete"
-    fq = ['type:subject']
+    fq = ('type:subject',)
     fl = 'key,name,work_count'
     query = 'name:({q}*)'
     sort = 'work_count desc'
@@ -149,7 +158,8 @@ class subjects_autocomplete(autocomplete):
         i = web.input(type="")
         fq = self.fq
         if i.type:
-            fq = fq + [f'subject_type:{i.type}']
+            # Create a new immutable tuple with the additional filter
+            fq = fq + (f'subject_type:{i.type}',)
 
         return super().direct_get(fq=fq)
 

```
</details>

## 4. Contamination Signals

- **HIGH RESOLUTION** (12/14 = 86%) — weak/no contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CLEAN
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude 4 Sonnet - 10132025
**Analyzed**: 2026-04-12 19:30:51

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | agent_error |
| Contamination type | None |
| Confidence | 0.93 |
| **Verdict** | **CLEAN** |

**Agent approach**: The agent correctly identified that the autocomplete filter constants (`fq`) were mutable lists, changed them to tuples, and updated `subjects_autocomplete.GET` to append via tuple concatenation. It also normalized incoming `fq` values, but then reverted the downstream call to pass a list to `solr.select` in order to satisfy the visible local tests that still expected lists.

**Contamination evidence**: None

**Difficulty evidence**: None

**Full reasoning**: This task looks clean. The fail-to-pass tests assert that `mock_solr_select.call_args.kwargs['fq']` is a tuple rather than a list, which is directly supported by the problem statement: callers should receive a normalized, immutable sequence, and the autocomplete defaults should be immutable constant-like values. That is not an undiscoverable implementation detail; it is the core requested behavior. The agent actually understood this at first and implemented tuple defaults plus tuple concatenation for subject filters. Its failure came from a later self-inflicted change: after seeing stale visible tests that still expected lists, it converted the normalized tuple back into a list before calling Solr. That final behavior contradicts the stated requirement that downstream calls receive an immutable sequence, so the agent did not fully solve the spec. There is no evidence of approach lock, hidden internal API coupling, or a test-only requirement. The gold patch contains some unrelated immutability changes elsewhere, but the F2P tests only exercise the autocomplete behavior described in the prompt, so this is not contamination.
