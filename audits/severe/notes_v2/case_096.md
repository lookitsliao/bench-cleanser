# Case #96 Re-Audit Notes (v2)

**Instance**: `instance_internetarchive__openlibrary-5fb312632097be7e9ac6ab657964af115224d15d-v0f5aece3601a5b4419f7ccec1dbda2071be28ee4`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

# Title: Missing support for structured retrieval of external profiles from Wikidata entities

## Description
Author pages do not show external profile links from Wikidata in a structured or language-aware way, even though Wikidata has Wikipedia links in different languages and identifiers for external services like Google Scholar. This makes it harder for users to reach trusted external sources about an author.

## Current Behavior
The model does not resolve Wikipedia sitelinks according to a v...

**Type**: python | **Repo**: internetarchive/openlibrary
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 8 |
| Gold patch files | 8 |
| Gold patch size | 174888 chars |
| Test patch size | 4941 chars |
| Test patch files | 1 |
| F2P tests | 4 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
openlibrary/tests/core/test_wikidata.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 7549c413a901a640aa351933392f503648d345cc
git clean -fd 
git checkout 7549c413a901a640aa351933392f503648d345cc 
git checkout 5fb312632097be7e9ac6ab657964af115224d15d -- openlibrary/tests/core/test_wikidata.py
```

## 3. Trajectory Evidence

### Resolution Rate: 0/14 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 38 |
| Claude Sonnet 4 - paper | FAIL | 22 |
| Gemini 2.5 Pro Preview - paper | FAIL | 12 |
| GPT-4o - paper | FAIL | 23 |
| GPT-5 High - paper | FAIL | 29 |
| GPT OSS - paper | FAIL | 51 |
| Kimi - paper | FAIL | 43 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 51 |
| Claude 4 Sonnet - 10132025 | FAIL | 40 |
| GPT-5 - 10132025 | FAIL | 25 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 9 |
| GPT-5 Codex -- debug-oct22 | FAIL | 116 |
| GLM-4.5 -- 10222025 | FAIL | 18 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 50 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 65
- **Total tokens**: ~28360
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
/app/webpack.config.js
/app/SECURITY.md
/app/conf
/app/conf/twa
/app/conf/email.ini
/app/conf/solr
/app/conf/openlibrary.yml
/app/conf/coverstore.yml
/app/conf/svgo.config.js
/app/conf/logging.ini
/app/conf/infobase.yml
/app/config
/app/compose.yaml
/app/scripts
/app/scripts/update_stale_work_references.py
/app/scripts/dump-ratings.sql
/app/scripts/tests
/app/scripts/infobase-server
/app/scripts/i18n-messages
/app/scripts/_init_path.py
/app/scripts/run_doctests.sh
/app/scripts/import_pressbooks.py
/app/scripts/Readme.txt
/app/scripts/detect_missing_i18n.py
/app/scripts/install_openresty.sh
/app/scripts/delete_import_items.py
/app/scripts/cron_watcher.py
/app/scripts/dump-reading-log.sql
/app/scripts/apply_offline_mode.sh
/app/scripts/oldump.py
/app/scripts/__init__.py
/app/scripts/sitemaps
/app/scripts/make-integration-branch-sample.txt
/app/scripts/coverstore-server
/app/scripts/install_nodejs.sh
/app/scripts/run_olserver.sh
/app/scripts/gh_scripts
/app/scripts/test_py3.sh
/app/scripts/setup_olserver.sh
/app/scripts/generate-api-docs.py
/app/scripts/copydocs.py
/app/scripts/partner_batch_imports.py
/app/scripts/providers
/app/scripts/promise_batch_imports.py
/app/scripts/upstream-adapter
/app/scripts/dev-instance
/app/scripts/obfi
/app/scripts/open_syllabus_project_parser.py
/app/scripts/pull-templates.py
/app/scripts/openlibrary-server
/app/scripts/solr_builder
/app/scripts/setup_gitpod.sh
/app/scripts/pr_slack_digest.py
/app/scripts/migrate_db.py
/app/scripts/get_web_error.py
/app/scripts/make-integration-branch.sh
/app/scripts/import_standard_ebooks.py
/app/scripts/update-loans.py
/app/scripts/dump-covers-metadata.sql
/app/scripts/fake_loan_server.py
/app/scripts/deployment
/app/scripts/lc_marc_update.py
/app/scripts/__pycache__
/app/scripts/oclc_to_marc.py
/app/scripts/mail_bad_author_query.py
/app/scripts/affiliate_server.py
/app/scripts/store_counts.py
/app/scripts/decode_ip.sh
/app/scripts/manage-imports.py
/app/scripts/import_open_textbook_library.py
/app/scripts/solr_restarter
/app/scripts/expire_accounts.py
/app/scripts/solr_updater.py
/app/scripts/oldump.sh
/app/scripts/solr_dump_xisbn.py
/app/scripts/start-solr.sh
/app/package.json
/app/openlibrary
/app/openlibrary/plugins
/app/openlibrary/admin
/app/openlibrary/coverstore
/app/openlibrary/mocks
/app/openlibrary/app.py
/app/openlibrary/i18n
/app/openlibrary/catalog
/app/openlibrary/components
/app/openlibrary/__pycache__
/app/openlibrary/accounts
/app/openlibrary/book_providers.py
/app/openlibrary/actions.py
/app/openlibrary/__init__.py
/app/openlibrary/macros
/app/openlibrary/data
/app/openlibrary/config.py
/app/openlibrary/conftest.py
/app/openlibrary/tests
/app/openlibrary/core
/app/openlibrary/solr
/app/openlibrary/views
/app/openlibrary/records
/app/openlibrary/olbase
/app/openlibrary/templates
/app/openlibrary/api.py
/app/openlibrary/code.py
/app/openlibrary/utils
/app/compose.staging.yaml
/app/requirements.txt
/app/stories
/app/stories/README.md
/app/stories/Introduction.mdx
/app/stories/Button.stories.js
/app/Readme.md
/app/compose.production.yaml
/app/node_modules
/app/node_modules/is-accessor-descriptor
/app/node_modules/thenify
/app/node_modules/chardet
/app/node_modules/@rollup
/app/node_modules/punycode
/app/node_modules/natural-compare
/app/node_modules/loader-utils
/app/node_modules/jquery-validation
/app/node_modules/proxy-from-env
/app/node_modules/babel-plugin-named-exports-order
/app/node_modules/fraction.js
/app/node_modules/@leichtgewicht
/app/node_modules/string.prototype.trim
/app/node_modules/jsdom
/app/node_modules/get-own-enumerable-property-symbols
/app/node_modules/de-indent
/app/node_modules/copy-descriptor
/app/node_modules/domutils
/app/node_modules/sort-keys
/app/node_modules/handlebars
/app/node_modules/data-view-buffer
/app/node_modules/braces
/app/node_modules/decompress
/app/node_modules/@sinonjs
/app/node_modules/get-nonce
/app/node_modules/pretty-bytes
/app/node_modules/content-disposition
/app/node_modules/process-exists
/app/node_modules/jsesc
/app/node_modules/ieee754
/app/node_modules/@aw-web-design
/app/node_modules/snapdragon
/app/node_modules/jest-changed-files
/app/node_modules/typed-array-buffer
/app/node_modules/loader-runner
/app/node_modules/buffer-from
/app/node_modules/yallist
/app/node_modules/to-regex
/app/node_modules/postcss-value-parser
/app/node_modules/es-define-property
/app/node_modules/workbox-routing
/app/node_modules/xtend
/app/node_modules/is-potential-custom-element-name
/app/node_modules/sax
/app/node_modules/dir-glob
/app/node_modules/quick-lru
/app/node_modules/image-size
/app/node_modules/is-obj
/app/node_modules/css-loader
/app/node_modules/detect-package-manager
/app/node_modules/read-pkg-up
/app/node_modules/ansi-styles
/app/node_modules/vue-eslint-parser
/app/node_modules/git-clone
/app/node_modules/postcss-minify-params
/app/node_modules/is-number-object
/app/node_modules/is-descriptor
/app/node_modules/details-polyfill
/app/node_modules/nice-try
/app/node_modules/sisteransi
/app/node_modules/string_decoder
/app/node_modules/mime-types
/app/node_modules/clone
/app/node_modules/hasown
/app/node_modules/thenify-all
/app/node_modules/gopd
/app/node_modules/right-pad
/app/node_modules/event-pubsub
/app/node_modules/is-module
/app/node_modules/import-local
/app/node_modules/postcss-ordered-values
/app/node_modules/caller-callsite
/app/node_modules/string.prototype.trimstart
/app/node_modules/is-plain-object
/app/node_modules/faye-websocket
/app/node_modules/@szmarczak
/app/node_modules/destroy
/app/node_modules/ret
/app/node_modules/assign-symbols
/app/node_modules/@sindresorhus
/app/node_modules/node-forge
/app/node_modules/irregular-plurals
/app/node_modules/serve-static
/app/node_modules/picomatch
/app/node_modules/bmp-js
/app/node_modules/urix
/app/node_modules/p-try
/app/node_modules/send
/app/node_modules/portfinder
/app/node_modules/loglevel
/app/node_modules/normalize-range
/app/node_modules/get-pixels
/app/node_modules/agent-base
/app/node_modules/esbuild-plugin-alias
/app/node_modules/path-scurry
/app/node_modules/json-schema-traverse
/app/node_modules/is-gzip
/app/node_modules/yaml-front-matter
/app/node_modules/bonjour-service
/app/node_modules/escape-goat
/app/node_modules/workbox-expiration
/app/node_modules/eventemitter3
/app/node_modules/cli-table3
/app/node_modules/postcss-reduce-transforms
/app/node_modules/shellwords
/app/node_modules/istanbul-lib-instrument
/app/node_modules/decompress-tar
/app/node_modules/glob-parent
/app/node_modules/cli-highlight
/app/node_modules/address
/app/node_modules/ext-list
/app/node_modules/@sideway
/app/node_modules/unicode-match-property-value-ecmascript
/app/node_modules/has-tostringtag
/app/node_modules/compression
/app/node_modules/finalhandler
/app/node_modules/nodemon
/app/node_modules/dot-case
/app/node_modules/whatwg-mimetype
/app/node_modules/source-map
/app/node_modules/is-nan
/app/node_modules/minimist-options
/app/node_modules/workbox-recipes
/app/node_modules/magic-string
/app/node_modules/chownr
/app/node_modules/saxes
/app/node_modules/opencollective-postinstall
/app/node_modules/progress-webpack-plugin
/app/node_modules/ajv
/app/node_modules/@discoveryjs
/app/node_modules/require-directory
/app/node_modules/postcss-convert-values
/app/node_modules/onetime
/app/node_modules/thunky
/app/node_modules/param-case
/app/node_modules/flot
/app/node_modules/make-dir
/app/node_modules/class-utils
/app/node_modules/https-proxy-agent
/app/node_modules/@ericblade
/app/node_modules/istanbul-lib-source-maps
/app/node_modules/app-root-dir
/app/node_modules/brace-expansion
/app/node_modules/object.pick
/app/node_modules/@josephg
/app/node_modules/@akryum
/app/node_modules/launch-editor-middleware
/app/node_modules/source-map-resolve
/app/node_modules/tiny-invariant
/app/node_modules/utils-merge
/app/node_modules/bytes
/app/node_modules/deepmerge
/ap
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
	        return None
   784	
   785	    def __repr__(self):
   786	        return "<Author: %s>" % repr(self.key)
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 53] [assistant]
Now let me fix the Author model to actually use the wikidata functionality. I need to remove the early return None statement:

[MSG 54] [user]
Observation: 

Testing existing WikidataEntity functionality:
- ID: Q42
- English description: English writer
- German description (should fallback to EN): englischer Schriftsteller
- Nonexistent language description (should fallback to EN): English writer

Testing missing functionality that needs to be implemented:
✓ SOCIAL_PROFILE_CONFIGS found: [{'icon_name': 'google_scholar.svg', 'wikidata_property': 'P1960', 'label': 'Google Scholar', 'base_url': 'https://scholar.google.com/citations?user='}]
✓ get_external_profiles function found
✓ _get_wiki_profiles function found
✓ _get_wikipedia_link function found
✓ _get_statement_values function found

This script will be updated as we implement the missing functionality.






[MSG 55] [assistant]
Now let's test our implementation:

[MSG 56] [user]
Observation: 































































































































































































































































The file /app/test_wikidata_implementation.py has been edited. Here's the result of running `cat -n` on a snippet of /app/test_wikidata_implementation.py:
    43	    print(f"- English description: {entity.get_description('en')}")
    44	    print(f"- German description (should fallback to EN): {entity.get_description('de')}")
    45	    print(f"- Nonexistent language description (should fallback to EN): {entity.get_description('fr')}")
    46	    print()
    47	
    48	def test_new_functionality():
    49	    """Test the new functionality that has been implemented"""
    50	    
    51	    print("Testing newly implemented functionality:")
    52	    
    53	    # Import all the new functions
    54	    from openlibrary.core.wikidata import (
    55	        SOCIAL_PROFILE_CONFIGS, 
    56	        get_external_profiles, 
    57	        _get_wiki_profiles, 
    58	        _get_wikipedia_link, 
    59	        _get_statement_values
    60	    )
    61	    
    62	    print(f"✓ SOCIAL_PROFILE_CONFIGS found: {SOCIAL_PROFILE_CONFIGS}")
    63	    print("✓ All functions imported successfully")
    64	    
    65	    # Create test data with Wikipedia and Google Scholar info
    66	    test_data = {
    67	        'id': 'Q42',
    68	        'type': 'item',
    69	        'labels': {'en': 'Douglas Adams', 'fr': 'Douglas Adams', 'de': 'Douglas Adams'},
    70	        'descriptions': {'en': 'English writer', 'de': 'englischer Schriftsteller'},
    71	        'aliases': {},
    72	        'statements': {
    73	            'P1960': [  # Google Scholar ID
    74	                {'mainsnak': {'datavalue': {'value': 'test-scholar-id-123'}}},
    75	                {'mainsnak': {'datavalue': {'value': 'test-scholar-id-456'}}}  # Multiple values
    76	            ]
    77	        },
    78	        'sitelinks': {
    79	            'enwiki': {'title': 'Douglas_Adams', 'url': 'https://en.wikipedia.org/wiki/Douglas_Adams'},
    80	            'dewiki': {'title': 'Douglas_Adams', 'url': 'https://de.wikipedia.org/wiki/Douglas_Adams'},
    81	            'frwiki': {'title': 'Douglas_Adams'}  # No URL provided, should construct one
    82	        }
    83	    }
    84	    
    85	    from datetime import datetime
    86	    entity = WikidataEntity.from_dict(test_data, datetime.now())
    87	    
    88	    # Test _get_statement_values function
    89	    print("\nTesting _get_statement_values:")
    90	    scholar_ids = _get_statement_values(entity, 'P1960')
    91	    print(f"✓ Found Google Scholar IDs: {scholar_ids}")
    92	    empty_values = _get_statement_values(entity, 'P999999')  # Non-existent property
    93	    print(f"✓ Non-existent property returns empty list: {empty_values}")
    94	    
    95	    # Test _get_wikipedia_link function
    96	    print("\nTesting _get_wikipedia_link:")
    97	    en_result = _get_wikipedia_link(entity, 'en')
    98	    print(f"✓ English Wikipedia: {en_result}")
    99	    de_result = _get_wikipedia_link(entity, 'de') 
   100	    print(f"✓ German Wikipedia: {de_result}")
   101	    fr_result = _get_wikipedia_link(entity, 'fr')  # Should construct URL from title
   102	    print(f"✓ French Wikipedia (constructed): {fr_result}")
   103	    es_result = _get_wikipedia_link(entity, 'es')  # Should fallback to English
   104	    print(f"✓ Spanish Wikipedia (fallback to EN): {es_result}")
   105	    
   106	    # Test _get_wiki_profiles function
   107	    print("\nTesting _get_wiki_profiles:")
   108	    wiki_profiles_en = _get_wiki_profiles(entity, 'en')
   109	    print(f"✓ English wiki profiles: {len(wiki_profiles_en)} items")
   110	    for profile in wiki_profiles_en:
   111	        print(f"  - {profile['label']}: {profile['url']}")
   112	    
   113	    wiki_profiles_de = _get_wiki_profiles(entity, 'de')
   114	    print(f"✓ German wiki profiles: {len(wiki_profiles_de)} items")
   115	    for profile in wiki_profiles_de:
   116	        print(f"  - {profile['label']}: {profile['url']}")
   117	    
   118	    # Test get_external_profiles function (main function)
   119	    print("\nTesting get_external_profiles (main function):")
   120	    all_profiles_en = get_external_profiles(entity, 'en')
   121	    print(f"✓ All external profiles (EN): {len(all_profiles_en)} items")
   122	    for profile in all_profiles_en:
   123	        print(f"  - {profile['label']}: {profile['url']} (icon: {profile['icon_path']})")
   124	    
   125	    all_profiles_de = get_external_profiles(entity, 'de')
   126	    print(f"✓ All external profiles (DE): {len(all_profiles_de)} items")
   127	    for profile in all_profiles_de:
   128	        print(f"  - {profile['label']}: {profile['url']} (icon: {profile['icon_path']})")
   129	    
   130	    # Test with empty entity
   131	    print("\nTesting with empty entity:")
   132	    empty_profiles = get_external_profiles(None)
   133	    print(f"✓ Empty entity returns empty list: {empty_profiles}")
   134	    
   135	    print("\n✓ All tests passed!")
   136	
   137	if __name__ == "__main__":
   138	    test_existing_functionality()
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 57] [assistant]
Great! Now let me create a comprehensive test script to verify that all the new functionality works correctly:

[MSG 58] [user]
Observation: 













The file /app/test_wikidata_implementation.py has been edited. Here's the result of running `cat -n` on a snippet of /app/test_wikidata_implementation.py:
   132	    empty_profiles = get_external_profiles(None)
   133	    print(f"✓ Empty entity returns empty list: {empty_profiles}")
   134	    
   135	    print("\n✓ All tests passed!")
   136	
   137	if __name__ == "__main__":
   138	    test_existing_functionality()
   139	    test_new_functionality()
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 59] [user]
Observation: 

Testing existing WikidataEntity functionality:
- ID: Q42
- English description: English writer
- German description (should fallback to EN): englischer Schriftsteller
- Nonexistent language description (should fallback to EN): English writer

Testing newly implemented functionality:
✓ SOCIAL_PROFILE_CONFIGS found: [{'icon_name': 'google_scholar.svg', 'wikidata_property': 'P1960', 'label': 'Google Scholar', 'base_url': 'https://scholar.google.com/citations?user='}]
✓ All functions imported successfully

Testing _get_statement_values:
✓ Found Google Scholar IDs: ['test-scholar-id-123', 'test-scholar-id-456']
✓ Non-existent property returns empty list: []

Testing _get_wikipedia_link:
✓ English Wikipedia: ('https://en.wikipedia.org/wiki/Douglas_Adams', 'en')
✓ German Wikipedia: ('https://de.wikipedia.org/wiki/Douglas_Adams', 'de')
✓ French Wikipedia (constructed): ('https://fr.wikipedia.org/wiki/Douglas_Adams', 'fr')
✓ Spanish Wikipedia (fallback to EN): ('https://en.wikipedia.org/wiki/Douglas_Adams', 'en')

Testing _get_wiki_profiles:
✓ English wiki profiles: 2 items
  - Wikipedia: https://en.wikipedia.org/wiki/Douglas_Adams
  - Wikidata: https://www.wikidata.org/wiki/Q42
✓ German wiki profiles: 2 items
  - Wikipedia (in de): https://de.wikipedia.org/wiki/Douglas_Adams
  - Wikidata: https://www.wikidata.org/wiki/Q42

Testing get_external_profiles (main function):
✓ All external profiles (EN): 4 items
  - Wikipedia: https://en.wikipedia.org/wiki/Douglas_Adams (icon: /static/images/icons/wikipedia.svg)
  - Wikidata: https://www.wikidata.org/wiki/Q42 (icon: /static/images/icons/wikidata.svg)
  - Google Scholar: https://scholar.google.com/citations?user=test-scholar-id-123 (icon: /static/images/icons/google_scholar.svg)
  - Google Scholar: https://scholar.google.com/citations?user=test-scholar-id-456 (icon: /static/images/icons/google_scholar.svg)
✓ All external profiles (DE): 4 items
  - Wikipedia (in de): https://de.wikipedia.org/wiki/Douglas_Adams (icon: /static/images/icons/wikipedia.svg)
  - Wikidata: https://www.wikidata.org/wiki/Q42 (icon: /static/images/icons/wikidata.svg)
  - Google Scholar: https://scholar.google.com/citations?user=test-scholar-id-123 (icon: /static/images/icons/google_scholar.svg)
  - Google Scholar: https://scholar.google.com/citations?user=test-scholar-id-456 (icon: /static/images/icons/google_scholar.svg)

Testing with empty entity:
✓ Empty entity returns empty list: []

✓ All tests passed!






[MSG 60] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/templates/authors/infobox.html:
     1	$def with (page, edit_view: bool = False, imagesId=0)
     2	
     3	$ is_librarian = ctx.user and (ctx.user.is_librarian() or ctx.user.is_super_librarian() or ctx.user.is_admin())
     4	
     5	$if edit_view:
     6	    $ wikidata = page.wikidata(bust_cache=True, fetch_missing=True)
     7	$else:
     8	    $ wikidata = page.wikidata(fetch_missing=is_librarian)
     9	
    10	$def render_infobox_row(label, itemprop, value):
    11	    $if value:
    12	        <tr>
    13	            <td><strong>$label</strong></td>
    14	            <td><span itemprop="$itemprop">$value</span></td>
    15	        </tr>
    16	
    17	<div class="infobox">
    18	    <div class="illustration">
    19	        $:render_template("covers/author_photo", page)
    20	        $:render_template("covers/change", page, ".bookCover img", imagesId)
    21	    </div>
    22	    <p class="short-description">
    23	        $if wikidata:
    24	            $wikidata.get_description(i18n.get_locale())
    25	    </p>
    26	    <table>
    27	        $if page.birth_date or page.death_date:
    28	            $:render_infobox_row(_("Born"), 'birthDate', page.birth_date)
    29	            $:render_infobox_row(_("Died"), 'deathDate', page.death_date)
    30	        $elif page.date:
    31	                $:render_infobox_row(_("Date"), '', page.date)
    32	    </table>
    33	</div>
    34	







[MSG 61] [assistant]
Excellent! The wikidata functionality is working correctly. Now I need to integrate this with the author infobox template. Let me modify the infobox template to display these external profiles:

[MSG 62] [user]
Observation: 

/app/openlibrary/macros/WorkInfo.html:$ cur_locale = i18n.get_locale()
/app/openlibrary/templates/authors/infobox.html:            $wikidata.get_description(i18n.get_locale())






[MSG 63] [assistant]
I need to modify the infobox template to add the external profiles. First, let me check if there's access to the i18n module to get the locale:

[MSG 64] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **ALL AGENTS FAIL** (14 runs, 0 pass) — strong contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CONFIRMED_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 20:56:33

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | test_coupling |
| Confidence | 0.9 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent identified that Wikidata support was stubbed out, re-enabled `Author.wikidata`, added logic for Wikipedia fallback and external profile extraction, and started wiring icons/template support. Its implementation used standalone helper functions and a different output/icon schema, then it timed out before finishing or submitting a patch.

**Contamination evidence**: The F2P tests assert on specific internal helper methods and exact output structure not stated in the problem: they require private methods named `_get_wikipedia_link` and `_get_statement_values` to exist on `WikidataEntity`, require a public method named `get_external_profiles` on that class, and require each profile dict to use exact keys/values like `icon_url` with hard-coded paths such as `/static/images/identifier_icons/google_scholar.svg`, plus exact labels like `Wikipedia` and `Wikidata`. The problem statement only specifies behavior (language-aware Wikipedia fallback, extraction of external identifiers, structured profile list), not these internal method names, class placement, dict schema, or asset paths. A behaviorally correct implementation using free functions, different helper names, different dict keys, or different icon locations would still fail these tests.

**Difficulty evidence**: None

**Full reasoning**: The agent did understand the feature request: it found that `Author.wikidata()` was effectively disabled, recognized the need for language-aware Wikipedia lookup and external identifier parsing, and implemented much of that logic. However, it timed out before submitting a patch, and its draft implementation also diverged from the repository's expected structure. More importantly, the test patch itself is strongly contaminated. Rather than validating only the user-visible behavior described in the problem statement, the tests lock onto gold-patch internals: exact helper method names on `WikidataEntity` (including private `_get_*` methods), exact profile dict keys, and exact static asset paths. None of those implementation details are derivable from the prompt. So although this specific agent failed by timeout, the benchmark task is still severely contaminated because a correct solution to the stated problem could be rejected unless it mirrors the gold patch's internal API and data shape.
