# Case #97 Re-Audit Notes (v2)

**Instance**: `instance_internetarchive__openlibrary-7edd1ef09d91fe0b435707633c5cc9af41dedddf-v76304ecdb3a5954fcf13feb710e8c40fcf24b73c`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"#  Autocomplete endpoints lack unified logic and flexible OLID handling\n\n## Description: \n\nCurrently, the autocomplete endpoints (‘/works/_autocomplete’, ‘/authors/_autocomplete’, and ‘/subjects_autocomplete’) contain duplicated and inconsistent logic for handling search queries and embedded OLID detection. Each endpoint implements its own approach for constructing Solr queries, selecting response fields, and applying filters, leading to discrepancies in the returned results and the documen...

**Type**: python | **Repo**: internetarchive/openlibrary
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 2 |
| Gold patch files | 2 |
| Gold patch size | 9581 chars |
| Test patch size | 4187 chars |
| Test patch files | 1 |
| F2P tests | 2 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
openlibrary/plugins/worksearch/tests/test_autocomplete.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 1d2cbffd8cbda42d71d50a045a8d2b9ebfe1f781
git clean -fd 
git checkout 1d2cbffd8cbda42d71d50a045a8d2b9ebfe1f781 
git checkout 7edd1ef09d91fe0b435707633c5cc9af41dedddf -- openlibrary/plugins/worksearch/tests/test_autocomplete.py
```

## 3. Trajectory Evidence

### Resolution Rate: 0/13 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 37 |
| Claude Sonnet 4 - paper | FAIL | 25 |
| Gemini 2.5 Pro Preview - paper | FAIL | 12 |
| GPT-4o - paper | FAIL | 17 |
| GPT-5 High - paper | FAIL | 28 |
| GPT OSS - paper | FAIL | 49 |
| Kimi - paper | FAIL | 33 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 77 |
| Claude 4 Sonnet - 10132025 | FAIL | 45 |
| GPT-5 - 10132025 | FAIL | 25 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 19 |
| GPT-5 Codex -- debug-oct22 | FAIL | 125 |
| GLM-4.5 -- 10222025 | FAIL | 51 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 65
- **Total tokens**: ~24813
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
/app/renovate.json
/app/requirements_test.txt
/app/infogami
/app/docker
/app/docker/ol-nginx-start.sh
/app/docker/ol-home-start.sh
/app/docker/ol-solr-updater-start.sh
/app/docker/ol-infobase-start.sh
/app/docker/ol-web-start.sh
/app/docker/nginx.conf
/app/docker/ol-db-init.sh
/app/docker/infobase_nginx.conf
/app/docker/Dockerfile.oldev
/app/docker/README.md
/app/docker/ol-affiliate-server-start.sh
/app/docker/web_nginx.conf
/app/docker/ol-importbot-start.sh
/app/docker/covers_nginx.conf
/app/docker/ol-covers-start.sh
/app/docker/public_nginx.conf
/app/docker/Dockerfile.olbase
/app/docker/ol-cron-start.sh
/app/config
/app/Readme_chinese.md
/app/setup.py
/app/compose.override.yaml
/app/tests
/app/tests/screenshots
/app/tests/unit
/app/tests/test_docker_compose.py
/app/tests/integration
/app/compose.production.yaml
/app/CONTRIBUTING.md
/app/CODE_OF_CONDUCT.md
/app/compose.infogami-local.yaml
/app/node_modules
/app/node_modules/has-bigints
/app/node_modules/xml2js
/app/node_modules/download-git-repo
/app/node_modules/ci-env
/app/node_modules/public-encrypt
/app/node_modules/import-local
/app/node_modules/html-encoding-sniffer
/app/node_modules/html-minifier
/app/node_modules/file-uri-to-path
/app/node_modules/ecc-jsbn
/app/node_modules/arr-diff
/app/node_modules/yaml-front-matter
/app/node_modules/ipaddr.js
/app/node_modules/finalhandler
/app/node_modules/copy-to-clipboard
/app/node_modules/iterate-value
/app/node_modules/sane
/app/node_modules/arr-union
/app/node_modules/mdast-util-from-markdown
/app/node_modules/tasklist
/app/node_modules/fs-capacitor
/app/node_modules/postcss-selector-parser
/app/node_modules/lodash.memoize
/app/node_modules/slick-carousel
/app/node_modules/ansi-align
/app/node_modules/express-history-api-fallback
/app/node_modules/hast-util-to-parse5
/app/node_modules/parse5
/app/node_modules/bser
/app/node_modules/is-plain-object
/app/node_modules/clipboardy
/app/node_modules/less
/app/node_modules/watchpack
/app/node_modules/http-proxy
/app/node_modules/path-dirname
/app/node_modules/class-utils
/app/node_modules/babel-plugin-polyfill-corejs3
/app/node_modules/@tootallnate
/app/node_modules/ext-list
/app/node_modules/js-queue
/app/node_modules/jest-docblock
/app/node_modules/react-fast-compare
/app/node_modules/keyv
/app/node_modules/tweetnacl
/app/node_modules/regex-not
/app/node_modules/is-ssh
/app/node_modules/ignore-by-default
/app/node_modules/react-element-to-jsx-string
/app/node_modules/internal-ip
/app/node_modules/buffer
/app/node_modules/dom-serializer
/app/node_modules/rgba-regex
/app/node_modules/prelude-ls
/app/node_modules/fast-glob
/app/node_modules/comma-separated-tokens
/app/node_modules/postcss-less
/app/node_modules/pngjs
/app/node_modules/istanbul-lib-source-maps
/app/node_modules/dns-packet
/app/node_modules/send
/app/node_modules/@sinclair
/app/node_modules/cssesc
/app/node_modules/performance-now
/app/node_modules/react-lifecycles-compat
/app/node_modules/html-escaper
/app/node_modules/neat-csv
/app/node_modules/callsites
/app/node_modules/del
/app/node_modules/gensync
/app/node_modules/domain-browser
/app/node_modules/create-ecdh
/app/node_modules/pug-strip-comments
/app/node_modules/http-signature
/app/node_modules/element-resize-detector
/app/node_modules/vue-multiselect
/app/node_modules/postcss-normalize-repeat-style
/app/node_modules/prismjs
/app/node_modules/compute-scroll-into-view
/app/node_modules/postcss-normalize-positions
/app/node_modules/postcss-normalize-unicode
/app/node_modules/balanced-match
/app/node_modules/promise
/app/node_modules/highlight.js
/app/node_modules/@mrmlnc
/app/node_modules/ext-name
/app/node_modules/loglevel
/app/node_modules/streamsearch
/app/node_modules/datatables.net-dt
/app/node_modules/glob
/app/node_modules/react-sizeme
/app/node_modules/cp-file
/app/node_modules/object-keys
/app/node_modules/minipass-flush
/app/node_modules/ora
/app/node_modules/sinon
/app/node_modules/is-symbol
/app/node_modules/postcss-flexbugs-fixes
/app/node_modules/inherits
/app/node_modules/path-key
/app/node_modules/@reach
/app/node_modules/select-hose
/app/node_modules/istanbul-lib-coverage
/app/node_modules/deprecated-decorator
/app/node_modules/vue-eslint-parser
/app/node_modules/postcss-modules-local-by-default
/app/node_modules/minimist
/app/node_modules/fresh
/app/node_modules/worker-farm
/app/node_modules/resolve-url
/app/node_modules/constantinople
/app/node_modules/to-regex-range
/app/node_modules/is-string
/app/node_modules/json-buffer
/app/node_modules/elliptic
/app/node_modules/uri-js
/app/node_modules/is-absolute-url
/app/node_modules/isurl
/app/node_modules/escape-string-regexp
/app/node_modules/p-limit
/app/node_modules/parse-url
/app/node_modules/defer-to-connect
/app/node_modules/ramda
/app/node_modules/copy-anything
/app/node_modules/hash-sum
/app/node_modules/html-void-elements
/app/node_modules/generate-function
/app/node_modules/duplexer3
/app/node_modules/strip-eof
/app/node_modules/string_decoder
/app/node_modules/ms
/app/node_modules/browserify-sign
/app/node_modules/querystringify
/app/node_modules/set-blocking
/app/node_modules/on-finished
/app/node_modules/iferr
/app/node_modules/has-unicode
/app/node_modules/is-word-character
/app/node_modules/esutils
/app/node_modules/bytes
/app/node_modules/istanbul-lib-report
/app/node_modules/any-promise
/app/node_modules/builtins
/app/node_modules/js-yaml
/app/node_modules/@emotion
/app/node_modules/postcss-minify-params
/app/node_modules/globals
/app/node_modules/p-timeout
/app/node_modules/token-stream
/app/node_modules/git-up
/app/node_modules/buffer-json
/app/node_modules/agent-base
/app/node_modules/connect-history-api-fallback
/app/node_modules/pend
/app/node_modules/unicode-match-property-value-ecmascript
/app/node_modules/react-inspector
/app/node_modules/csso
/app/node_modules/interpret
/app/node_modules/es-abstract
/app/node_modules/array-union
/app/node_modules/fd-slicer
/app/node_modules/braces
/app/node_modules/jest-each
/app/node_modules/selfsigned
/app/node_modules/delegates
/app/node_modules/delayed-stream
/app/node_modules/cssfilter
/app/node_modules/array.prototype.map
/app/node_modules/good-listener
/app/node_modules/xmlbuilder
/app/node_modules/doctrine
/app/node_modules/strict-uri-encode
/app/node_modules/object-copy
/app/node_modules/apollo-server-caching
/app/node_modules/prebuild-install
/app/node_modules/lodash.clonedeep
/app/node_modules/fs-monkey
/app/node_modules/p-try
/app/node_modules/exec-sh
/app/node_modules/is-natural-number
/app/node_modules/tesseract.js-core
/app/node_modules/http-proxy-middleware
/app/node_modules/gl-vec2
/app/node_modules/urix
/app/node_modules/@apollographql
/app/node_modules/abab
/app/node_modules/hsl-regex
/app/node_modules/to-buffer
/app/node_modules/minipass-collect
/app/node_modules/argparse
/app/node_modules/require-from-string
/app/node_modules/hash.js
/app/node_modules/postcss-discard-duplicates
/app/node_modules/object.values
/app/node_modules/eslint-plugin-vue
/app/node_modules/sec
/app/node_modules/diffie-hellman
/app/node_modules/chartjs-plugin-datalabels
/app/node_modules/extend-shallow
/app/node_modules/postcss-merge-rules
/app/node_modules/require-directory
/app/node_modules/babel-eslint
/app/node_modules/acorn
/app/node_modules/symbol-observable
/app/node_modules/unbox-primitive
/app/node_modules/worker-rpc
/app/node_modules/graphql-tag
/app/node_modules/clean-css
/app/node_modules/warning
/app/node_modules/xml-name-validator
/app/node_modules/collect-v8-coverage
/app/node_modules/mz
/app/node_modules/workbox-navigation-preload
/app/node_modules/cacache
/app/node_modules/core-js-compat
/app/node_modules/select
/app/node_modules/resolve-from
/app/node_modules/string.prototype.trimstart
/app/node_modules/object-path
/app/node_modules/jest-mock
/app/node_modules/buffer-from
/app/node_modules/loader-fs-cache
/app/node_modules/babel-plugin-
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
to_json(docs)
    78	
    79	
    80	class languages_autocomplete(delegate.page):
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 37] [assistant]
Perfect! The new functions are working correctly. Now I need to refactor the autocomplete.py file to use the unified approach. Let me create the new autocomplete.py file:

[MSG 38] [user]
Observation: 





































































The file /app/openlibrary/plugins/worksearch/autocomplete.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/autocomplete.py:
    86	        return to_json(
    87	            list(itertools.islice(utils.autocomplete_languages(i.q), i.limit))
    88	        )
    89	
    90	
    91	class works_autocomplete(autocomplete):
    92	    """Autocomplete for works with unified logic."""
    93	    path = "/works/_autocomplete"
    94	    
    95	    def __init__(self):
    96	        super().__init__()
    97	        self.query_template = 'title:"{q}"^2 OR title:({q}*)'
    98	        self.fq = 'type:work AND key:*W'
    99	        self.fl = 'key,title,subtitle,cover_i,first_publish_year,author_name,edition_count'
   100	        self.sort = 'edition_count desc'
   101	        self.olid_suffix = 'W'
   102	        self.result_processor = self._process_works_results
   103	    
   104	    def _process_works_results(self, docs):
   105	        """Process work results to add required frontend fields."""
   106	        processed_docs = []
   107	        for d in docs:
   108	            # Exclude fake works that actually have an edition key
   109	            if d['key'][-1] == 'W':
   110	                # Required by the frontend
   111	                d['name'] = d['key'].split('/')[-1]
   112	                d['full_title'] = d['title']
   113	                if 'subtitle' in d:
   114	                    d['full_title'] += ": " + d['subtitle']
   115	                processed_docs.append(d)
   116	        return processed_docs
   117	
   118	
   119	class authors_autocomplete(delegate.page):
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 39] [assistant]
Now let me implement the specific autocomplete classes. First, let me replace the works_autocomplete class:

[MSG 40] [user]
Observation: 






























































The file /app/openlibrary/plugins/worksearch/autocomplete.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/autocomplete.py:
   114	                    d['full_title'] += ": " + d['subtitle']
   115	                processed_docs.append(d)
   116	        return processed_docs
   117	
   118	
   119	class authors_autocomplete(autocomplete):
   120	    """Autocomplete for authors with unified logic.""" 
   121	    path = "/authors/_autocomplete"
   122	    
   123	    def __init__(self):
   124	        super().__init__()
   125	        self.query_template = 'name:({q}*) OR alternate_names:({q}*)'
   126	        self.fq = 'type:author'
   127	        self.fl = '*'  # Get all fields to access top_work and top_subjects
   128	        self.sort = 'work_count desc'
   129	        self.olid_suffix = 'A'
   130	        self.result_processor = self._process_authors_results
   131	    
   132	    def _process_authors_results(self, docs):
   133	        """Process author results to convert top_work and top_subjects."""
   134	        for d in docs:
   135	            if 'top_work' in d:
   136	                d['works'] = [d.pop('top_work')]
   137	            else:
   138	                d['works'] = []
   139	            d['subjects'] = d.pop('top_subjects', [])
   140	        return docs
   141	
   142	
   143	class subjects_autocomplete(delegate.page):
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 41] [assistant]
Now let me replace the authors_autocomplete class:

[MSG 42] [user]
Observation: 






















































The file /app/openlibrary/plugins/worksearch/autocomplete.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/autocomplete.py:
   138	                d['works'] = []
   139	            d['subjects'] = d.pop('top_subjects', [])
   140	        return docs
   141	
   142	
   143	class subjects_autocomplete(delegate.page):
   144	    """Autocomplete for subjects with optional type filtering."""
   145	    path = "/subjects_autocomplete"
   146	    # can't use /subjects/_autocomplete because the subjects endpoint = /subjects/[^/]+
   147	
   148	    def GET(self):
   149	        i = web.input(q="", type="", limit=5)
   150	        i.limit = safeint(i.limit, 5)
   151	
   152	        solr = get_solr()
   153	        prefix_q = solr.escape(i.q).strip()
   154	        solr_q = f'name:({prefix_q}*)'
   155	        
   156	        # Add subject_type filter if type is provided
   157	        fq = 'type:subject'
   158	        if i.type:
   159	            fq += f' AND subject_type:{i.type}'
   160	
   161	        params = {
   162	            'fl': 'key,name,subject_type,work_count',
   163	            'q_op': 'AND',
   164	            'fq': fq,
   165	            'sort': 'work_count desc',
   166	            'rows': i.limit,
   167	        }
   168	
   169	        data = solr.select(solr_q, **params)
   170	        # Return only key and name fields as specified
   171	        docs = [{'key': d['key'], 'name': d['name']} for d in data['docs']]
   172	
   173	        return to_json(docs)
   174	
   175	
   176	def setup():
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 43] [assistant]
Now let me replace the subjects_autocomplete class:

[MSG 44] [user]
Observation: 
Trying:
    extract_numeric_id_from_olid("OL123W")
Expecting:
    '123'
ok
Trying:
    extract_numeric_id_from_olid("/authors/OL123A")
Expecting:
    '123'
ok
Trying:
    find_author_olid_in_string("ol123a")
Expecting:
    'OL123A'
ok
Trying:
    find_author_olid_in_string("/authors/OL123A/edit")
Expecting:
    'OL123A'
ok
Trying:
    find_author_olid_in_string("some random string")
Expecting nothing
ok
Trying:
    find_olid_in_string("ol123a")
Expecting:
    'OL123A'
ok
Trying:
    find_olid_in_string("/authors/OL123A/edit")
Expecting:
    'OL123A'
ok
Trying:
    find_olid_in_string("ol456w", "W")
Expecting:
    'OL456W'
ok
Trying:
    find_olid_in_string("ol456w", "A")
Expecting nothing
ok
Trying:
    find_olid_in_string("some random string")
Expecting nothing
ok
Trying:
    find_work_olid_in_string("ol123w")
Expecting:
    'OL123W'
ok
Trying:
    find_work_olid_in_string("/works/OL123W/Title_of_book")
Expecting:
    'OL123W'
ok
Trying:
    find_work_olid_in_string("some random string")
Expecting nothing
ok
Trying:
    dicts = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
Expecting nothing
ok
Trying:
    sorted(finddict(dicts, x=1).items())
Expecting:
    [('x', 1), ('y', 2)]
ok
Trying:
    all(is_number(n) for n in (1234, "1234", -1234, "-1234", 123.4, -123.4))
Expecting:
    True
ok
Trying:
    not any(is_number(n) for n in ("123.4", "-123.4", "123a", "--1234"))
Expecting:
    True
ok
Trying:
    multisort_best([], [])
Expecting nothing
ok
Trying:
    multisort_best([3,4,5], [('max', lambda x: x)])
Expecting:
    5
ok
Trying:
    multisort_best([
        {'provider': 'ia', 'size': 4},
        {'provider': 'ia', 'size': 12},
        {'provider': None, 'size': 42},
    ], [
        ('min', lambda x: 0 if x['provider'] == 'ia' else 1),
        ('max', lambda x: x['size']),
    ])
Expecting:
    {'provider': 'ia', 'size': 12}
ok
Trying:
    olid_to_key("OL123A")
Expecting:
    '/authors/'
ok
Trying:
    olid_to_key("OL456W") 
Expecting:
    '/works/'
ok
Trying:
    olid_to_key("OL789M")
Expecting:
    '/books/'
ok
Trying:
    olid_to_key("OL123X")
Expecting:
    Traceback (most recent call last):
    ...
    ValueError: Unknown OLID suffix: X
ok
Trying:
    str_to_key("?H$e##l{o}[0] -world!")
Expecting:
    'helo0_-world!'
ok
Trying:
    str_to_key("".join(to_drop))
Expecting:
    ''
ok
Trying:
    str_to_key("")
Expecting:
    ''
ok
Trying:
    take_best([], 'min', lambda x: x)
Expecting:
    []
ok
Trying:
    take_best([3, 2, 1], 'min', lambda x: x)
Expecting:
    [1]
ok
Trying:
    take_best([3, 4, 5], 'max', lambda x: x)
Expecting:
    [5]
ok
Trying:
    take_best([4, 1, -1, -1], 'min', lambda x: x)
Expecting:
    [-1, -1]
ok
Trying:
    uniq("abcbcddefefg")
Expecting:
    ['a', 'b', 'c', 'd', 'e', 'f', 'g']
ok
Trying:
    uniq("011223344556677889")
Expecting:
    ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
ok
8 items had no tests:
    __init__
    __init__.OrderedEnum
    __init__.OrderedEnum.__ge__
    __init__.OrderedEnum.__gt__
    __init__.OrderedEnum.__le__
    __init__.OrderedEnum.__lt__
    __init__.dicthash
    __init__.get_software_version
11 items passed all tests:
   2 tests in __init__.extract_numeric_id_from_olid
   3 tests in __init__.find_author_olid_in_string
   5 tests in __init__.find_olid_in_string
   3 tests in __init__.find_work_olid_in_string
   2 tests in __init__.finddict
   2 tests in __init__.is_number
   3 tests in __init__.multisort_best
   4 tests in __init__.olid_to_key
   3 tests in __init__.str_to_key
   4 tests in __init__.take_best
   2 tests in __init__.uniq
33 tests in 19 items.
33 passed and 0 failed.
Test passed.




[MSG 45] [assistant]
Now let me test the doctests for the new functions:

[MSG 46] [user]
Observation: 



































































































File created successfully at: /app/test_new_autocomplete.py




[MSG 47] [assistant]
Excellent! All doctests pass. Now let me test the modified autocomplete functions by writing a test script:

[MSG 48] [user]
Observation: 
Testing unified OLID functions...
✓ All unified OLID function tests passed
Testing autocomplete class structure...
✓ All autocomplete class tests passed
✓ All tests passed!




[MSG 49] [user]
Observation: 
Import successful




[MSG 50] [assistant]
Excellent! Now let me check if there are any syntax issues by doing a simple import test:

[MSG 51] [user]
Observation: 





















































































File created successfully at: /app/test_edge_cases.py




[MSG 52] [assistant]
Great! Now let me run a final test to verify the docstrings and edge cases:

[MSG 53] [user]
Observation: 
Testing edge cases...
✓ All edge case tests passed
Testing path extraction...
✓ All path extraction tests passed
✓ All edge case tests passed!




[MSG 54] [user]
Observation: 
/app/test_autocomplete.py
/app/test_new_autocomplete.py
/app/test_edge_cases.py




[MSG 55] [assistant]
Perfect! Now let me check if there are any existing unit tests for the autocomplete module that I need to update:

[MSG 56] [user]
Observation: 
Testing doctests...
Done




[MSG 57] [assistant]
It seems there aren't existing Python unit tests for the autocomplete functionality. That's fine since the PR description mentions they've already taken care of test file changes. 

Let me now run the doctests to make sure they pass:

[MSG 58] [user]
Observation: 
Old functions still work: OL123A OL456W




[MSG 59] [assistant]
Great! Now let me verify that the old OLID functions still work to ensure backward compatibility:

[MSG 60] [user]
Observation: 




[MSG 61] [assistant]
Let me also add the updated imports to the utils module's __init__.py file to make sure the new functions are available:

[MSG 62] [user]
Observation: 
All functions imported successfully




[MSG 63] [assistant]
It looks like there isn't an explicit `__all__` list, so the functions should be available automatically. Let me verify that all the functions are accessible:

[MSG 64] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **ALL AGENTS FAIL** (13 runs, 0 pass) — strong contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CONFIRMED_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 20:57:38

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | test_coupling |
| Confidence | 0.96 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent inspected the three autocomplete endpoints and OLID helpers, then started refactoring toward a shared base autocomplete class plus generalized OLID extraction/conversion utilities. It also partially rewrote works/authors handling and added fallback logic for missing Solr hits, but never finalized or submitted a patch.

**Contamination evidence**: The F2P tests are coupled to gold-patch internals rather than just required behavior. They import and instantiate a specific base class named `autocomplete`, assert an exact Solr query string ordering (`title:"foo"^2 OR title:(foo*) OR name:"foo"^2 OR name:(foo*)`) instead of accepting equivalent queries, require `fq` to be a list with exact contents, and—most clearly—patch `openlibrary.plugins.worksearch.autocomplete.autocomplete.db_fetch` and assert it is called with `/works/OL123W`. The problem statement only requires fallback to the primary data source; any correct implementation using `web.ctx.site.get(...)` directly or a differently named helper would fail. The works test also requires `fq == ['type:work', 'key:*W']`, but `key:*W` is not stated in the problem description.

**Difficulty evidence**: None

**Full reasoning**: This task appears contaminated even though the agent itself timed out without submitting a patch. The problem statement is fairly high-level: unify endpoint logic, include exact and starts-with matching on title/name, exclude editions, honor limit, and support OLID lookup with DB fallback when Solr misses. The tests, however, enforce specific implementation details from the gold patch. They require a concrete base class named `autocomplete`, exact query-string text and ordering rather than semantically equivalent Solr queries, a particular representation of filters as lists, a specific works-only `key:*W` filter not stated in the prompt, and a dedicated helper method `db_fetch` invoked in the fallback path. A solution that fully satisfies the stated behavior but uses direct DB access instead of `db_fetch`, or builds an equivalent query in a different order, would still fail. That is classic test coupling / approach lock contamination. The agent did understand the task and began a reasonable refactor, but its no-patch outcome is separate from the underlying benchmark issue: the F2P tests are stricter than the spec in ways not derivable from the prompt.
