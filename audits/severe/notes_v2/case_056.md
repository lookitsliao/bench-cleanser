# Case #56 Re-Audit Notes (v2)

**Instance**: `instance_ansible__ansible-d33bedc48fdd933b5abd65a77c081876298e2f07-v0f01c69f1e2528b935359cfe578530722bca2c59`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"## config values returned by get_option() may lose tags \n\n## Summary: The ensure_type() function in Ansible's config manager loses data tags during type conversion and has multiple type coercion bugs. Values lose their trust/origin metadata when converted, unhashable values cause TypeError exceptions, byte values cause unhandled exceptions, sequences don't convert properly to lists, mappings don't convert to dictionaries, and boolean-to-integer conversion fails. \n\n## Issue Type: Bug Report ...

**Type**: python | **Repo**: ansible/ansible
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 7 |
| Gold patch files | 7 |
| Gold patch size | 23129 chars |
| Test patch size | 9482 chars |
| Test patch files | 1 |
| F2P tests | 7 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
test/units/config/test_manager.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard dcc5dac1846be3bf6e948a2950b93477b9193076
git clean -fd 
git checkout dcc5dac1846be3bf6e948a2950b93477b9193076 
git checkout d33bedc48fdd933b5abd65a77c081876298e2f07 -- test/units/config/test_manager.py
```

## 3. Trajectory Evidence

### Resolution Rate: 0/14 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 47 |
| Claude Sonnet 4 - paper | FAIL | 22 |
| Gemini 2.5 Pro Preview - paper | FAIL | 20 |
| GPT-4o - paper | FAIL | 30 |
| GPT-5 High - paper | FAIL | 47 |
| GPT OSS - paper | FAIL | 51 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 94 |
| Claude 4 Sonnet - 10132025 | FAIL | 66 |
| GPT-5 - 10132025 | FAIL | 116 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 10 |
| GPT-5 Codex -- debug-oct22 | FAIL | 209 |
| GLM-4.5 -- 10222025 | FAIL | 87 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 85 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 74
- **Total tokens**: ~28219
- **Truncated**: False
- **Has agent patch**: False
- **Leakage signals**: []

### Trajectory Head (first actions)
<details>
<summary>Click to expand (first ~2K tokens)</summary>

```
[MSG 0] [user]
Observation: 

/app/lib/ansible/utils/collection_loader/_collection_config.py
/app/lib/ansible/cli/inventory.py
/app/lib/ansible/cli/config.py
/app/lib/ansible/_internal/_json/_profiles/_inventory_legacy.py
/app/lib/ansible/_internal/ansible_collections/ansible/_protomatter/plugins/lookup/config.py
/app/lib/ansible/config/__init__.py
/app/lib/ansible/config/manager.py
/app/lib/ansible/inventory/manager.py
/app/lib/ansible/inventory/host.py
/app/lib/ansible/inventory/data.py
/app/lib/ansible/inventory/helpers.py
/app/lib/ansible/inventory/group.py
/app/lib/ansible/inventory/__init__.py
/app/lib/ansible/plugins/inventory/script.py
/app/lib/ansible/plugins/inventory/__init__.py
/app/lib/ansible/plugins/inventory/auto.py
/app/lib/ansible/plugins/inventory/host_list.py
/app/lib/ansible/plugins/inventory/toml.py
/app/lib/ansible/plugins/inventory/constructed.py
/app/lib/ansible/plugins/inventory/advanced_host_list.py
grep: write error: Broken pipe






[MSG 1] [assistant]
I'll start by exploring the repository structure to understand the codebase and locate the relevant files for configuration management and inventory plugins.

[MSG 2] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app, excluding hidden items:
/app
/app/bin
/app/bin/ansible-galaxy
/app/bin/ansible-doc
/app/bin/ansible-test
/app/bin/ansible-pull
/app/bin/ansible-config
/app/bin/ansible
/app/bin/ansible-vault
/app/bin/ansible-console
/app/bin/ansible-inventory
/app/bin/ansible-playbook
/app/lib
/app/lib/ansible
/app/COPYING
/app/MANIFEST.in
/app/hacking
/app/hacking/deprecated_issue_template.md
/app/hacking/backport
/app/hacking/tests
/app/hacking/azp
/app/hacking/create-bulk-issues.py
/app/hacking/ansible-profile.py
/app/hacking/README.md
/app/hacking/ticket_stubs
/app/hacking/env-setup.fish
/app/hacking/env-setup
/app/hacking/report.py
/app/hacking/update-sanity-requirements.py
/app/hacking/return_skeleton_generator.py
/app/hacking/test-module.py
/app/ansible_core.egg-info
/app/ansible_core.egg-info/entry_points.txt
/app/ansible_core.egg-info/PKG-INFO
/app/ansible_core.egg-info/SOURCES.txt
/app/ansible_core.egg-info/dependency_links.txt
/app/ansible_core.egg-info/top_level.txt
/app/ansible_core.egg-info/requires.txt
/app/requirements.txt
/app/packaging
/app/packaging/release.py
/app/packaging/cli-doc
/app/licenses
/app/licenses/simplified_bsd.txt
/app/licenses/PSF-license.txt
/app/licenses/MIT-license.txt
/app/licenses/Apache-License.txt
/app/licenses/BSD-3-Clause.txt
/app/changelogs
/app/changelogs/config.yaml
/app/changelogs/fragments
/app/changelogs/changelog.yaml
/app/changelogs/README.md
/app/pyproject.toml
/app/README.md
/app/test
/app/test/units
/app/test/lib
/app/test/support
/app/test/integration
/app/test/sanity








[MSG 3] [user]
Observation: 

<NOTE>This file is too large to display entirely. Showing abbreviated version. Please use `str_replace_editor view` with the `view_range` parameter to show selected lines next.</NOTE>
     1 # Copyright: (c) 2017, Ansible Project
     2 # GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
     3 
     4 from __future__ import annotations
     5 
     6 import atexit
     7 import decimal
     8 import configparser
     9 import os
    10 import os.path
    11 import sys
    12 import stat
    13 import tempfile
    14 import typing as t
    15 
    16 from collections.abc import Mapping, Sequence
    17 from jinja2.nativetypes import NativeEnvironment
    18 
    19 from ansible.errors import AnsibleOptionsError, AnsibleError, AnsibleUndefinedConfigEntry, AnsibleRequiredOptionError
    20 from ansible.module_utils.common.sentinel import Sentinel
    21 from ansible.module_utils.common.text.converters import to_text, to_bytes, to_native
    22 from ansible.module_utils.common.yaml import yaml_load
    23 from ansible.module_utils.six import string_types
    24 from ansible.module_utils.parsing.convert_bool import boolean
    25 from ansible.parsing.quoting import unquote
    26 from ansible.utils.path import cleanup_tmp_file, makedirs_safe, unfrackpath
    27 
    28 
    29 INTERNAL_DEFS = {'lookup': ('_terms',)}
    30 
    31 GALAXY_SERVER_DEF = [
    32     ('url', True, 'str'),
    33     ('username', False, 'str'),
    34     ('password', False, 'str'),
    35     ('token', False, 'str'),
    36     ('auth_url', False, 'str'),
    37     ('api_version', False, 'int'),
    38     ('validate_certs', False, 'bool'),
    39     ('client_id', False, 'str'),
    40     ('client_secret', False, 'str'),
    41     ('timeout', False, 'int'),
    42 ]
    43 
    44 # config definition fields
    45 GALAXY_SERVER_ADDITIONAL = {
    46     'api_version': {'default': None, 'choices': [2, 3]},
    47     'validate_certs': {'cli': [{'name': 'validate_certs'}]},
    48     'timeout': {'cli': [{'name': 'timeout'}]},
    49     'token': {'default': None},
    50 }
    51 
    52 
    53 def _get_config_label(plugin_type: str, plugin_name: str, config: str) -> str:
    54 ... eliding lines 54-65 ...
    66 
    67 
    68 # FIXME: see if we can unify in module_utils with similar function used by argspec
    69 def ensure_type(value, value_type, origin=None, origin_ftype=None):
    70 ... eliding lines 70-190 ...
   191 
   192 
   193 # FIXME: see if this can live in utils/path
   194 def resolve_path(path, basedir=None):
   195     """ resolve relative or 'variable' paths """
   196     if '{{CWD}}' in path:  # allow users to force CWD using 'magic' {{CWD}}
   197         path = path.replace('{{CWD}}', os.getcwd())
   198 
   199     return unfrackpath(path, follow=False, basedir=basedir)
   200 
   201 
   202 # FIXME: generic file type?
   203 def get_config_type(cfile):
   204 
   205 ... eliding lines 205-215 ...
   216 
   217 
   218 # FIXME: can move to module_utils for use for ini plugins also?
   219 def get_ini_config_value(p, entry):
   220 ... eliding lines 220-227 ...
   228 
   229 
   230 def find_ini_config_file(warnings=None):
   231 ... eliding lines 231-290 ...
   291 
   292 
   293 def _add_base_defs_deprecations(base_defs):
   294 ... eliding lines 294-304 ...
   305 
   306 
   307 class ConfigManager(object):
   308 
   309     DEPRECATED = []  # type: list[tuple[str, dict[str, str]]]
   310     WARNINGS = set()  # type: set[str]
   311 
   312     def __init__(self, conf_file=None, defs_file=None):
   313 
   314 ... eliding lines 314-333 ...
   334 
   335     def load_galaxy_server_defs(self, server_list):
   336 
   337 ... eliding lines 337-369 ...
   338 ... eliding lines 338-358 ...
   370 
   371     def template_default(self, value, variables):
   372 ... eliding lines 372-381 ...
   382 
   383     def _read_config_yaml_file(self, yml_file):
   384         # TODO: handle relative paths as relative to the directory containing the current playbook instead of CWD
   385         # Currently this is only used with absolute paths to the `ansible/config` directory
   386 ... eliding lines 386-391 ...
   392 
   393     def _parse_config_file(self, cfile=None):
   394 ... eliding lines 394-418 ...
   419 
   420     def _find_yaml_config_files(self):
   421         """ Load YAML Config Files in order, check merge flags, keep origin of settings"""
   422         pass
   423 
   424     def get_plugin_options(self, plugin_type, name, keys=None, variables=None, direct=None):
   425 
   426 ... eliding lines 426-431 ...
   432 
   433     def get_plugin_vars(self, plugin_type, name):
   434 
   435 ... eliding lines 435-440 ...
   441 
   442     def get_plugin_options_from_var(self, plugin_type, name, variable):
   443 
   444 ... eliding lines 444-450 ...
   451 
   452     def get_configuration_definition(self, name, plugin_type=None, plugin_name=None):
   453 
   454 ... eliding lines 454-462 ...
   463 
   464     def has_configuration_definition(self, plugin_type, name):
   465 
   466         has = False
   467         if plugin_
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
print(f"ERROR: Item {i} lost its trust tag!")
    38	    
    39	    # Test boolean conversion
    40	    print("\nTesting boolean conversion...")
    41	    bool_tagged = AnsibleTagHelper.tag("true", TrustedAsTemplate())
    42	    bool_result = ensure_type(bool_tagged, 'bool')
    43	    print(f"Boolean result: {repr(bool_result)}, type: {type(bool_result)}")
    44	    print(f"Boolean has tag: {TrustedAsTemplate.is_tagged_on(bool_result)}")
    45	    
    46	    # Test integer conversion
    47	    print("\nTesting integer conversion...")
    48	    int_tagged = AnsibleTagHelper.tag("42", TrustedAsTemplate())
    49	    int_result = ensure_type(int_tagged, 'int')
    50	    print(f"Integer result: {repr(int_result)}, type: {type(int_result)}")
    51	    print(f"Integer has tag: {TrustedAsTemplate.is_tagged_on(int_result)}")
    52	    
    53	    # Test with YAML list input  
    54	    print("\nTesting YAML list input...")
    55	    yaml_list = ["item1", "item2", "item3"]
    56	    # Tag the list itself
    57	    tagged_list = AnsibleTagHelper.tag(yaml_list, TrustedAsTemplate())
    58	    list_result = ensure_type(tagged_list, 'list')
    59	    print(f"List result: {repr(list_result)}")
    60	    print(f"List has tag: {TrustedAsTemplate.is_tagged_on(list_result)}")
    61	    
    62	    if isinstance(list_result, list):
    63	        for i, item in enumerate(list_result):
    64	            has_tag = TrustedAsTemplate.is_tagged_on(item)
    65	            print(f"List item {i}: {repr(item)}, has tag: {has_tag}")
    66	    
    67	    # Test string coercion from different types
    68	    print("\nTesting string coercion...")
    69	    int_value = AnsibleTagHelper.tag(42, TrustedAsTemplate())
    70	    str_result = ensure_type(int_value, 'str')
    71	    print(f"String from int: {repr(str_result)}, has tag: {TrustedAsTemplate.is_tagged_on(str_result)}")
    72	    
    73	    bool_value = AnsibleTagHelper.tag(True, TrustedAsTemplate())
    74	    str_result2 = ensure_type(bool_value, 'str')
    75	    print(f"String from bool: {repr(str_result2)}, has tag: {TrustedAsTemplate.is_tagged_on(str_result2)}")
    76	
    77	if __name__ == "__main__":
    78	    test_ensure_type_tag_propagation()
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 65] [user]
Observation: 

Testing tag propagation in ensure_type...
Original value: 'test,value,list'
Tagged value: 'test,value,list'
Has TrustedAsTemplate tag: True
Converted to list: ['test', 'value', 'list']
Result type: <class 'list'>
Result is list: True
Item 0: 'test', has tag: False
ERROR: Item 0 lost its trust tag!
Item 1: 'value', has tag: False
ERROR: Item 1 lost its trust tag!
Item 2: 'list', has tag: False
ERROR: Item 2 lost its trust tag!

Testing boolean conversion...
Boolean result: True, type: <class 'bool'>
Boolean has tag: False

Testing integer conversion...
Integer result: 42, type: <class 'int'>
Integer has tag: False

Testing YAML list input...
List result: ['item1', 'item2', 'item3']
List has tag: True
List item 0: 'item1', has tag: False
List item 1: 'item2', has tag: False
List item 2: 'item3', has tag: False

Testing string coercion...
String from int: '42', has tag: False
String from bool: 'True', has tag: False






[MSG 66] [user]
Observation: 

Here's the result of running `cat -n` on /app/lib/ansible/module_utils/parsing/convert_bool.py:
     1	# Copyright: 2017, Ansible Project
     2	# Simplified BSD License (see licenses/simplified_bsd.txt or https://opensource.org/licenses/BSD-2-Clause )
     3	
     4	from __future__ import annotations
     5	
     6	from ansible.module_utils.six import binary_type, text_type
     7	from ansible.module_utils.common.text.converters import to_text
     8	
     9	
    10	BOOLEANS_TRUE = frozenset(('y', 'yes', 'on', '1', 'true', 't', 1, 1.0, True))
    11	BOOLEANS_FALSE = frozenset(('n', 'no', 'off', '0', 'false', 'f', 0, 0.0, False))
    12	BOOLEANS = BOOLEANS_TRUE.union(BOOLEANS_FALSE)
    13	
    14	
    15	def boolean(value, strict=True):
    16	    if isinstance(value, bool):
    17	        return value
    18	
    19	    normalized_value = value
    20	    if isinstance(value, (text_type, binary_type)):
    21	        normalized_value = to_text(value, errors='surrogate_or_strict').lower().strip()
    22	
    23	    if normalized_value in BOOLEANS_TRUE:
    24	        return True
    25	    elif normalized_value in BOOLEANS_FALSE or not strict:
    26	        return False
    27	
    28	    raise TypeError("The value '%s' is not a valid boolean. Valid booleans include: %s" % (to_text(value), ', '.join(repr(i) for i in BOOLEANS)))
    29	







[MSG 67] [assistant]
Perfect! Now I can see the issue. The `ensure_type` function is not propagating tags properly. Based on the PR description, I need to modify the `ensure_type` function to:

1. Propagate tags from the original value to the converted value
2. Handle tag propagation for lists (propagate to each item)
3. Handle type coercion while preserving tags

Let me first look at how the `convert_bool.boolean` function works, as the PR mentions issues with it:

[MSG 68] [user]
Observation: 

























































File created successfully at: /app/test_boolean_issue.py






[MSG 69] [assistant]
According to the PR description, I need to fix the issue where "The `convert_bool.boolean` function should return `False` or raise `TypeError` for unhashable inputs, rather than raising `ValueError` due to invalid set membership checks."

Let me check if that's a current issue:

[MSG 70] [user]
Observation: 

Exception for empty dict: TypeError: unhashable type: 'dict'
Exception for empty list: TypeError: unhashable type: 'list'






[MSG 71] [user]
Observation: 

Here's the result of running `cat -n` on /app/lib/ansible/config/manager.py:
    69	def ensure_type(value, value_type, origin=None, origin_ftype=None):
    70	    """ return a configuration variable with casting
    71	    :arg value: The value to ensure correct typing of
    72	    :kwarg value_type: The type of the value.  This can be any of the following strings:
    73	        :boolean: sets the value to a True or False value
    74	        :bool: Same as 'boolean'
    75	        :integer: Sets the value to an integer or raises a ValueType error
    76	        :int: Same as 'integer'
    77	        :float: Sets the value to a float or raises a ValueType error
    78	        :list: Treats the value as a comma separated list.  Split the value
    79	            and return it as a python list.
    80	        :none: Sets the value to None
    81	        :path: Expands any environment variables and tilde's in the value.
    82	        :tmppath: Create a unique temporary directory inside of the directory
    83	            specified by value and return its path.
    84	        :temppath: Same as 'tmppath'
    85	        :tmp: Same as 'tmppath'
    86	        :pathlist: Treat the value as a typical PATH string.  (On POSIX, this
    87	            means comma separated strings.)  Split the value and then expand
    88	            each part for environment variables and tildes.
    89	        :pathspec: Treat the value as a PATH string. Expands any environment variables
    90	            tildes's in the value.
    91	        :str: Sets the value to string types.
    92	        :string: Same as 'str'
    93	    """
    94	
    95	    errmsg = ''
    96	    basedir = None
    97	    if origin and os.path.isabs(origin) and os.path.exists(to_bytes(origin)):
    98	        basedir = origin
    99	
   100	    if value_type:
   101	        value_type = value_type.lower()
   102	
   103	    if value is not None:
   104	        if value_type in ('boolean', 'bool'):
   105	            value = boolean(value, strict=False)
   106	
   107	        elif value_type in ('integer', 'int'):
   108	            if not isinstance(value, int):
   109	                try:
   110	                    if (decimal_value := decimal.Decimal(value)) == (int_part := int(decimal_value)):
   111	                        value = int_part
   112	                    else:
   113	                        errmsg = 'int'
   114	                except decimal.DecimalException:
   115	                    errmsg = 'int'
   116	
   117	        elif value_type == 'float':
   118	            if not isinstance(value, float):
   119	                value = float(value)
   120	
   121	        elif value_type == 'list':
   122	            if isinstance(value, string_types):
   123	                value = [unquote(x.strip()) for x in value.split(',')]
   124	            elif not isinstance(value, Sequence):
   125	                errmsg = 'list'
   126	
   127	        elif value_type == 'none':
   128	            if value == "None":
   129	                value = None
   130	
   131	            if value is not None:
   132	                errmsg = 'None'
   133	
   134	        elif value_type == 'path':
   135	            if isinstance(value, string_types):
   136	                value = resolve_path(value, basedir=basedir)
   137	            else:
   138	                errmsg = 'path'
   139	
   140	        elif value_type in ('tmp', 'temppath', 'tmppath'):
   141	            if isinstance(value, string_types):
   142	                value = resolve_path(value, basedir=basedir)
   143	                if not os.path.exists(value):
   144	                    makedirs_safe(value, 0o700)
   145	                prefix = 'ansible-local-%s' % os.getpid()
   146	                value = tempfile.mkdtemp(prefix=prefix, dir=value)
   147	                atexit.register(cleanup_tmp_file, value, warn=True)
   148	            else:
   149	                errmsg = 'temppath'
   150	
   151	        elif value_type == 'pathspec':
   152	            if isinstance(value, string_types):
   153	                value = value.split(os.pathsep)
   154	
   155	            if isinstance(value, Sequence):
   156	                value = [resolve_path(x, basedir=basedir) for x in value]
   157	            else:
   158	                errmsg = 'pathspec'
   159	
   160	        elif value_type == 'pathlist':
   161	            if isinstance(value, string_types):
   162	                value = [x.strip() for x in value.split(',')]
   163	
   164	            if isinstance(value, Sequence):
   165	                value = [resolve_path(x, basedir=basedir) for x in value]
   166	            else:
   167	                errmsg = 'pathlist'
   168	
   169	        elif value_type in ('dict', 'dictionary'):
   170	            if not isinstance(value, Mapping):
   171	                errmsg = 'dictionary'
   172	
   173	        elif value_type in ('str', 'string'):
   174	            if isinstance(value, (string_types, bool, int, float, complex)):
   175	                value = to_text(value, errors='surrogate_or_strict')
   176	                if origin_ftype and origin_ftype == 'ini':
   177	                    value = unquote(value)
   178	            else:
   179	                errmsg = 'string'
   180	
   181	        # defaults to string type
   182	        elif isinstance(value, (string_types)):
   183	            value = to_text(value, errors='surrogate_or_strict')
   184	            if origin_ftype and origin_ftype == 'ini':
   185	                value = unquote(value)
   186	
   187	        if errmsg:
   188	            raise ValueError(f'Invalid type provided for {errmsg!r}: {value!r}')
   189	
   190	    return to_text(value, errors='surrogate_or_strict', nonstring='passthru')
   191	







[MSG 72] [assistant]
Good, so the boolean function is raising TypeError as expected for unhashable types, not ValueError. So the issue might be somewhere else or already fixed.

Now let me look at the key issue: tag propagation in `ensure_type`. Let me analyze the existing code and see what needs to be changed:

[MSG 73] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **ALL AGENTS FAIL** (14 runs, 0 pass) — strong contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CLEAN
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 19:47:51

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | None |
| Confidence | 0.94 |
| **Verdict** | **CLEAN** |

**Agent approach**: The agent inspected `ansible.config.manager.ensure_type`, the bool conversion helper, and the datatag machinery, then wrote small repro scripts to confirm that tags were dropped during conversions and to probe unhashable-bool behavior. It never progressed to an implementation patch before autosubmission.

**Contamination evidence**: None

**Difficulty evidence**: None

**Full reasoning**: This looks clean. The failing F2P tests are behavior-level checks directly supported by the problem statement: unhashable inputs to `ensure_type(..., 'bool')` should not explode, sequences should convert to `list`, mappings should convert to `dict`, and tags should be preserved across type conversion. The tests call the public `ensure_type` API and assert on returned values/tags, not on internal helper names, exact implementation structure, or gold-patch-specific architecture. Although the full added test file contains some more specific coverage, the actual fail-to-pass subset here is tightly aligned with the stated bug report. In the trajectory, the agent clearly identified the relevant code, reproduced the tag-loss bug, and explored the datatag API, but stalled and was autosubmitted without a patch. That points to failure from not finishing the implementation, not from hidden or undiscoverable test requirements.
