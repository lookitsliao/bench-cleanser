# Case #26 Re-Audit Notes (v2)

**Instance**: `instance_internetarchive__openlibrary-431442c92887a3aece3f8aa771dd029738a80eb1-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

## Title: Child nodes in Luqum parse trees cannot be replaced.

### Problem:

Currently, the Luqum utilities provide functionality to traverse and remove nodes in a parse tree, but they do not offer a direct way to replace an existing child node with a new one. This limitation complicates scenarios where an expression needs to be updated in place while preserving the overall tree structure.

### Steps to Reproduce:

1. Parse a query into a luqum tree using `luqum_parser`.

2. Traverse the tree w...

**Type**: python | **Repo**: internetarchive/openlibrary
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 2 |
| Gold patch files | 2 |
| Gold patch size | 5570 chars |
| Test patch size | 1546 chars |
| Test patch files | 1 |
| F2P tests | 7 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
openlibrary/tests/solr/test_query_utils.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 188a76779dbd2368d73313ad15cae639c295eb21
git clean -fd 
git checkout 188a76779dbd2368d73313ad15cae639c295eb21 
git checkout 431442c92887a3aece3f8aa771dd029738a80eb1 -- openlibrary/tests/solr/test_query_utils.py
```

## 3. Trajectory Evidence

### Resolution Rate: 7/13 (54%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 33 |
| Claude Sonnet 4 - paper | FAIL | 12 |
| Gemini 2.5 Pro Preview - paper | FAIL | 22 |
| GPT-4o - paper | FAIL | 73 |
| GPT-5 High - paper | FAIL | 27 |
| GPT OSS - paper | PASS | 46 |
| Kimi - paper | PASS | 51 |
| Claude 4.5 Sonnet - 10132025 | PASS | 46 |
| GPT-5 - 10132025 | FAIL | 15 |
| Gemini 2.5 Pro Preview -- debug-oct22 | PASS | 16 |
| GPT-5 Codex -- debug-oct22 | PASS | 48 |
| GLM-4.5 -- 10222025 | PASS | 41 |
| Claude 4.5 Haiku -- 10222025 | PASS | 51 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 59
- **Total tokens**: ~32060
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
/app/docker-compose.infogami-local.yml
/app/setup.py
/app/Makefile
/app/docker-compose.override.yml
/app/CONTRIBUTING.md
/app/requirements.txt
/app/node_modules
/app/node_modules/create-react-context
/app/node_modules/functional-red-black-tree
/app/node_modules/es-get-iterator
/app/node_modules/pretty-error
/app/node_modules/fs-write-stream-atomic
/app/node_modules/lines-and-columns
/app/node_modules/vue-loader
/app/node_modules/object.getownpropertydescriptors
/app/node_modules/bonjour
/app/node_modules/domutils
/app/node_modules/nwsapi
/app/node_modules/dotenv-defaults
/app/node_modules/sisteransi
/app/node_modules/watchpack-chokidar2
/app/node_modules/decimal.js
/app/node_modules/regenerate
/app/node_modules/clipboard
/app/node_modules/which
/app/node_modules/es-abstract
/app/node_modules/domelementtype
/app/node_modules/spdy
/app/node_modules/stream-shift
/app/node_modules/iterate-iterator
/app/node_modules/stack-utils
/app/node_modules/is-generator-fn
/app/node_modules/browserify-des
/app/node_modules/to-fast-properties
/app/node_modules/for-in
/app/node_modules/@popperjs
/app/node_modules/unist-util-visit-parents
/app/node_modules/on-headers
/app/node_modules/hast-util-to-parse5
/app/node_modules/nise
/app/node_modules/parse-passwd
/app/node_modules/diff
/app/node_modules/html-escaper
/app/node_modules/p-limit
/app/node_modules/utils-merge
/app/node_modules/mimic-fn
/app/node_modules/walker
/app/node_modules/parse-git-config
/app/node_modules/has-symbols
/app/node_modules/minipass
/app/node_modules/is-symbol
/app/node_modules/remark-slug
/app/node_modules/babel-jest
/app/node_modules/postcss-modules-extract-imports
/app/node_modules/esquery
/app/node_modules/array-uniq
/app/node_modules/map-visit
/app/node_modules/jpeg-js
/app/node_modules/get-pixels
/app/node_modules/get-intrinsic
/app/node_modules/launch-editor-middleware
/app/node_modules/upath
/app/node_modules/caniuse-api
/app/node_modules/has-to-string-tag-x
/app/node_modules/postcss-reduce-transforms
/app/node_modules/string-length
/app/node_modules/imurmurhash
/app/node_modules/postcss-discard-empty
/app/node_modules/timed-out
/app/node_modules/object-inspect
/app/node_modules/unicode-property-aliases-ecmascript
/app/node_modules/tweetnacl
/app/node_modules/postcss-modules-scope
/app/node_modules/wide-align
/app/node_modules/htmlparser2
/app/node_modules/electron-to-chromium
/app/node_modules/ts-invariant
/app/node_modules/pug-code-gen
/app/node_modules/has-flag
/app/node_modules/symbol-tree
/app/node_modules/gud
/app/node_modules/prebuild-install
/app/node_modules/safe-buffer
/app/node_modules/flush-write-stream
/app/node_modules/workbox-recipes
/app/node_modules/ts-essentials
/app/node_modules/asn1
/app/node_modules/repeat-string
/app/node_modules/process
/app/node_modules/less-loader
/app/node_modules/is-resolvable
/app/node_modules/caniuse-lite
/app/node_modules/js-yaml
/app/node_modules/no-case
/app/node_modules/simple-swizzle
/app/node_modules/har-schema
/app/node_modules/simple-get
/app/node_modules/ansi-escapes
/app/node_modules/ajv-keywords
/app/node_modules/thenify-all
/app/node_modules/download
/app/node_modules/run-parallel
/app/node_modules/pify
/app/node_modules/node-releases
/app/node_modules/statuses
/app/node_modules/request
/app/node_modules/lower-case
/app/node_modules/hast-to-hyperscript
/app/node_modules/node-dir
/app/node_modules/buffer-indexof
/app/node_modules/co
/app/node_modules/is-path-inside
/app/node_modules/ndarray-linear-interpolate
/app/node_modules/safer-buffer
/app/node_modules/clone-response
/app/node_modules/get-symbol-description
/app/node_modules/delayed-stream
/app/node_modules/workbox-range-requests
/app/node_modules/worker-farm
/app/node_modules/yargs
/app/node_modules/webpack-filter-warnings-plugin
/app/node_modules/define-properties
/app/node_modules/setimmediate
/app/node_modules/p-all
/app/node_modules/uniq
/app/node_modules/glob-parent
/app/node_modules/react-error-overlay
/app/node_modules/is-expression
/app/node_modules/ts-map
/app/node_modules/aws-sign2
/app/node_modules/psl
/app/node_modules/to-arraybuffer
/app/node_modules/compression
/app/node_modules/iota-array
/app/node_modules/nice-try
/app/node_modules/has-tostringtag
/app/node_modules/min-indent
/app/node_modules/cookie
/app/node_modules/apollo-link
/app/node_modules/source-map-resolve
/app/node_modules/prettycli
/app/node_modules/character-entities
/app/node_modules/decamelize
/app/node_modules/error-stack-parser
/app/node_modules/getpass
/app/node_modules/color-name
/app/node_modules/strip-json-comments
/app/node_modules/regenerator-transform
/app/node_modules/node-int64
/app/node_modules/postcss
/app/node_modules/internal-slot
/app/node_modules/object-assign
/app/node_modules/pascalcase
/app/node_modules/property-information
/app/node_modules/merge-stream
/app/node_modules/has-symbol-support-x
/app/node_modules/lazy-universal-dotenv
/app/node_modules/cjs-module-lexer
/app/node_modules/@apollo
/app/node_modules/js-queue
/app/node_modules/randomfill
/app/node_modules/vue-docgen-loader
/app/node_modules/@stylelint
/app/node_modules/rgba-regex
/app/node_modules/is-directory
/app/node_modules/deepmerge
/app/node_modules/chalk
/app/node_modules/handle-thing
/app/node_modules/is-map
/app/node_modules/mdast-util-to-markdown
/app/node_modules/timers-browserify
/app/node_modules/cli-highlight
/app/node_modules/jsdom
/app/node_modules/postcss-resolve-nested-selector
/app/node_modules/common-tags
/app/node_modules/workbox-sw
/app/node_modules/domhandler
/app/node_modules/forwarded
/app/node_modules/lodash.merge
/app/node_modules/gauge
/app/node_modules/node-libs-browser
/app/node_modules/apollo-cache-control
/app/node_modules/@apollographql
/app/node_modules/react-syntax-highlighter
/app/node_modules/map-or-similar
/app/node_modules/jsonfile
/app/node_modules/is-callable
/app/node_modules/extsprintf
/app/node_modules/type-check
/app/node_modules/is-number-object
/app/node_modules/stream-browserify
/app/node_modules/internal-ip
/app/node_modules/validate-npm-package-name
/app/node_modules/homedir-polyfill
/app/node_modules/babel-plugin-apply-mdx-type-prop
/app/node_modules/core-js
/app/node_modules/duplexer3
/app/node_modules/busboy
/app/node_modules/cssstyle
/app/node_modules/decompress-tarbz2
/app/node_modules/trough
/app/node_modules/de-indent
/app/node_modules/class-utils
/app/node_modules/jest-validate
/app/node_modules/optionator
/app/node_modules/yaml-front-matter
/app/node_modules/map-cache
/app/node_modules/jest-jasmine2
/app/node_modules/progress
/app/node_modules/@types
/app/node_modules/@hapi
/app/node_modules/es6-shim
/app/node_modules/saxes
/app/node_modules/jquery-validation
/app/node_modules/iferr
/app/node_modules/path-dirname
/app/node_modules/slash
/app/node_modules/eslint
/app/node_modules/better-opn
/app/node_modules/stable
/app/node_modules/acorn-jsx
/app/node_modules/postcss-loader
/app/node_modules/tough-cookie
/app/node_modules/boolbase
/app/node_modules/@akryum
/app/node_modules/collection-visit
/app/node_modules/svgo
/app/node_modules/agent-base
/app/node_modules/lucene-query-parser
/app/node_modules/regjsparser
/app/node_modules/brace-expansion
/app/node_modules/inquirer
/app/node_modules/workbox-streams
/app/node_modules/core-js-pure
/app/node_modules/type-fest
/app/node_modules/cookie-signature
/app/node_modules/char-regex
/app/node_modules/select
/app/node_modules/make-dir
/app/node_modules/mute-stream
/app/node_modules/websocket-driver
/app/node_modules/set-value
/app/node_modules/methods
/app/node_modules/tslib
/app/node_modules/istanbul-lib-instrument
/app/node_modules/vm-browserify
/app/node_modules/caseless
/app/node_modules/github-slugger
/app/node_modules/parent-module
/app/node_modules/http-proxy-agent
/app/node_modules/xmlchars
/app/node_modules/big.js
/app/node_modules/whatwg-url
/app/node_modules/number-is-nan
/app/node_modules/b
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
ork_field_to_edition_field` function to return `Optional[str | Callable[[str], str]]`
5. Update the field conversion logic to handle callable mappings
6. Handle the case where a callable field mapping would replace the root node

Let me start implementing these changes:

[MSG 46] [user]
Observation: 
































































The file /app/openlibrary/solr/query_utils.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/solr/query_utils.py:
     6	
     7	class EmptyTreeError(Exception):
     8	    pass
     9	
    10	
    11	def luqum_remove_child(child: Item, parents: list[Item]):
    12	    """
    13	    Removes a child from a luqum parse tree. If the tree
    14	    ends up being empty, errors.
    15	
    16	    :param child: Node to remove
    17	    :param parents: Path of parent nodes leading from the root of the tree
    18	    """
    19	    parent = parents[-1] if parents else None
    20	    if parent is None:
    21	        # We cannot remove the element if it is the root of the tree
    22	        raise EmptyTreeError()
    23	    elif isinstance(parent, (BaseOperation, Group, Unary)):
    24	        new_children = tuple(c for c in parent.children if c != child)
    25	        if not new_children:
    26	            # If we have deleted all the children, we need to delete the parent
    27	            # as well. And potentially recurse up the tree.
    28	            luqum_remove_child(parent, parents[:-1])
    29	        else:
    30	            parent.children = new_children
    31	    else:
    32	        raise ValueError("Not supported for generic class Item")
    33	
    34	
    35	def luqum_replace_child(old_child: Item, new_child: Item, parents: list[Item]):
    36	    """
    37	    Replaces a child node in a luqum parse tree with a new node.
    38	    
    39	    :param old_child: Node to replace
    40	    :param new_child: New node to replace with
    41	    :param parents: Path of parent nodes leading from the root of the tree
    42	    """
    43	    parent = parents[-1] if parents else None
    44	    if parent is None:
    45	        # Cannot replace the root node directly, caller must handle this case
    46	        raise ValueError("Cannot replace root node using luqum_replace_child")
    47	    elif isinstance(parent, (BaseOperation, Group, Unary)):
    48	        new_children = tuple(
    49	            new_child if c == old_child else c
    50	            for c in parent.children
    51	        )
    52	        parent.children = new_children
    53	    else:
    54	        raise ValueError("Not supported for generic class Item")
    55	
    56	
    57	def luqum_traverse(item: Item, _parents: list[Item] | None = None):
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 47] [assistant]
First, let me add the `luqum_replace_child` function to the query_utils.py file:

[MSG 48] [user]
Observation: 
Here's the result of running `cat -n` on /app/openlibrary/plugins/worksearch/schemes/works.py:
     1	from datetime import datetime
     2	import logging
     3	import re
     4	import sys
     5	from typing import Any, Optional
     6	
     7	import luqum.tree
     8	import web
     9	from openlibrary.plugins.upstream.utils import convert_iso_to_marc
    10	from openlibrary.plugins.worksearch.schemes import SearchScheme
    11	from openlibrary.solr.query_utils import (
    12	    EmptyTreeError,
    13	    fully_escape_query,
    14	    luqum_parser,
    15	    luqum_remove_child,
    16	    luqum_traverse,
    17	)
    18	from openlibrary.utils.ddc import (
    19	    normalize_ddc,
    20	    normalize_ddc_prefix,
    21	    normalize_ddc_range,
    22	)
    23	from openlibrary.utils.isbn import normalize_isbn
    24	from openlibrary.utils.lcc import (
    25	    normalize_lcc_prefix,
    26	    normalize_lcc_range,
    27	    short_lcc_to_sortable_lcc,
    28	)
    29	
    30	logger = logging.getLogger("openlibrary.worksearch")





[MSG 49] [assistant]
Now let me modify the works.py file to implement the required changes. First, let me see the current import statements:

[MSG 50] [user]
Observation: 

































The file /app/openlibrary/plugins/worksearch/schemes/works.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/schemes/works.py:
     1	from datetime import datetime
     2	import logging
     3	import re
     4	import sys
     5	from typing import Any, Callable, Optional
     6	
     7	import luqum.tree
     8	import web
     9	from openlibrary.plugins.upstream.utils import convert_iso_to_marc
    10	from openlibrary.plugins.worksearch.schemes import SearchScheme
    11	from openlibrary.solr.query_utils import (
    12	    EmptyTreeError,
    13	    fully_escape_query,
    14	    luqum_parser,
    15	    luqum_remove_child,
    16	    luqum_replace_child,
    17	    luqum_traverse,
    18	)
    19	from openlibrary.utils.ddc import (
    20	    normalize_ddc,
    21	    normalize_ddc_prefix,
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 51] [assistant]
I need to update the imports and type annotation:

[MSG 52] [user]
Observation: 
Here's the result of running `cat -n` on /app/openlibrary/plugins/worksearch/schemes/works.py:
   265	        ed_q = None
   266	        editions_fq = []
   267	        if has_solr_editions_enabled() and 'editions:[subquery]' in solr_fields:
   268	            WORK_FIELD_TO_ED_FIELD = {
   269	                # Internals
   270	                'edition_key': 'key',
   271	                'text': 'text',
   272	                # Display data
   273	                'title': 'title',
   274	                'title_suggest': 'title_suggest',
   275	                'subtitle': 'subtitle',
   276	                # TODO: Change to alternative_title after full reindex
   277	                'alternative_title': 'title',
   278	                'alternative_subtitle': 'subtitle',
   279	                'cover_i': 'cover_i',
   280	                # Misc useful data
   281	                'language': 'language',
   282	                'publisher': 'publisher',
   283	                'publisher_facet': 'publisher_facet',
   284	                'publish_date': 'publish_date',
   285	                'publish_year': 'publish_year',
   286	                # Identifiers
   287	                'isbn': 'isbn',
   288	                # 'id_*': 'id_*', # Handled manually for now to match any id field
   289	                'ebook_access': 'ebook_access',
   290	                # IA
   291	                'has_fulltext': 'has_fulltext',
   292	                'ia': 'ia',
   293	                'ia_collection': 'ia_collection',
   294	                'ia_box_id': 'ia_box_id',
   295	                'public_scan_b': 'public_scan_b',
   296	            }
   297	
   298	            def convert_work_field_to_edition_field(field: str) -> Optional[str]:
   299	                """
   300	                Convert a SearchField name (eg 'title') to the correct fieldname
   301	                for use in an edition query.
   302	
   303	                If no conversion is possible, return None.
   304	                """
   305	                if field in WORK_FIELD_TO_ED_FIELD:
   306	                    return WORK_FIELD_TO_ED_FIELD[field]
   307	                elif field.startswith('id_'):
   308	                    return field
   309	                elif field in self.all_fields or field in self.facet_fields:
   310	                    return None
   311	                else:
   312	                    raise ValueError(f'Unknown field: {field}')
   313	
   314	            def convert_work_query_to_edition_query(work_query: str) -> str:
   315	                """





[MSG 53] [assistant]
Now let me look at the WORK_FIELD_TO_ED_FIELD definition and the convert_work_field_to_edition_field function:

[MSG 54] [user]
Observation: 
























































The file /app/openlibrary/plugins/worksearch/schemes/works.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/schemes/works.py:
   263	        )
   264	
   265	        ed_q = None
   266	        editions_fq = []
   267	        if has_solr_editions_enabled() and 'editions:[subquery]' in solr_fields:
   268	            WORK_FIELD_TO_ED_FIELD: dict[str, str | Callable[[str], str]] = {
   269	                # Internals
   270	                'edition_key': 'key',
   271	                'text': 'text',
   272	                # Display data
   273	                'title': 'title',
   274	                'title_suggest': 'title_suggest',
   275	                'subtitle': 'subtitle',
   276	                # TODO: Change to alternative_title after full reindex
   277	                'alternative_title': lambda expr: f'title:({expr}) OR subtitle:({expr})',
   278	                'alternative_subtitle': 'subtitle',
   279	                'cover_i': 'cover_i',
   280	                # Misc useful data
   281	                'language': 'language',
   282	                'publisher': 'publisher',
   283	                'publisher_facet': 'publisher_facet',
   284	                'publish_date': 'publish_date',
   285	                'publish_year': 'publish_year',
   286	                # Identifiers
   287	                'isbn': 'isbn',
   288	                # 'id_*': 'id_*', # Handled manually for now to match any id field
   289	                'ebook_access': 'ebook_access',
   290	                # IA
   291	                'has_fulltext': 'has_fulltext',
   292	                'ia': 'ia',
   293	                'ia_collection': 'ia_collection',
   294	                'ia_box_id': 'ia_box_id',
   295	                'public_scan_b': 'public_scan_b',
   296	            }
   297	
   298	            def convert_work_field_to_edition_field(field: str) -> Optional[str]:
   299	                """
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 55] [assistant]
Now I need to update the WORK_FIELD_TO_ED_FIELD dictionary to support both strings and callable functions, and change the alternative_title mapping:

[MSG 56] [user]
Observation: 




























The file /app/openlibrary/plugins/worksearch/schemes/works.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/schemes/works.py:
   293	                'ia_collection': 'ia_collection',
   294	                'ia_box_id': 'ia_box_id',
   295	                'public_scan_b': 'public_scan_b',
   296	            }
   297	
   298	            def convert_work_field_to_edition_field(field: str) -> Optional[str | Callable[[str], str]]:
   299	                """
   300	                Convert a SearchField name (eg 'title') to the correct fieldname
   301	                for use in an edition query.
   302	
   303	                If no conversion is possible, return None.
   304	                """
   305	                if field in WORK_FIELD_TO_ED_FIELD:
   306	                    return WORK_FIELD_TO_ED_FIELD[field]
   307	                elif field.startswith('id_'):
   308	                    return field
   309	                elif field in self.all_fields or field in self.facet_fields:
   310	                    return None
   311	                else:
   312	                    raise ValueError(f'Unknown field: {field}')
   313	
   314	            def convert_work_query_to_edition_query(work_query: str) -> str:
   315	                """
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 57] [assistant]
Now I need to update the convert_work_field_to_edition_field function signature and logic:

[MSG 58] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **HIGH RESOLUTION** (7/13 = 54%) — weak/no contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CLEAN
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 19:13:36

| Field | Value |
|-------|-------|
| Agent understood problem | False |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | None |
| Confidence | 0.98 |
| **Verdict** | **CLEAN** |

**Agent approach**: The agent spent most of the trajectory chasing an unrelated worksearch title/subtitle mapping issue in `works.py`, then only late in the run added a partial `luqum_replace_child` helper. That helper used the wrong API shape (`old_child, new_child, parents`) and the agent never finished wiring or submitted a patch.

**Contamination evidence**: None

**Difficulty evidence**: None

**Full reasoning**: This task looks clean, not contaminated. The problem statement explicitly asks for a helper to replace a child node in a luqum parse tree, with the call shape 'parent, old child, new child', preserving structure and raising `ValueError` for unsupported parent types. The added F2P tests do exactly that: they import `luqum_replace_child`, call it with `(parents[-1], node, luqum_parser(replace_with))`, and assert on the resulting serialized tree for a couple of representative nested cases. Those are direct black-box checks of the stated behavior, not hidden implementation details. The fact that the gold patch also changes `works.py` is overpatch/noise from the downstream use case; the tests shown do not require that larger change. The agent failed because it misunderstood the task almost from the start, repeatedly focusing on an unrelated `alternative_title`/`subtitle` search mapping issue, and when it finally added `luqum_replace_child` it gave it the wrong signature (using a parents list rather than an explicit parent argument) and did not finish or submit a patch before autosubmission. The extra F2P failures for `test_luqum_parser` and `test_luqum_remove_child` are plausibly due to module import failure when `luqum_replace_child` is missing, not because those tests encode undiscoverable requirements.
