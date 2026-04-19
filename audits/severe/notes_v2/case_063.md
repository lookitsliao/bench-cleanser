# Case #63 Re-Audit Notes (v2)

**Instance**: `instance_internetarchive__openlibrary-8a9d9d323dfcf2a5b4f38d70b1108b030b20ebf3-v13642507b4fc1f8d234172bf8129942da2c2ca26`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

# Support importing staged ISBNdb data dumps via CLI 

# Description: 
There is currently no mechanism to ingest ISBN metadata from locally staged ISBNdb ‘.jsonl’ dumps into the OpenLibrary import system. This prevents users or developers from testing or processing ISBNdb-provided records using the ‘manage_imports.py’ pipeline. While the system includes infrastructure for running imports via Docker Compose, the ingestion pathway for raw ISBNdb batches is missing integration support in the import...

**Type**: python | **Repo**: internetarchive/openlibrary
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 3 |
| Gold patch files | 3 |
| Gold patch size | 14302 chars |
| Test patch size | 2823 chars |
| Test patch files | 1 |
| F2P tests | 16 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
scripts/tests/test_isbndb.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 9db365285453fb388757aa65ae06226e7c0f64cf
git clean -fd 
git checkout 9db365285453fb388757aa65ae06226e7c0f64cf 
git checkout 8a9d9d323dfcf2a5b4f38d70b1108b030b20ebf3 -- scripts/tests/test_isbndb.py
```

## 3. Trajectory Evidence

### Resolution Rate: 0/13 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 37 |
| Claude Sonnet 4 - paper | FAIL | 17 |
| Gemini 2.5 Pro Preview - paper | FAIL | 46 |
| GPT-4o - paper | FAIL | 18 |
| GPT-5 High - paper | FAIL | 26 |
| GPT OSS - paper | FAIL | 48 |
| Kimi - paper | FAIL | 40 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 64 |
| GPT-5 - 10132025 | FAIL | 32 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 14 |
| GPT-5 Codex -- debug-oct22 | FAIL | 35 |
| GLM-4.5 -- 10222025 | FAIL | 42 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 54 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 66
- **Total tokens**: ~31347
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
/app/compose.production.yaml
/app/compose.override.yaml
/app/compose.staging.yaml
/app/tests
/app/tests/screenshots
/app/tests/unit
/app/tests/test_docker_compose.py
/app/tests/integration
/app/CODE_OF_CONDUCT.md
/app/renovate.json
/app/package-lock.json
/app/package.json
/app/scripts
/app/scripts/oldump.py
/app/scripts/solr_builder
/app/scripts/dump-reading-log.sql
/app/scripts/generate-api-docs.py
/app/scripts/run_olserver.sh
/app/scripts/migrate_db.py
/app/scripts/oldump.sh
/app/scripts/solr_dump_xisbn.py
/app/scripts/upstream-adapter
/app/scripts/manage_imports.py
/app/scripts/solr_restarter
/app/scripts/i18n-messages
/app/scripts/tests
/app/scripts/infobase-server
/app/scripts/delete_import_items.py
/app/scripts/make-integration-branch.sh
/app/scripts/promise_batch_imports.py
/app/scripts/__init__.py
/app/scripts/setup_gitpod.sh
/app/scripts/mail_bad_author_query.py
/app/scripts/oclc_to_marc.py
/app/scripts/lc_marc_update.py
/app/scripts/solr_updater.py
/app/scripts/openlibrary-server
/app/scripts/setup_olserver.sh
/app/scripts/run_doctests.sh
/app/scripts/dev-instance
/app/scripts/test_py3.sh
/app/scripts/providers
/app/scripts/partner_batch_imports.py
/app/scripts/import_pressbooks.py
/app/scripts/install_nodejs.sh
/app/scripts/sponsor_update_prices.py
/app/scripts/cron_watcher.py
/app/scripts/get_web_error.py
/app/scripts/__pycache__
/app/scripts/deployment
/app/scripts/make-integration-branch-sample.txt
/app/scripts/install_openresty.sh
/app/scripts/fake_loan_server.py
/app/scripts/update-loans.py
/app/scripts/store_counts.py
/app/scripts/coverstore-server
/app/scripts/copydocs.py
/app/scripts/pull-templates.py
/app/scripts/pr_slack_digest.py
/app/scripts/affiliate_server.py
/app/scripts/_init_path.py
/app/scripts/dump-ratings.sql
/app/scripts/update_stale_work_references.py
/app/scripts/sitemaps
/app/scripts/import_standard_ebooks.py
/app/scripts/expire_accounts.py
/app/scripts/Readme.txt
/app/scripts/start-solr.sh
/app/bundlesize.config.json
/app/compose.yaml
/app/requirements.txt
/app/conf
/app/conf/install.ini
/app/conf/bashrc
/app/conf/infobase.yml
/app/conf/nginx
/app/conf/svgo.config.js
/app/conf/email.ini
/app/conf/services.ini
/app/conf/crontab
/app/conf/coverstore.yml
/app/conf/twa
/app/conf/openlibrary.yml
/app/conf/solr
/app/conf/logging.ini
/app/static
/app/static/favicon.ico
/app/static/fonts
/app/static/build
/app/static/coverstore-robots.txt
/app/static/manifest.json
/app/static/robots.txt
/app/static/norobots.txt
/app/static/css
/app/static/images
/app/static/opensearch.xml
/app/static/openapi.json
/app/static/status-500.html
/app/static/offline.html
/app/static/logos
/app/openlibrary
/app/openlibrary/utils
/app/openlibrary/plugins
/app/openlibrary/views
/app/openlibrary/i18n
/app/openlibrary/admin
/app/openlibrary/actions.py
/app/openlibrary/__pycache__
/app/openlibrary/api.py
/app/openlibrary/mocks
/app/openlibrary/book_providers.py
/app/openlibrary/macros
/app/openlibrary/records
/app/openlibrary/catalog
/app/openlibrary/core
/app/openlibrary/data
/app/openlibrary/tests
/app/openlibrary/solr
/app/openlibrary/app.py
/app/openlibrary/config.py
/app/openlibrary/code.py
/app/openlibrary/components
/app/openlibrary/accounts
/app/openlibrary/conftest.py
/app/openlibrary/coverstore
/app/openlibrary/templates
/app/openlibrary/__init__.py
/app/openlibrary/olbase
/app/pyproject.toml
/app/CONTRIBUTING.md
/app/webpack.config.js
/app/SECURITY.md
/app/requirements_test.txt
/app/infogami
/app/Makefile
/app/compose.infogami-local.yaml
/app/setup.py
/app/config
/app/node_modules
/app/node_modules/babel-core
/app/node_modules/compression
/app/node_modules/obuf
/app/node_modules/get-caller-file
/app/node_modules/has-symbols
/app/node_modules/use-callback-ref
/app/node_modules/fswin
/app/node_modules/ini
/app/node_modules/stream-shift
/app/node_modules/onetime
/app/node_modules/css-minimizer-webpack-plugin
/app/node_modules/html-minifier-terser
/app/node_modules/is-electron
/app/node_modules/decompress
/app/node_modules/memoizerific
/app/node_modules/slick-carousel
/app/node_modules/webpack-merge
/app/node_modules/duplexer
/app/node_modules/@sinclair
/app/node_modules/bser
/app/node_modules/fetch-retry
/app/node_modules/agent-base
/app/node_modules/collection-visit
/app/node_modules/csso
/app/node_modules/@apollographql
/app/node_modules/unist-util-is
/app/node_modules/prepend-http
/app/node_modules/jest-config
/app/node_modules/cli-highlight
/app/node_modules/repeat-string
/app/node_modules/jest-docblock
/app/node_modules/define-property
/app/node_modules/pretty-error
/app/node_modules/yauzl
/app/node_modules/restore-cursor
/app/node_modules/postcss-normalize-whitespace
/app/node_modules/eslint
/app/node_modules/is-number
/app/node_modules/object.pick
/app/node_modules/foreground-child
/app/node_modules/at-least-node
/app/node_modules/object-is
/app/node_modules/arr-union
/app/node_modules/merge-source-map
/app/node_modules/dequal
/app/node_modules/color-name
/app/node_modules/postcss-unique-selectors
/app/node_modules/colors
/app/node_modules/dom-converter
/app/node_modules/has-yarn
/app/node_modules/react-inspector
/app/node_modules/postcss-reduce-transforms
/app/node_modules/range-parser
/app/node_modules/har-schema
/app/node_modules/fs-extra
/app/node_modules/raw-body
/app/node_modules/ora
/app/node_modules/quick-lru
/app/node_modules/strip-comments
/app/node_modules/doctrine
/app/node_modules/faye-websocket
/app/node_modules/js-tokens
/app/node_modules/colorette
/app/node_modules/send
/app/node_modules/fs-monkey
/app/node_modules/details-polyfill
/app/node_modules/source-list-map
/app/node_modules/istanbul-lib-report
/app/node_modules/get-value
/app/node_modules/postcss-discard-duplicates
/app/node_modules/braces
/app/node_modules/dashdash
/app/node_modules/strip-final-newline
/app/node_modules/is-plain-obj
/app/node_modules/@aw-web-design
/app/node_modules/loglevel
/app/node_modules/pirates
/app/node_modules/yargs-parser
/app/node_modules/regenerator-runtime
/app/node_modules/workbox-strategies
/app/node_modules/esbuild-register
/app/node_modules/tar
/app/node_modules/source-map-support
/app/node_modules/dns-equal
/app/node_modules/get-pixels
/app/node_modules/thenify
/app/node_modules/postcss-normalize-display-values
/app/node_modules/call-bind
/app/node_modules/jest-watcher
/app/node_modules/pstree.remy
/app/node_modules/bundlesize2
/app/node_modules/node-int64
/app/node_modules/tweetnacl
/app/node_modules/parse-json
/app/node_modules/default-browser-id
/app/node_modules/webidl-conversions
/app/node_modules/less-plugin-clean-css
/app/node_modules/pascal-case
/app/node_modules/workbox-recipes
/app/node_modules/postcss-normalize-url
/app/node_modules/http-errors
/app/node_modules/extract-zip
/app/node_modules/escalade
/app/node_modules/node-fetch-native
/app/node_modules/websocket-driver
/app/node_modules/postcss-minify-gradients
/app/node_modules/inflight
/app/node_modules/steno
/app/node_modules/indent-string
/app/node_modules/lodash
/app/node_modules/@eslint-community
/app/node_modules/git-config-path
/app/node_modules/snapdragon-util
/app/node_modules/@josephg
/app/node_modules/lru-cache
/app/node_modules/colord
/app/node_modules/amdefine
/app/node_modules/is-docker
/app/node_modules/emittery
/app/node_modules/@ampproject
/app/node_modules/jest-changed-files
/app/node_modules/hard-rejection
/app/node_modules/esbuild-plugin-alias
/app/node_modules/word-wrap
/app/node_modules/temp-dir
/app/node_modules/workbox-navigation-preload
/app/node_modules/style-search
/app/node_modules/@sideway
/app/node_modules/arrify
/app/node_modules/moment
/app/node_modules/utils-merge
/app/node_modules/has-to-string-tag-x
/app/node_modules/vue-style-loader
/app/node_modules/cli-cursor
/app/node_modules/execa
/app/node_modules/babel-plugin-jest-hoist
/app/node_modules/function-bind
/app/node_modules/on-finished
/ap
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
already available:

[MSG 52] [user]
Observation: 

/app/scripts/import_pressbooks.py
/app/scripts/import_standard_ebooks.py
/app/openlibrary/plugins/openlibrary/opds.py
/app/openlibrary/plugins/importapi/code.py
/app/openlibrary/plugins/importapi/tests/test_code.py
grep: write error: Broken pipe
grep: write error: Broken pipe
grep: write error: Broken pipe
grep: write error: Broken pipe
grep: write error: Broken pipe






[MSG 53] [user]
Observation: 

/app/scripts/import_standard_ebooks.py:        "languages": [marc_lang_code],






[MSG 54] [user]
Observation: 


def map_data(entry) -> dict[str, Any]:
    """Maps Standard Ebooks feed entry to an Open Library import object."""
    std_ebooks_id = entry.id.replace('https://standardebooks.org/ebooks/', '')
    image_uris = filter(lambda link: link.rel == IMAGE_REL, entry.links)

    # Standard ebooks only has English works at this time ; because we don't have an
    # easy way to translate the language codes they store in the feed to the MARC
    # language codes, we're just gonna handle English for now, and have it error
    # if Standard Ebooks ever adds non-English works.
    marc_lang_code = 'eng' if entry.language.startswith('en-') else None
    if not marc_lang_code:
        raise ValueError(f'Feed entry language {entry.language} is not supported.')
    import_record = {
        "title": entry.title,
        "source_records": [f"standard_ebooks:{std_ebooks_id}"],
        "publishers": [entry.publisher],
        "publish_date": entry.dc_issued[0:4],
        "authors": [{"name": author.name} for author in entry.authors],
        "description": entry.content[0].value,
        "subjects": [tag.term for tag in entry.tags],
        "identifiers": {"standard_ebooks": [std_ebooks_id]},
        "languages": [marc_lang_code],
    }

    if image_uris:
        import_record['cover'] = f'{BASE_SE_URL}{next(iter(image_uris))["href"]}'

    return import_record


def create_batch(records: list[dict[str, str]]) -> None:
    """Creates Standard Ebook batch import job.






[MSG 55] [assistant]
Let me check that import_standard_ebooks for language handling:

[MSG 56] [user]
Observation: 

/app/scripts/tests/test_partner_batch_imports.py
/app/scripts/providers/isbndb.py
/app/scripts/partner_batch_imports.py






[MSG 57] [assistant]
Let me look for language mapping utilities in the codebase:

[MSG 58] [user]
Observation: 

        'publishers',
        'weight',
        'authors',
        'lc_classifications',
        'pagination',
        'languages',
        'subjects',
        'source_records',
    ]
    INACTIVE_FIELDS = [
        "copyright",
--
        self.publishers = [data[135]]
        self.weight = data[39]
        self.authors = self.contributors(data)
        self.lc_classifications = [data[147]] if data[147] else []
        self.pagination = data[36]
        self.languages = [data[37].lower()]
        self.source_records = [self.source_id]
        self.subjects = [
            s.capitalize().replace('_', ', ')
            for s in data[91:100]
            # + data[101:120]






[MSG 59] [assistant]
Let me check the partner_batch_imports for language handling:

[MSG 60] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app/openlibrary/plugins/upstream, excluding hidden items:
/app/openlibrary/plugins/upstream
/app/openlibrary/plugins/upstream/data.py
/app/openlibrary/plugins/upstream/adapter.py
/app/openlibrary/plugins/upstream/jsdef.py
/app/openlibrary/plugins/upstream/borrow.py
/app/openlibrary/plugins/upstream/spamcheck.py
/app/openlibrary/plugins/upstream/checkins.py
/app/openlibrary/plugins/upstream/recentchanges.py
/app/openlibrary/plugins/upstream/__init__.py
/app/openlibrary/plugins/upstream/addbook.py
/app/openlibrary/plugins/upstream/covers.py
/app/openlibrary/plugins/upstream/addtag.py
/app/openlibrary/plugins/upstream/account.py
/app/openlibrary/plugins/upstream/merge_authors.py
/app/openlibrary/plugins/upstream/utils.py
/app/openlibrary/plugins/upstream/code.py
/app/openlibrary/plugins/upstream/forms.py
/app/openlibrary/plugins/upstream/models.py
/app/openlibrary/plugins/upstream/pages
/app/openlibrary/plugins/upstream/pages/home.page
/app/openlibrary/plugins/upstream/mybooks.py
/app/openlibrary/plugins/upstream/tests
/app/openlibrary/plugins/upstream/tests/test_checkins.py
/app/openlibrary/plugins/upstream/tests/__init__.py
/app/openlibrary/plugins/upstream/tests/test_data
/app/openlibrary/plugins/upstream/tests/test_utils.py
/app/openlibrary/plugins/upstream/tests/test_related_carousels.py
/app/openlibrary/plugins/upstream/tests/test_account.py
/app/openlibrary/plugins/upstream/tests/test_merge_authors.py
/app/openlibrary/plugins/upstream/tests/test_addbook.py
/app/openlibrary/plugins/upstream/tests/test_models.py
/app/openlibrary/plugins/upstream/tests/test_forms.py
/app/openlibrary/plugins/upstream/edits.py








[MSG 61] [assistant]
Let me check upstream utilities for language code mapping:

[MSG 62] [user]
Observation: 

STRIP_CHARS = ",'\" "
REPLACE_CHARS = "]["


class LanguageMultipleMatchError(Exception):
    """Exception raised when more than one possible language match is found."""

    def __init__(self, language_name):
        self.language_name = language_name


class LanguageNoMatchError(Exception):
    """Exception raised when no matching languages are found."""

    def __init__(self, language_name):
        self.language_name = language_name


class MultiDict(MutableMapping):
    """Ordered Dictionary that can store multiple values.

    Must be initialized without an `items` parameter, or `items` must be an
    iterable of two-value sequences. E.g., items=(('a', 1), ('b', 2))

    >>> d = MultiDict()
    >>> d['x'] = 1
--
    return web.ctx.site.get_many(web.ctx.site.things(q))


@public
def commify_list(items: Iterable[Any]) -> str:
    # Not sure why lang is sometimes ''
    lang = web.ctx.lang or 'en'
    # If the list item is a template/html element, we strip it
    # so that there is no space before the comma.
    return format_list([str(x).strip() for x in items], locale=lang)


@public
def json_encode(d):
    return json.dumps(d)


def unflatten(d: Storage, separator: str = "--") -> Storage:
    """Convert flattened data into nested form.

--
    return web.ctx.site.get_many([v.key for v in versions])


def get_locale():
    try:
        return babel.Locale(web.ctx.get("lang") or "en")
    except babel.core.UnknownLocaleError:
        return babel.Locale("en")


class HasGetKeyRevision(Protocol):
    key: str
    revision: int

    def get(self, item) -> Any:
        ...
--
            if unicodedata.category(c) != 'Mn'
        )


@functools.cache
def get_languages() -> dict:
    keys = web.ctx.site.things({"type": "/type/language", "limit": 1000})
    return {lang.key: lang for lang in web.ctx.site.get_many(keys)}


def autocomplete_languages(prefix: str) -> Iterator[Storage]:
    """
    Given, e.g., "English", this returns an iterator of:
        <Storage {'key': '/languages/ang', 'code': 'ang', 'name': 'English, Old (ca. 450-1100)'}>
        <Storage {'key': '/languages/eng', 'code': 'eng', 'name': 'English'}>
        <Storage {'key': '/languages/enm', 'code': 'enm', 'name': 'English, Middle (1100-1500)'}>
    """

    def normalize(s: str) -> str:
        return strip_accents(s).lower()

    prefix = normalize(prefix)
    user_lang = web.ctx.lang or 'en'
    for lang in get_languages().values():
        user_lang_name = safeget(lambda: lang['name_translated'][user_lang][0])
        if user_lang_name and normalize(user_lang_name).startswith(prefix):
            yield Storage(
                key=lang.key,
                code=lang.code,
                name=user_lang_name,
            )
            continue

        lang_iso_code = safeget(lambda: lang['identifiers']['iso_639_1'][0])
        native_lang_name = safeget(lambda: lang['name_translated'][lang_iso_code][0])
        if native_lang_name and normalize(native_lang_name).startswith(prefix):
            yield Storage(
                key=lang.key,
                code=lang.code,
                name=native_lang_name,
            )
            continue

        if normalize(lang.name).startswith(prefix):
            yield Storage(
                key=lang.key,
                code=lang.code,
                name=lang.name,
            )
            continue


def get_abbrev_from_full_lang_name(input_lang_name: str, languages=None) -> str:
    """
    Take a language name, in English, such as 'English' or 'French' and return
    'eng' or 'fre', respectively, if there is one match.

    If there are zero matches, raise LanguageNoMatchError.
    If there are multiple matches, raise a LanguageMultipleMatchError.
    """
    if languages is None:
        languages = get_languages().values()
    target_abbrev = ""

    def normalize(s: str) -> str:
        return strip_accents(s).lower()

    for language in languages:
        if normalize(language.name) == normalize(input_lang_name):
            if target_abbrev:
                raise LanguageMultipleMatchError(input_lang_name)

            target_abbrev = language.code
            continue

        for key in language.name_translated:
            if normalize(language.name_translated[key][0]) == normalize(
                input_lang_name
            ):
                if target_abbrev:
                    raise LanguageMultipleMatchError(input_lang_name)
                target_abbrev = language.code
                break

    if not target_abbrev:
        raise LanguageNoMatchError(input_lang_name)

    return target_abbrev


def get_language(lang_or_key: str) -> "None | Thing | Nothing":
    if isinstance(lang_or_key, str):
        return get_languages().get(lang_or_key)
    else:
        return lang_or_key


@public
def get_language_name(lang_or_key: "Nothing | str | Thing") -> Nothing | str:
    if isinstance(lang_or_key, str):
        lang = get_language(lang_or_key)
        if not lang:
            return lang_or_key
    else:
        lang = lang_or_key

    user_lang = web.ctx.lang or 'en'
    return safeget(lambda: lang['name_translated'][user_lang][0]) or lang.name  # type: ignore[index]


@functools.cache
def convert_iso_to_marc(iso_639_1: str) -> str | None:
    """
    e.g. 'en' -> 'eng'
    """
    for lang in get_languages().values():
        code = safeget(lambda: lang['identifiers']['iso_639_1'][0])
        if code == iso_639_1:
            return lang.code
    return None


@public
def get_author_config():
    return _get_author_config()


@web.memoize
def _get_author_config():






[MSG 63] [user]
Observation: 



































































The file /app/scripts/providers/isbndb.py has been edited. Here's the result of running `cat -n` on a snippet of /app/scripts/providers/isbndb.py:
     1	import json
     2	import logging
     3	import os
     4	import re
     5	from typing import Any, Final
     6	import requests
     7	
     8	from json import JSONDecodeError
     9	
    10	from openlibrary.config import load_config
    11	from openlibrary.core.imports import Batch
    12	from scripts.partner_batch_imports import is_published_in_future_year
    13	from scripts.solr_builder.solr_builder.fn_to_cli import FnToCLI
    14	from openlibrary.plugins.upstream.utils import (
    15	    get_abbrev_from_full_lang_name, 
    16	    LanguageNoMatchError,
    17	    LanguageMultipleMatchError,
    18	    convert_iso_to_marc
    19	)
    20	
    21	logger = logging.getLogger("openlibrary.importer.isbndb")
    22	
    23	SCHEMA_URL = (
    24	    "https://raw.githubusercontent.com/internetarchive"
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 64] [assistant]
Excellent! I found the language utilities. Now I can implement the ISBNdb import functionality. Let me create the enhanced functionality:

[MSG 65] [user]
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
**Analyzed**: 2026-04-12 19:56:15

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | contamination |
| Contamination type | task_patch_mismatch |
| Confidence | 0.98 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent focused on the stated CLI-integration problem: it inspected `scripts/manage_imports.py`, the import queue classes, and the existing `scripts/providers/isbndb.py`, planning to add a new manage-imports command and wire staged ISBNdb JSONL data into the existing import pipeline. It later explored provider parsing details and language utilities, but never submitted a patch.

**Contamination evidence**: The problem statement is about adding CLI support so users can stage/import local `isbndb.jsonl` dumps via `manage_imports.py`. But the F2P tests do not exercise `manage_imports.py` or any CLI pathway at all. Instead they import a specific provider class `ISBNdb` from `scripts/providers/isbndb.py`, require that exact class name (replacing the preexisting `Biblio`), and unit-test private/internal helpers `_get_languages()` and `_get_year()` with specific normalization behavior (e.g. `en_US -> ['eng']`, `es,Eng -> ['spa', 'eng']`, `December 2000 -> '2000'`). None of those APIs, helper names, or edge-case behaviors are stated in the task. A solution that correctly added CLI integration using the existing provider would still fail these tests.

**Difficulty evidence**: None

**Full reasoning**: This is a clear contamination case, primarily a task/spec mismatch. The agent read the prompt and sensibly pursued the documented problem: integrating ISBNdb dumps into the import CLI by examining `manage_imports.py`, the import queue, and staging flow. That is exactly what the problem statement asks for. However, the gold patch and F2P tests instead center on internal provider refactoring and normalization logic inside `scripts/providers/isbndb.py`, including an exact public class rename (`Biblio` -> `ISBNdb`) and tests against private methods `_get_languages` and `_get_year`. Those requirements are not derivable from the prompt, and the tests never verify the advertised CLI behavior. So the agent's failure is not evidence that the task is merely hard; it was being guided by the stated requirement while the tests demanded different, hidden implementation details.
