# Case #92 Re-Audit Notes (v2)

**Instance**: `instance_internetarchive__openlibrary-d109cc7e6e161170391f98f9a6fa1d02534c18e4-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

## Title: Add ability to annotate individual list seeds with public notes 

## Description: 
When users create a list in Open Library, they currently cannot add notes to individual items (seeds) in the list. The only available annotation is a single global description that applies to the entire list. This limitation makes it difficult to provide context, comments, or explanations for specific list items. 

## Current Behavior: 
Users can add a general description to a list, but cannot attach ite...

**Type**: python | **Repo**: internetarchive/openlibrary
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 10 |
| Gold patch files | 10 |
| Gold patch size | 38928 chars |
| Test patch size | 1397 chars |
| Test patch files | 1 |
| F2P tests | 2 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
openlibrary/tests/core/test_lists_model.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard daf93507208f2206f8950e3bb5fffac7caf80520
git clean -fd 
git checkout daf93507208f2206f8950e3bb5fffac7caf80520 
git checkout d109cc7e6e161170391f98f9a6fa1d02534c18e4 -- openlibrary/tests/core/test_lists_model.py
```

## 3. Trajectory Evidence

### Resolution Rate: 3/13 (23%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 46 |
| Claude Sonnet 4 - paper | FAIL | 20 |
| Gemini 2.5 Pro Preview - paper | FAIL | 66 |
| GPT-4o - paper | FAIL | 29 |
| GPT-5 High - paper | FAIL | 51 |
| GPT OSS - paper | FAIL | 18 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | PASS | 129 |
| GPT-5 - 10132025 | FAIL | 74 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 68 |
| GPT-5 Codex -- debug-oct22 | FAIL | 195 |
| GLM-4.5 -- 10222025 | PASS | 103 |
| Claude 4.5 Haiku -- 10222025 | PASS | 95 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 81
- **Total tokens**: ~27344
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
/app/stories
/app/stories/README.md
/app/stories/Introduction.mdx
/app/stories/Button.stories.js
/app/docker
/app/docker/ol-covers-start.sh
/app/docker/Dockerfile.olbase
/app/docker/ol-solr-updater-start.sh
/app/docker/ol-nginx-start.sh
/app/docker/ol-home-start.sh
/app/docker/nginx.conf
/app/docker/ol-db-init.sh
/app/docker/ol-importbot-start.sh
/app/docker/ol-cron-start.sh
/app/docker/infobase_nginx.conf
/app/docker/ol-infobase-start.sh
/app/docker/ol-affiliate-server-start.sh
/app/docker/web_nginx.conf
/app/docker/public_nginx.conf
/app/docker/README.md
/app/docker/covers_nginx.conf
/app/docker/Dockerfile.oldev
/app/docker/ol-web-start.sh
/app/LICENSE
/app/vue.config.js
/app/compose.override.yaml
/app/infogami
/app/compose.yaml
/app/compose.staging.yaml
/app/Readme_chinese.md
/app/Readme.md
/app/SECURITY.md
/app/webpack.config.js
/app/requirements_test.txt
/app/scripts
/app/scripts/import_open_textbook_library.py
/app/scripts/fake_loan_server.py
/app/scripts/oldump.py
/app/scripts/lc_marc_update.py
/app/scripts/update_stale_work_references.py
/app/scripts/pull-templates.py
/app/scripts/import_pressbooks.py
/app/scripts/providers
/app/scripts/infobase-server
/app/scripts/install_openresty.sh
/app/scripts/affiliate_server.py
/app/scripts/update-loans.py
/app/scripts/deployment
/app/scripts/tests
/app/scripts/cron_watcher.py
/app/scripts/test_py3.sh
/app/scripts/Readme.txt
/app/scripts/dev-instance
/app/scripts/mail_bad_author_query.py
/app/scripts/get_web_error.py
/app/scripts/pr_slack_digest.py
/app/scripts/oldump.sh
/app/scripts/oclc_to_marc.py
/app/scripts/upstream-adapter
/app/scripts/delete_import_items.py
/app/scripts/dump-reading-log.sql
/app/scripts/__pycache__
/app/scripts/promise_batch_imports.py
/app/scripts/solr_updater.py
/app/scripts/coverstore-server
/app/scripts/run_doctests.sh
/app/scripts/manage-imports.py
/app/scripts/setup_olserver.sh
/app/scripts/openlibrary-server
/app/scripts/solr_dump_xisbn.py
/app/scripts/import_standard_ebooks.py
/app/scripts/start-solr.sh
/app/scripts/sitemaps
/app/scripts/sponsor_update_prices.py
/app/scripts/setup_gitpod.sh
/app/scripts/migrate_db.py
/app/scripts/__init__.py
/app/scripts/generate-api-docs.py
/app/scripts/install_nodejs.sh
/app/scripts/expire_accounts.py
/app/scripts/i18n-messages
/app/scripts/make-integration-branch-sample.txt
/app/scripts/run_olserver.sh
/app/scripts/partner_batch_imports.py
/app/scripts/solr_builder
/app/scripts/_init_path.py
/app/scripts/solr_restarter
/app/scripts/dump-ratings.sql
/app/scripts/make-integration-branch.sh
/app/scripts/copydocs.py
/app/scripts/store_counts.py
/app/static
/app/static/images
/app/static/css
/app/static/offline.html
/app/static/openapi.json
/app/static/favicon.ico
/app/static/coverstore-robots.txt
/app/static/status-500.html
/app/static/opensearch.xml
/app/static/logos
/app/static/manifest.json
/app/static/robots.txt
/app/static/fonts
/app/static/norobots.txt
/app/CONTRIBUTING.md
/app/config
/app/openlibrary
/app/openlibrary/accounts
/app/openlibrary/catalog
/app/openlibrary/components
/app/openlibrary/config.py
/app/openlibrary/core
/app/openlibrary/code.py
/app/openlibrary/conftest.py
/app/openlibrary/admin
/app/openlibrary/coverstore
/app/openlibrary/data
/app/openlibrary/records
/app/openlibrary/utils
/app/openlibrary/plugins
/app/openlibrary/solr
/app/openlibrary/actions.py
/app/openlibrary/__init__.py
/app/openlibrary/__pycache__
/app/openlibrary/tests
/app/openlibrary/views
/app/openlibrary/olbase
/app/openlibrary/api.py
/app/openlibrary/mocks
/app/openlibrary/macros
/app/openlibrary/i18n
/app/openlibrary/book_providers.py
/app/openlibrary/app.py
/app/openlibrary/templates
/app/CODE_OF_CONDUCT.md
/app/pyproject.toml
/app/Makefile
/app/bundlesize.config.json
/app/vendor
/app/vendor/js
/app/vendor/infogami
/app/conf
/app/conf/openlibrary.yml
/app/conf/logging.ini
/app/conf/twa
/app/conf/infobase.yml
/app/conf/svgo.config.js
/app/conf/email.ini
/app/conf/solr
/app/conf/coverstore.yml
/app/requirements.txt
/app/setup.py
/app/package.json
/app/renovate.json
/app/package-lock.json
/app/compose.production.yaml
/app/tests
/app/tests/integration
/app/tests/unit
/app/tests/screenshots
/app/tests/test_docker_compose.py
/app/compose.infogami-local.yaml








[MSG 1] [assistant]
I'll help you implement the necessary changes to support annotating individual list seeds with public notes. Let's start by exploring the repository structure and understanding the current implementation.

[MSG 2] [user]
Observation: 

/app/openlibrary/core/lists/engine.py
/app/openlibrary/core/lists/model.py
/app/openlibrary/core/lists/__init__.py
/app/openlibrary/core/waitinglist.py
/app/openlibrary/plugins/openlibrary/tests/test_listapi.py
/app/openlibrary/plugins/openlibrary/tests/test_lists.py
/app/openlibrary/plugins/openlibrary/lists.py
/app/openlibrary/solr/updater/list.py
/app/openlibrary/tests/core/test_lists_engine.py
/app/openlibrary/tests/core/lists/test_model.py
/app/openlibrary/tests/core/test_waitinglist.py
/app/openlibrary/tests/core/test_lists_model.py






[MSG 3] [assistant]
Now let's look at the list-related code. Based on the PR description, I need to focus on files related to lists functionality:

[MSG 4] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app/openlibrary/core/lists, excluding hidden items:
/app/openlibrary/core/lists
/app/openlibrary/core/lists/engine.py
/app/openlibrary/core/lists/model.py
/app/openlibrary/core/lists/__init__.py








[MSG 5] [assistant]
Great! Let's examine the main lists implementation files:

[MSG 6] [user]
Observation: 

<NOTE>This file is too large to display entirely. Showing abbreviated version. Please use `str_replace_editor view` with the `view_range` parameter to show selected lines next.</NOTE>
     1 """Helper functions used by the List model.
     2 """
     3 from functools import cached_property
     4 from typing import TypedDict, cast
     5 
     6 import web
     7 import logging
     8 
     9 from infogami import config
    10 from infogami.infobase import client, common
    11 from infogami.utils import stats
    12 
    13 from openlibrary.core import helpers as h
    14 from openlibrary.core import cache
    15 from openlibrary.core.models import Image, Subject, Thing, ThingKey
    16 from openlibrary.plugins.upstream.models import Author, Changeset, Edition, User, Work
    17 
    18 from openlibrary.plugins.worksearch.search import get_solr
    19 from openlibrary.plugins.worksearch.subjects import get_subject
    20 import contextlib
    21 
    22 logger = logging.getLogger("openlibrary.lists.model")
    23 
    24 
    25 class SeedDict(TypedDict):
    26     key: ThingKey
    27 
    28 
    29 SeedSubjectString = str
    30 """
    31 When a subject is added to a list, it's added as a string like:
    32 - "subject:foo"
    33 - "person:floyd_heywood"
    34 """
    35 
    36 
    37 class List(Thing):
    38     """Class to represent /type/list objects in OL.
    39 
    40     List contains the following properties, theoretically:
    41         * cover - id of the book cover. Picked from one of its editions.
    42         * tags - list of tags to describe this list.
    43     """
    44 
    45     name: str | None
    46     """Name of the list"""
    47 
    48     description: str | None
    49     """Detailed description of the list (markdown)"""
    50 
    51     seeds: list[Thing | SeedSubjectString]
    52     """Members of the list. Either references or subject strings."""
    53 
    54     def url(self, suffix="", **params):
    55         return self.get_url(suffix, **params)
    56 
    57     def get_url_suffix(self):
    58         return self.name or "unnamed"
    59 
    60     def get_owner(self) -> User | None:
    61         if match := web.re_compile(r"(/people/[^/]+)/lists/OL\d+L").match(self.key):
    
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
   return subject_key_to_seed(seed['key'])
    78	                else:
    79	                    return seed
    80	
    81	    @staticmethod
    82	    def from_input():
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 68] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/plugins/openlibrary/lists.py:
    81	    @staticmethod
    82	    def from_input():
    83	        DEFAULTS = {
    84	            'key': None,
    85	            'name': '',
    86	            'description': '',
    87	            'seeds': [],
    88	        }
    89	        if data := web.data():
    90	            # If the requests has data, parse it and use it to populate the list
    91	            if web.ctx.env.get('CONTENT_TYPE') == 'application/json':
    92	                i = {} | DEFAULTS | json.loads(data)
    93	            else:
    94	                form_data = {
    95	                    # By default all the values are lists
    96	                    k: v[0]
    97	                    for k, v in parse_qs(bytes.decode(data)).items()
    98	                }
    99	                i = {} | DEFAULTS | utils.unflatten(form_data)
   100	        else:
   101	            # Otherwise read from the query string
   102	            i = utils.unflatten(web.input(**DEFAULTS))
   103	
   104	        normalized_seeds = [
   105	            ListRecord.normalize_input_seed(seed)
   106	            for seed_list in i['seeds']
   107	            for seed in (
   108	                seed_list.split(',') if isinstance(seed_list, str) else [seed_list]
   109	            )
   110	        ]
   111	        normalized_seeds = [
   112	            seed
   113	            for seed in normalized_seeds
   114	            if seed and (isinstance(seed, str) or seed.get('key'))
   115	        ]
   116	        return ListRecord(
   117	            key=i['key'],
   118	            name=i['name'],
   119	            description=i['description'],
   120	            seeds=normalized_seeds,
   121	        )
   122	
   123	    def to_thing_json(self):
   124	        return {
   125	            "key": self.key,
   126	            "type": {"key": "/type/list"},
   127	            "name": self.name,
   128	            "description": self.description,
   129	            "seeds": self.seeds,
   130	        }







[MSG 69] [assistant]
Now I need to update the from_input method to handle annotated seeds from form data. Let me examine the current implementation:

[MSG 70] [user]
Observation: 

























The file /app/openlibrary/plugins/openlibrary/lists.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/openlibrary/lists.py:
   106	            for seed_list in i['seeds']
   107	            for seed in (
   108	                seed_list.split(',') if isinstance(seed_list, str) else [seed_list]
   109	            )
   110	        ]
   111	        normalized_seeds = [
   112	            seed
   113	            for seed in normalized_seeds
   114	            if seed and (
   115	                isinstance(seed, str) 
   116	                or seed.get('key')  # ThingReferenceDict
   117	                or ('thing' in seed and seed['thing'].get('key'))  # AnnotatedSeedDict
   118	            )
   119	        ]
   120	        return ListRecord(
   121	            key=i['key'],
   122	            name=i['name'],
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 71] [assistant]
I need to update the filtering condition in the from_input method to handle annotated seeds:

[MSG 72] [user]
Observation: 























































































































































The file /app/openlibrary/templates/type/list/edit.html has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/templates/type/list/edit.html:
    16	        <b class="warning">
    17	            $_("⚠️ Saving global lists is admin-only while the feature is under development.")
    18	        </b>
    19	</div>
    20	
    21	$# Render the ith seed input field
    22	$jsdef render_seed_field(i, seed):
    23	    <li class="mia__input ac-input">
    24	        <div class="seed--controls">
    25	            <div class="mia__reorder mia__index">≡ #$(i + 1)</div>
    26	            <button class="mia__remove" type="button">Remove</button>
    27	        </div>
    28	        <main>
    29	            $ # Determine seed key and notes from either format
    30	            $ seed_key = seed.get('thing', {}).get('key', '') if 'thing' in seed else seed.get('key', '')
    31	            $ seed_notes = seed.get('notes', '')
    32	            
    33	            <input class="ac-input__value" name="seeds--$i--key" type="hidden" value="$seed_key" />
    34	            $# Displayed
    35	            <input
    36	                class="ac-input__visible"
    37	                value="$seed_key.split('/')[-1]"
    38	                placeholder="$_('Search for a book')"
    39	                $if seed_key:
    40	                    type="hidden"
    41	            />
    42	            <div class="ac-input__preview">
    43	                $# Note: Cannot use "in" because this is a jsdef function
    44	                $if seed_key:
    45	                    $ prefix = seed_key.split('/')[1]
    46	                    $if prefix == 'works' or prefix == 'books':
    47	                        $:lazy_thing_preview(seed_key, 'render_lazy_work_preview')
    48	                    $elif prefix == 'authors':
    49	                        $:lazy_thing_preview(seed_key, 'render_lazy_author_preview')
    50	                    $else:
    51	                        $seed_key
    52	                $else:
    53	                    $seed_key
    54	            </div>
    55	            $# Notes field
    56	            <div class="seed-notes">
    57	                <textarea 
    58	                    class="seed-notes__textarea"
    59	                    name="seeds--$i--notes"
    60	                    placeholder="$_('Optional notes for this item...')"
    61	                    rows="2" 
    62	                    cols="50">$seed_notes</textarea>
    63	            </div>
    64	        </main>
    65	    </li>
    66	
    67	$# import the side-effect of the jsdef function
    68	$:render_template('jsdef/LazyWorkPreview', None)
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 73] [assistant]
Now I need to update the templates to support notes in the editing interface. Let me update the edit.html template:

[MSG 74] [user]
Observation: 































































The file /app/openlibrary/templates/type/list/edit.html has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/templates/type/list/edit.html:
   123	            >$lst.description</textarea>
   124	        </div>
   125	
   126	        <hr />
   127	
   128	        <ol class="list-edit__items multi-input-autocomplete--seeds">
   129	            $if lst.seeds:
   130	                $for i, seed in enumerate(lst.seeds):
   131	                    $ # Convert seeds to template-friendly format
   132	                    $if isinstance(seed, str):
   133	                        $ template_seed = {'key': '/subjects/' + seed, 'notes': ''}
   134	                    $elif hasattr(seed, 'to_db'):
   135	                        $ # AnnotatedSeedThing - convert to template format
   136	                        $ db_seed = seed.to_db()
   137	                        $if isinstance(db_seed, str):
   138	                            $ template_seed = {'key': '/subjects/' + db_seed, 'notes': ''}
   139	                        $elif 'thing' in db_seed:
   140	                            $ template_seed = {'thing': db_seed['thing'], 'notes': db_seed.get('notes', '')}
   141	                        $else:
   142	                            $ template_seed = {'key': db_seed['key'], 'notes': ''}
   143	                    $else:
   144	                        $ # Regular Thing object
   145	                        $ template_seed = {'key': seed.key, 'notes': ''}
   146	                    $:render_seed_field(i, template_seed)
   147	            $else:
   148	                $:render_seed_field(0, {'key': '', 'notes': ''})
   149	            <a href="javascript:;" class="mia__add">$_('Add another book')</a>
   150	        </ol>
   151	
   152	        <hr />
   153	
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 75] [assistant]
Now I need to also fix the seed rendering logic in the edit template. The current code assumes seeds are always dictionaries with 'key', but now they might be strings or have different structures:

[MSG 76] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/templates/type/list/view_body.html:
   120	                $ cover_url = default_image
   121	
   122	            $if seed.type in ['edition', 'work']:
   123	                $ use_my_books_droppers = 'my_books_dropper' in ctx.features
   124	                $ doc = solr_works.get(seed.key) or seed.document
   125	                $:macros.SearchResultsWork(doc, attrs=seed_attrs(seed), availability=availabilities.get(seed.key), decorations=remove_item_link(), extra=seed_meta_line(seed), include_dropper=use_my_books_droppers)
   126	            $else:
   127	                <li class="searchResultItem" $:seed_attrs(seed)>
   128	                    <span class="bookcover">
   129	                        <a href="$seed.url">
   130	                        <img src="$cover_url" alt="$seed.title"/>
   131	                        </a>
   132	                    </span>
   133	                    <div class="details">
   134	                        <div class="resultTitle">
   135	                            <h3 class="booktitle">
   136	                                <a href="$seed.url" class="results">$seed.title</a>
   137	                            </h3>
   138	                            $:seed_meta_line(seed)
   139	                        </div>
   140	                    </div>
   141	                    <span class="searchResultItemCTA">
   142	                        $:remove_item_link()
   143	                    </span>
   144	                </li>
   145	        </ul>
   146	    </div>
   147	
   148	    <div class="contentOnethird" style="margin-bottom:0;">
   149	
   150	        $:render_template("type/list/exports", list)







[MSG 77] [assistant]
Now I need to update the view template to show the notes. Let me update the view_body.html template:

[MSG 78] [user]
Observation: 

Here's the result of running `cat -n` on /app/openlibrary/templates/type/list/view_body.html:
    63	$def seed_meta_line(seed):
    64	    <span class="meta">
    65	        <!-- FIXME: I18N using internal seed.type directly for display is not internationalizable -->
    66	        <span class="type small">$seed.type</span>
    67	    </span>
    68	
    69	    $if sort == 'last_modified' and seed.last_update:
    70	        <span class="time">
    71	            $:_('Last modified <span>%(date)s</span>', date=datestr(seed.last_update))
    72	        </span>
    73	
    74	$def seed_attrs(seed):
    75	    data-seed-key="$seed.key"
    76	    data-list-key="$list.key"
    77	
    78	<div id="contentBody">
    79	    <div id="remove-seed-dialog" class="hidden" title="$_('Remove seed')">$_('Are you sure you want to remove this item from the list?')</div>
    80	    <div id="delete-list-dialog" class="hidden" title="$_('Remove Seed')">







[MSG 79] [assistant]
Let me look for where the seed display code is and add notes display:

[MSG 80] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **LOW RESOLUTION** (3/13 = 23%) — moderate contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CONFIRMED_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 20:51:05

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | test_coupling |
| Confidence | 0.97 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent correctly identified this as an end-to-end list-seed annotation feature and started modifying the list model, seed normalization, and list edit/view templates to support per-seed notes. It explored the relevant codepaths thoroughly but never converged to a finished patch before autosubmission.

**Contamination evidence**: The visible F2P tests do not check the user-facing feature from the prompt (editing/rendering public Markdown notes on list items). Instead they lock in exact internals from the gold refactor: they import a renamed internal type alias `ThingReferenceDict`, require a new factory `Seed.from_json(...)`, and assert the peculiar internal behavior that `hasattr(seed, "type") is False` for a seed created from a key dict. None of these API names or behaviors are stated or implied by the problem statement. A reasonable implementation of per-item notes could keep `Seed.__init__` handling dicts directly, use different helper names, or eagerly assign a type, and would still satisfy the product spec while failing these tests.

**Difficulty evidence**: None

**Full reasoning**: This task shows strong contamination. The problem statement is purely about product behavior: allow optional public Markdown notes on Thing seeds in lists, render them safely in list views, edit them from the list editing page, and leave subject-string seeds unchanged. The agent understood that scope and began implementing exactly those capabilities across the model and templates. However, the F2P tests shown are not validating that behavior. They validate specific implementation details of the gold patch's internal refactor in `openlibrary.core.lists.model`: a renamed TypedDict (`ThingReferenceDict`), a new `Seed.from_json` constructor, and even the exact lazy/unresolved-object behavior where `seed.type` is absent for a seed built from a plain key dict. Those are classic test-coupling signals. An agent could solve the stated feature correctly with a different but equally valid design and still fail these tests. The agent's actual run ended in a timeout, but independent inspection of the tests makes the benchmark issue clear: the tests are coupled to gold-patch internals rather than the spec.
