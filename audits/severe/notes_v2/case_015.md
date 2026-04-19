# Case #15 Re-Audit Notes (v2)

**Instance**: `instance_internetarchive__openlibrary-7f6b722a10f822171501d027cad60afe53337732-ve8c8d62a2b60610a3c4631f5f23ed866bada9818`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

# Title

Work search query processing fails for edge-case inputs after scheme refactor

## Problem Description

Following the introduction of the `SearchScheme`-based work search, raw user queries are not consistently normalized and escaped before reaching Solr. Inputs with trailing dashes, reserved operators, or quoted strings can be misinterpreted by the parser under the current work search scheme, leading to parse errors or unintended queries.

## Actual Behavior

Submitting work search queri...

**Type**: python | **Repo**: internetarchive/openlibrary
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 13 |
| Gold patch files | 13 |
| Gold patch size | 77388 chars |
| Test patch size | 9780 chars |
| Test patch files | 3 |
| F2P tests | 4 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
openlibrary/plugins/worksearch/schemes/tests/test_works.py
openlibrary/plugins/worksearch/tests/test_worksearch.py
openlibrary/utils/tests/test_utils.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard febda3f008cb4d4e4e0568ab4d671992ceea07cf
git clean -fd 
git checkout febda3f008cb4d4e4e0568ab4d671992ceea07cf 
git checkout 7f6b722a10f822171501d027cad60afe53337732 -- openlibrary/plugins/worksearch/schemes/tests/test_works.py openlibrary/plugins/worksearch/tests/test_worksearch.py openlibrary/utils/tests/test_utils.py
```

## 3. Trajectory Evidence

### Resolution Rate: 7/13 (54%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Sonnet 4 - paper | FAIL | 19 |
| Gemini 2.5 Pro Preview - paper | FAIL | 39 |
| GPT-4o - paper | FAIL | 41 |
| GPT-5 High - paper | PASS | 37 |
| GPT OSS - paper | FAIL | 17 |
| Kimi - paper | PASS | 51 |
| Claude 4.5 Sonnet - 10132025 | PASS | 78 |
| Claude 4 Sonnet - 10132025 | PASS | 49 |
| GPT-5 - 10132025 | PASS | 80 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 26 |
| GPT-5 Codex -- debug-oct22 | FAIL | 249 |
| GLM-4.5 -- 10222025 | PASS | 62 |
| Claude 4.5 Haiku -- 10222025 | PASS | 67 |

### Representative Trajectory: Gemini 2.5 Pro Preview - paper
- **Resolved**: False
- **Turns**: 75
- **Total tokens**: ~23721
- **Truncated**: False
- **Has agent patch**: False
- **Leakage signals**: []

### Trajectory Head (first actions)
<details>
<summary>Click to expand (first ~2K tokens)</summary>

```
[MSG 0] [user]
Observation: 

/app/openlibrary:
__init__.py  api.py		components   data    plugins	utils
__pycache__  app.py		config.py    i18n    records	views
accounts     book_providers.py	conftest.py  macros  solr
actions.py   catalog		core	     mocks   templates
admin	     code.py		coverstore   olbase  tests

/app/openlibrary/__pycache__:
__init__.cpython-311.pyc

/app/openlibrary/accounts:
__init__.py  model.py

/app/openlibrary/admin:
__init__.py  code.py  numbers.py  stats.py  templates  utils.py

/app/openlibrary/admin/templates:
admin

/app/openlibrary/admin/templates/admin:
index.html

/app/openlibrary/catalog:
README.md  __init__.py	add_book  get_ia.py  marc  merge  utils

/app/openlibrary/catalog/add_book:
__init__.py  load_book.py  match.py  tests

/app/openlibrary/catalog/add_book/tests:
__init__.py  test_add_book.py  test_load_book.py
conftest.py  test_data	       test_match.py

/app/openlibrary/catalog/add_book/tests/test_data:
coursepuremath00hardrich_meta.mrc    sexuallytransmit00egen_meta.mrc
descendantsofhug00cham_meta.mrc      treatiseonhistor00dixo_meta.mrc
flatlandromanceo00abbouoft_meta.mrc  v38.i37.records.utf8--16478504-1254
isbn_9781419594069_meta.mrc	     v39.i28.records.utf8--5362776-1764
nurembergwarcrim1997marr_meta.mrc    v39.i34.records.utf8--186503-1413
roadstogreatness00gall_meta.mrc      workshuberthowe00racegoog_meta.mrc

/app/openlibrary/catalog/marc:
__init__.py	 html.py	 marc_subject.py  parse.py
fast_parse.py	 marc_base.py	 marc_xml.py	  parse_xml.py
get_subjects.py  marc_binary.py  mnemonics.py	  tests

/app/openlibrary/catalog/marc/tests:
test_data	      test_marc.py	   test_marc_html.py  test_parse.py
test_get_subjects.py  test_marc_binary.py  test_mnemonics.py

/app/openlibrary/catalog/marc/tests/test_data:
bin_expect  bin_input  xml_expect  xml_input

/app/openlibrary/catalog/marc/tests/test_data/bin_expect:
13dipolarcycload00burk_meta.mrc      ocm00400866
bijouorannualofl1828cole_meta.mrc    onquietcomedyint00brid_meta.mrc
bpl_0486266893			     secretcodeofsucc00stjo_meta.mrc
collingswood_520aa.mrc		     talis_245p.mrc
collingswood_bad_008.mrc	     talis_740.mrc
cu31924091184469_meta.mrc	     talis_856.mrc
diebrokeradical400poll_meta.mrc      talis_empty_245.mrc
engineercorpsofh00sher_meta.mrc      talis_multi_work_tiles.mrc
equalsign_title.mrc		     talis_no_title.mrc
flatlandromanceo00abbouoft_meta.mrc  talis_two_authors.mrc
henrywardbeecher00robauoft_meta.mrc  thewilliamsrecord_vol29b_meta.mrc
histoirereligieu05cr_meta.mrc	     uoft_4351105_1626
ithaca_college_75002321		     upei_broken_008.mrc
ithaca_two_856u.mrc		     upei_short_008.mrc
lc_0444897283			     warofrebellionco1473unit_meta.mrc
lc_1416500308			     wrapped_lines
memoirsofjosephf00fouc_meta.mrc      wwu_51323556
merchantsfromcat00ben_meta.mrc	     zweibchersatir01horauoft_meta.mrc

/app/openlibrary/catalog/marc/tests/test_data/bin_input:
0descriptionofta1682unit_meta.mrc    mytwocountries1954asto_meta.mrc
13dipolarcycload00burk_meta.mrc      new_poganucpeoplethe00stowuoft_meta.mrc
1733mmoiresdel00vill_meta.mrc	     ocm00400866
bijouorannualofl1828cole_meta.mrc    onquietcomedyint00brid_meta.mrc
bpl_0486266893			     poganucpeoplethe00stowuoft_meta.mrc
collingswood_520aa.mrc		     scrapbooksofmoun03tupp_meta.mrc
collingswood_bad_008.mrc	     secretcodeofsucc00stjo_meta.mrc
cu31924091184469_meta.mrc	     talis_245p.mrc
dasrmischepriv00rein_meta.mrc	     talis_740.mrc
diebrokeradical400poll_meta.mrc      talis_856.mrc
engineercorpsofh00sher_meta.mrc      talis_empty_245.mrc
equalsign_title.mrc		     talis_multi_work_tiles.mrc
flatlandromanceo00abbouoft_meta.mrc  talis_no_title.mrc
henrywardbeecher00robauoft_meta.mrc  talis_no_title2.mrc
histoirereligieu05cr_meta.mrc	     talis_see_also.mrc
ithaca_college_75002321		     talis_two_authors.mrc
ithaca_two_856u.mrc		     thewilliamsrecord_vol29b_meta.mrc
lc_0444897283			     uoft_4351105_1626
lc_1416500308			     upei_broken_008.mrc
lesabndioeinas00sche_meta.mrc	     upei_short_008.mrc
lincolncentenary00horn_meta.mrc      warofrebellionco1473unit_meta.mrc
livrodostermosh00bragoog_meta.mrc    wrapped_lines
memoirsofjosephf00fouc_meta.mrc      wwu_51323556
merchantsfromcat00ben_meta.mrc	     zweibchersatir01horauoft_meta.mrc

/app/openlibrary/catalog/marc/tests/test_data/xml_expect:
00schlgoog_marc.xml		   flatlandromanceo00abbouoft_marc.xml
0descriptionofta1682unit_marc.xml  nybc200247_marc.xml
13dipolarcycload00burk_marc.xml    onquietcomedyint00brid_marc.xml
1733mmoiresdel00vill_marc.xml	   secretcodeofsucc00stjo_marc.xml
39002054008678.yale.edu_marc.xml   soilsurveyrepor00statgoog_marc.xml
bijouorannualofl1828cole_marc.xml  warofrebellionco1473unit_marc.xml
cu31924091184469_marc.xml	   zweibchersatir01horauoft_marc.xml
engineercorpsofh00sher_marc.xml

/app/openlibrary/catalog/marc/tests/test_data/xml_input:
00schlgoog_marc.xml		     lesabndioeinas00sche_marc.xml
0descriptionofta1682unit_marc.xml    lincolncentenary00horn_marc.xml
13dipolarcycload00burk_marc.xml      livrodostermosh00bragoog_marc.xml
1733mmoiresdel00vill_marc.xml	     mytwocountries1954asto_marc.xml
39002054008678.yale.edu_marc.xml     nybc200247_marc.xml
abhandlungender01ggoog_marc.xml      onquietcomedyint00brid_marc.xml
bijouorannualofl1828cole_marc.xml    scrapbooksofmoun03tupp_marc.xml
cu31924091184469_marc.xml	     secretcodeofsucc00stjo_marc.xml
dasrmischepriv00rein_marc.xml	     soilsurveyrepor00statgoog_marc.xml
engineercorpsofh00sher_marc.xml      warofrebellionco1473unit_marc.xml
flatlandromanceo00abbouoft_marc.xml  zweibchersatir01horauoft_marc.xml

/app/openlibrary/catalog/merge:
__init__.py    names.py       test_merge_marc.py
merge.py       normalize.py   test_names.py
merge_marc.py  test_merge.py  test_normalize.py

/app/openlibrary/catalog/utils:
__init__.py  edit.py  query.py

/app/openlibrary/components:
AuthorIdentifiers.vue  LibraryExplorer.vue  ObservationForm	 dev.js
HelloWorld.vue	       MergeUI		    ObservationForm.vue
LibraryExplorer        MergeUI.vue	    README.md

/app/openlibrary/components/LibraryExplorer:
assets	components  configs.js	ddc.json  lcc.json  utils  utils.js

/app/openlibrary/components/LibraryExplorer/assets:
logo.png

/app/openlibrary/components/LibraryExplorer/components:
BookCover3D.vue    CSSBox.vue	      LibraryToolbar.vue  ShelfLabel.vue
BookRoom.vue	   ClassSlider.vue    OLCarousel.vue	  ShelfProgressBar.vue
BooksCarousel.vue  DemoA.vue	      Shelf.vue		  icons
Bookshelf.vue	   FlatBookCover.vue  ShelfIndex.vue

/app/openlibrary/components/LibraryExplorer/components/icons:
ExpandIcon.vue	  FilterIcon.vue  RightArrowIcon.vue  SortIcon.vue
FeedbackIcon.vue  IndexIcon.vue   SettingsIcon.vue

/app/openlibrary/components/LibraryExplorer/utils:
lcc.js

/app/openlibrary/components/MergeUI:
AuthorRoleTable.vue  MergeRowEditionField.vue	  MergeTable.vue
EditionSnippet.vue   MergeRowField.vue		  TextDiff.vue
ExcerptsTable.vue    MergeRowJointField.vue	  utils.js
MergeRow.vue	     MergeRowReferencesField.vue

/app/openlibrary/components/ObservationForm:
ObservationService.js  Utils.js  components

/app/openlibrary/components/ObservationForm/components:
CardBody.vue	CategorySelector.vue  SavedTags.vue
CardHeader.vue	OLChip.vue	      ValueCard.vue

/app/openlibrary/core:
__init__.py	       formats.py     models.py        sponsorships.py
admin.py	       fulltext.py    observations.py  stats.py
booknotes.py	       helpers.py     olmarkdown.py    statsdb.py
bookshelves.py	       ia.py	      processors       users.sql
bookshelves_events.py  imports.py     ratings.py       vendors.py
cache.py	       lending.py     schema.py        waitinglist.py
civicrm.py	       lists	      schema.sql
db.py		       loanstats.py   sendmail.py
edits.py	       middleware.py  seq.py

/app/openlibrary/core/lists:
__init__.py  engine.py	model.py

/app/openlibrary/core/processors:
__init__.py  invalidation.py  readableurls.py

/app/openlibrary/coverstore:
__init__.py  code.py	coverlib.py  disk.py  schema.py   serve
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
ion: 

Couldn't find statsd_server section in config
Traceback (most recent call last):
  File "/app/reproduce_bug.py", line 7, in <module>
    from openlibrary.plugins.worksearch.code import run_sol_query
ImportError: cannot import name 'run_sol_query' from 'openlibrary.plugins.worksearch.code' (/app/openlibrary/plugins/worksearch/code.py)






[MSG 39] [assistant]
I'll run the script again with the mocked environment.

[MSG 40] [user]
Observation: 

The file /app/reproduce_bug.py has been edited. Here's the result of running `cat -n` on a snippet of /app/reproduce_bug.py:
     2	import sys
     3	sys.path.append('/app')
     4	
     5	import web
     6	from infogami import config
     7	from openlibrary.plugins.worksearch.code import run_solr_query
     8	
     9	# Mock the web environment
    10	web.ctx.env = {}
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 41] [assistant]
I apologize for the typo. It should be `run_solr_query`. I'll correct the script and run it again.

[MSG 42] [user]
Observation: 

Couldn't find statsd_server section in config
An exception occurred: 'REQUEST_METHOD'






[MSG 43] [assistant]
Now, let's try this again.

[MSG 44] [user]
Observation: 



















The file /app/reproduce_bug.py has been edited. Here's the result of running `cat -n` on a snippet of /app/reproduce_bug.py:
     3	sys.path.append('/app')
     4	
     5	import web
     6	from infogami import config
     7	from openlibrary.plugins.worksearch.code import run_solr_query
     8	
     9	# Mock the web environment
    10	web.ctx.env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/search', 'QUERY_STRING': 'q=Horror-'}
    11	config.statsd_server = {}
    12	config.plugin_worksearch = {'solr_base_url': 'http://solr:8983/solr/openlibrary-search'}
    13	
    14	try:
    15	    result = run_solr_query({'q': 'Horror-'}, spellcheck_count=10)
    16	    if result and result.get('error'):
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 45] [assistant]
It seems I'm still missing some web environment setup. The error `'REQUEST_METHOD'` suggests that the web context is not fully initialized. I'll add more to the mock environment.

[MSG 46] [user]
Observation: 

Couldn't find statsd_server section in config
An exception occurred: name 'solr_select_url' is not defined






[MSG 47] [assistant]
Let's run the script again.

[MSG 48] [user]
Observation: 

The file /app/reproduce_bug.py has been edited. Here's the result of running `cat -n` on a snippet of /app/reproduce_bug.py:
     7	from openlibrary.plugins.worksearch.code import run_solr_query
     8	
     9	# Mock the web environment
    10	web.ctx.env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/search', 'QUERY_STRING': 'q=Horror-'}
    11	config.statsd_server = {}
    12	config.plugin_worksearch = {'solr_base_url': 'http://solr:8983/solr/openlibrary-search', 'solr_select_url': 'http://solr:8983/solr/openlibrary-search/select'}
    13	
    14	try:
    15	    result = run_solr_query({'q': 'Horror-'}, spellcheck_count=10)
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 49] [assistant]
It seems I'm still missing a configuration variable. I'll add `solr_select_url` to the mock configuration.

[MSG 50] [user]
Observation: 

Couldn't find statsd_server section in config
An exception occurred: name 'solr_select_url' is not defined






[MSG 51] [assistant]
Let's try this one more time.

[MSG 52] [assistant]
I see, the `solr_select_url` is defined outside of the config object. I'll correct the script.

[MSG 53] [user]
Observation: 





























































































The file /app/reproduce_bug.py has been edited. Here's the result of running `cat -n` on a snippet of /app/reproduce_bug.py:
     1	
     2	import sys
     3	sys.path.append('/app')
     4	
     5	import web
     6	from infogami import config
     7	from openlibrary.plugins.worksearch.code import run_solr_query
     8	from openlibrary.plugins.worksearch import code as worksearch_code
     9	
    10	# Mock the web environment
    11	web.ctx.env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/search', 'QUERY_STRING': 'q=Horror-'}
    12	config.statsd_server = {}
    13	config.plugin_worksearch = {'solr_base_url': 'http://solr:8983/solr/openlibrary-search'}
    14	worksearch_code.solr_select_url = 'http://solr:8983/solr/openlibrary-search/select'
    15	
    16	try:
    17	    result = run_solr_query({'q': 'Horror-'}, spellcheck_count=10)
    18	    if result and result.get('error'):
    19	        print(f"Search failed with error: {result['error']}")
    20	    else:
    21	        print("Search successful.")
    22	        print(result)
    23	except Exception as e:
    24	    print(f"An exception occurred: {e}")
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 54] [assistant]
You are absolutely correct. I apologize for that mistake. I will correct my approach and use the proper command.

Let me try to fix the reproduction script again, this time being more careful about the configuration.

[MSG 55] [user]
Observation: 

Couldn't find statsd_server section in config
An exception occurred: HTTPConnectionPool(host='solr', port=8983): Max retries exceeded with url: /solr/openlibrary-search/select (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x2b827ac6df90>: Failed to establish a new connection: [Errno -2] Name or service not known'))






[MSG 56] [assistant]
I'll run the script again.

[MSG 57] [user]
Observation: 

The file /app/reproduce_bug.py has been edited. Here's the result of running `cat -n` on a snippet of /app/reproduce_bug.py:
     9	
    10	# Mock the web environment
    11	web.ctx.env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/search', 'QUERY_STRING': 'q=Horror-'}
    12	config.statsd_server = {}
    13	config.plugin_worksearch = {'solr_base_url': 'http://solr:8983/solr/openlibrary-search'}
    14	worksearch_code.solr_select_url = 'http://localhost:8983/solr/openlibrary-search/select'
    15	
    16	try:
    17	    result = run_solr_query({'q': 'Horror-'}, spellcheck_count=10)
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 58] [assistant]
The error `Name or service not known` indicates that the script can't resolve the hostname `solr`. This is because the script is running in a different container than the Solr service. I'll modify the script to use `localhost` instead of `solr` for the Solr hostname. This should work as long as the Solr service is running on the same machine.

[MSG 59] [user]
Observation: 

The file /app/reproduce_bug.py has been edited. Here's the result of running `cat -n` on a snippet of /app/reproduce_bug.py:
     8	from openlibrary.plugins.worksearch import code as worksearch_code
     9	
    10	# Mock the web environment
    11	web.ctx.env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/search', 'QUERY_STRING': 'q=Horror-'}
    12	config.statsd_server = {}
    13	config.plugin_worksearch = {'solr_base_url': 'http://localhost:8983/solr/openlibrary-search'}
    14	worksearch_code.solr_select_url = 'http://localhost:8983/solr/openlibrary-search/select'
    15	
    16	try:
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 60] [assistant]
I'll also need to change the `solr_base_url` to use `localhost`.

[MSG 61] [user]
Observation: 

Couldn't find statsd_server section in config
An exception occurred: HTTPConnectionPool(host='localhost', port=8983): Max retries exceeded with url: /solr/openlibrary-search/select (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x2b767c5be650>: Failed to establish a new connection: [Errno 111] Connection refused'))






[MSG 62] [assistant]
Now I'll run the script again.

[MSG 63] [user]
Observation: 







[MSG 64] [assistant]
It seems Solr is not running on localhost. I will assume for now that the bug is reproducible and proceed with the implementation of the `SearchScheme`. I'll come back to the reproduction script later.

My next step is to create the `SearchScheme` abstraction. I'll create a new directory `openlibrary/plugins/worksearch/schemes` and a file `__init__.py` inside it.I can't seem to get the reproduction script to work because Solr isn't running. I'll proceed with the implementation of the `SearchScheme`, assuming the bug is reproducible, and then return to the script later.

First, I'll create a new directory `openlibrary/plugins/worksearch/schemes` for the `SearchScheme` and add an `__init__.py` file to it.

[MSG 65] [user]
Observation: 





File created successfully at: /app/openlibrary/plugins/worksearch/schemes/__init__.py






[MSG 66] [user]
Observation: 





































































































File created successfully at: /app/openlibrary/plugins/worksearch/schemes/base.py






[MSG 67] [assistant]
Now I'll create the `base.py` file in the `schemes` directory and define the `SearchScheme` class. This class will have a `process_user_query` method that will handle the escaping of special characters.

[MSG 68] [user]
Observation: 



The file /app/openlibrary/plugins/worksearch/code.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/code.py:
    32	    get_language_name,
    33	    urlencode,
    34	)
    35	from openlibrary.plugins.worksearch.search import get_solr
    36	from openlibrary.solr.solr_types import SolrDocument
    37	from openlibrary.plugins.worksearch.schemes import SearchScheme
    38	from openlibrary.solr.query_utils import (
    39	    EmptyTreeError,
    40	    escape_unknown_fields,
    41	    fully_escape_query,
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 69] [assistant]
Now that the `SearchScheme` is defined, I need to modify the `run_solr_query` function in `openlibrary/plugins/worksearch/code.py` to use it. This will involve passing a `SearchScheme` instance to the function and using its `process_user_query` method.

First, I'll add the import for the `SearchScheme`.

[MSG 70] [user]
Observation: 















































The file /app/openlibrary/plugins/worksearch/code.py has been edited. Here's the result of running `cat -n` on a snippet of /app/openlibrary/plugins/worksearch/code.py:
   475	        return cookie_value == 'true'
   476	
   477	    return False
   478	
   479	
   480	def run_solr_query(
   481	    param: Optional[dict] = None,
   482	    rows=100,
   483	    page=1,
   484	    sort: str | None = None,
   485	    spellcheck_count=None,
   486	    offset=None,
   487	    fields: Union[str, list[str]] | None = None,
   488	    facet: Union[bool, Iterable[str]] = True,
   489	    allowed_filter_params=FACET_FIELDS,
   490	    extra_params: Optional[list[tuple[str, Any]]] = None,
   491	    scheme: Optional[SearchScheme] = None,
   492	):
   493	    """
   494	    :param param: dict of query parameters
   495	    """
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 71] [assistant]
Now, I'll modify the `run_solr_query` function to accept a `SearchScheme` and use it to process the query. I will also create a default `SearchScheme` instance to be used when no scheme is provided.

[MSG 72] [user]
Observation: 













No replacement was performed, old_str `    # The main query
    q = build_q_from_params(param)` did not appear verbatim in /app/openlibrary/plugins/worksearch/code.py.






[MSG 73] [assistant]
Now I need to add the logic to `run_solr_query` to use the scheme to process the query. I'll also create a default `SearchScheme` instance.

[MSG 74] [user]
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

**Model**: Gemini 2.5 Pro Preview - paper
**Analyzed**: 2026-04-12 18:59:39

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | agent_error |
| Contamination type | None |
| Confidence | 0.95 |
| **Verdict** | **CLEAN** |

**Agent approach**: The agent recognized that the issue involved query escaping/normalization in work search and that a SearchScheme/WorkSearchScheme abstraction was likely needed. It then spent most of the trajectory unsuccessfully exploring the repo, trying to reproduce the bug with an ad hoc script, and only began a partial refactor before exiting without a usable patch.

**Contamination evidence**: None

**Difficulty evidence**: None

**Full reasoning**: This task looks clean rather than contaminated. The problem statement explicitly mentions the new `WorkSearchScheme.process_user_query` path and the affected edge cases: trailing dashes, operator-like tokens, quoted phrases, and ISBN-like strings. The F2P tests exercise exactly those behaviors. While the tests do assert exact parsed-query strings, those expectations are not hidden gold-patch internals: the repo already contained the old `process_user_query` implementation in `openlibrary/plugins/worksearch/code.py`, along with the relevant alias mapping (`FIELD_NAME_MAP`) and query-transformation logic. In fact, most of the new tests were effectively migrated from existing tests in `test_worksearch.py`, and the remaining ISBN normalization behavior was already implemented in the old parser code. So an agent could reasonably infer the intended behavior by reading the existing code and porting/adapting it into `WorkSearchScheme`. The represented agent did not reach that point: it repeatedly chased nonexistent files, struggled with environment setup, failed to inspect the actual relevant code paths deeply, and exited without submitting a functional patch. That indicates implementation/process failure by the agent, not unfair tests.
