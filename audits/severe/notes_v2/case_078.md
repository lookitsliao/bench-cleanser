# Case #78 Re-Audit Notes (v2)

**Instance**: `instance_ansible__ansible-3889ddeb4b780ab4bac9ca2e75f8c1991bcabe83-v0f01c69f1e2528b935359cfe578530722bca2c59`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"## Title: iptables - added a chain_management parameter to control chain\n\n## Description\n\nI’m managing custom IPtables chains with Ansible-core from the devel branch on GitHub. Implementing chain creation and deletion would be helpful for users of Ansible-core as there’s currently no direct support for managing user-defined chains in the iptables module. This would simplify automating advanced firewall setups and ensure idempotency in playbooks.\n\nCurrently, the iptables module lacks built...

**Type**: python | **Repo**: ansible/ansible
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 2 |
| Gold patch files | 2 |
| Gold patch size | 4734 chars |
| Test patch size | 15836 chars |
| Test patch files | 10 |
| F2P tests | 8 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
test/integration/targets/iptables/aliases
test/integration/targets/iptables/tasks/chain_management.yml
test/integration/targets/iptables/tasks/main.yml
test/integration/targets/iptables/vars/alpine.yml
test/integration/targets/iptables/vars/centos.yml
test/integration/targets/iptables/vars/default.yml
test/integration/targets/iptables/vars/fedora.yml
test/integration/targets/iptables/vars/redhat.yml
test/integration/targets/iptables/vars/suse.yml
test/units/modules/test_iptables.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard d5a740ddca57ed344d1d023383d4aff563657424
git clean -fd 
git checkout d5a740ddca57ed344d1d023383d4aff563657424 
git checkout 3889ddeb4b780ab4bac9ca2e75f8c1991bcabe83 -- test/integration/targets/iptables/aliases test/integration/targets/iptables/tasks/chain_management.yml test/integration/targets/iptables/tasks/main.yml test/integration/targets/iptables/vars/alpine.yml test/integration/targets/iptables/vars/centos.yml test/integration/targets/iptables/vars/default.yml test/integra
```

## 3. Trajectory Evidence

### Resolution Rate: 0/13 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 45 |
| Claude Sonnet 4 - paper | FAIL | 19 |
| Gemini 2.5 Pro Preview - paper | FAIL | 27 |
| GPT-5 High - paper | FAIL | 34 |
| GPT OSS - paper | FAIL | 45 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 82 |
| Claude 4 Sonnet - 10132025 | FAIL | 74 |
| GPT-5 - 10132025 | FAIL | 129 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 163 |
| GPT-5 Codex -- debug-oct22 | FAIL | 58 |
| GLM-4.5 -- 10222025 | FAIL | 60 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 73 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 75
- **Total tokens**: ~21176
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
/app/requirements.txt
/app/setup.py
/app/examples
/app/examples/ansible.cfg
/app/examples/hosts
/app/examples/hosts.yaml
/app/examples/inventory_script_schema.json
/app/examples/scripts
/app/examples/DOCUMENTATION.yml
/app/examples/hosts.yml
/app/examples/play.yml
/app/examples/plugin_filters.yml
/app/bin
/app/bin/ansible-galaxy
/app/bin/ansible-test
/app/bin/ansible-inventory
/app/bin/ansible-doc
/app/bin/ansible-connection
/app/bin/ansible-console
/app/bin/ansible-pull
/app/bin/ansible-vault
/app/bin/ansible
/app/bin/ansible-playbook
/app/bin/ansible-config
/app/setup.cfg
/app/Makefile
/app/README.rst
/app/docs
/app/docs/docsite
/app/docs/templates
/app/docs/man
/app/docs/bin
/app/lib
/app/lib/ansible_core.egg-info
/app/lib/ansible
/app/test
/app/test/sanity
/app/test/ansible_test
/app/test/utils
/app/test/units
/app/test/support
/app/test/integration
/app/test/lib
/app/changelogs
/app/changelogs/CHANGELOG.rst
/app/changelogs/changelog.yaml
/app/changelogs/fragments
/app/changelogs/config.yaml
/app/hacking
/app/hacking/backport
/app/hacking/README.md
/app/hacking/build_library
/app/hacking/fix_test_syntax.py
/app/hacking/build-ansible.py
/app/hacking/ansible-profile
/app/hacking/test-module
/app/hacking/env-setup.fish
/app/hacking/report.py
/app/hacking/test-module.py
/app/hacking/get_library.py
/app/hacking/ticket_stubs
/app/hacking/tests
/app/hacking/return_skeleton_generator.py
/app/hacking/deprecated_issue_template.md
/app/hacking/azp
/app/hacking/update-sanity-requirements.py
/app/hacking/env-setup
/app/licenses
/app/licenses/MIT-license.txt
/app/licenses/Apache-License.txt
/app/licenses/simplified_bsd.txt
/app/licenses/PSF-license.txt
/app/MANIFEST.in
/app/packaging
/app/packaging/sdist
/app/packaging/release
/app/COPYING
/app/pyproject.toml








[MSG 1] [assistant]
I'll help you implement the necessary changes to add chain management functionality to the iptables module. Let's start by exploring the repository structure and understanding the current implementation.

[MSG 2] [user]
Observation: 

/app/lib/ansible/modules/iptables.py
/app/test/units/modules/test_iptables.py






[MSG 3] [assistant]
Let me look for the iptables module in the Ansible library:

[MSG 4] [user]
Observation: 

<NOTE>This file is too large to display entirely. Showing abbreviated version. Please use `str_replace_editor view` with the `view_range` parameter to show selected lines next.</NOTE>
     1 # -*- coding: utf-8 -*-
     2 
     3 # Copyright: (c) 2015, Linus Unnebäck <linus@folkdatorn.se>
     4 # Copyright: (c) 2017, Sébastien DA ROCHA <sebastien@da-rocha.net>
     5 # GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
     6 
     7 from __future__ import absolute_import, division, print_function
     8 __metaclass__ = type
     9 
    10 
    11 DOCUMENTATION = r'''
    12 ---
    13 module: iptables
    14 short_description: Modify iptables rules
    15 version_added: "2.0"
    16 author:
    17 - Linus Unnebäck (@LinusU) <linus@folkdatorn.se>
    18 - Sébastien DA ROCHA (@sebastiendarocha)
    19 description:
    20   - C(iptables) is used to set up, maintain, and inspect the tables of IP packet
    21     filter rules in the Linux kernel.
    22   - This module does not handle the saving and/or loading of rules, but rather
    23     only manipulates the current rules that are present in memory. This is the
    24     same as the behaviour of the C(iptables) and C(ip6tables) command which
    25     this module uses internally.
    26 extends_documentation_fragment: action_common_attributes
    27 attributes:
    28     check_mode:
    29         support: full
    30     diff_mode:
    31         support: none
    32     platform:
    33         platforms: linux
    34 notes:
    35   - This module just deals with individual rules. If you need advanced
    36     chaining of rules the recommended way is to template the iptables restore
    37     file.
    38 options:
    39   table:
    40     description:
    41       - This option specifies the packet matching table which the command should operate on.
    42       - If the kernel is configured with automatic module loading, an attempt will be made
    43          to load the appropriate module for that table if it is not already there.
    44     type: str
    45     choices: [ filter, nat, mangle, raw, security ]
    46     default: filter
    47   state:
    48     description:
    49       - Whether the rule should be absent or present.
    50     type: str
    51     choices: [ absent, present ]
    52     default: present
    53   action:
    54     description:
    55       - Whether the rule should be appended at the bottom or inserted at the top.
    56       - If the rule already exists the chain will not be modified.
    57     type: str
    58     choices: [ append, insert ]
    59     default: append
    60     version_added: "2.2"
    61   rule_num:
    62     description:
    63       - Insert the rule as the given rule number.
    64       - This works only with C(action=insert).
    65     type: str
    66     version_added: "2.5"
    67   ip_version:
    68     description:
    69       - Which version of the IP protocol this rule should apply to.
    70     type: str
    71     choices: [ ipv4, ipv6 ]
    72     default: ipv4
    73   chain:
    74     description:
    75       - Specify the iptables chain to modify.
    76       - This could be a user-defined chain or one of the standard iptables chains, like
    77         C(INPUT), C(FORWARD), C(OUTPUT), C(PREROUTING), C(POSTROUTING), C(SECMARK) or C(CONNSECMARK).
    78     type: str
    79   protocol:
    80     description:
    81       - The protocol of the rule or of the packet to check.
    82       - The specified protocol can be one of C(tcp), C(udp), C(udplite), C(icmp), C(ipv6-icmp) or C(icmpv6),
    83         C(esp), C(ah), C(sctp) or the special keyword C(all), or it can be a numeric value,
    84         representing one of these protocols or a different one.
    85       - A protocol name from I(/etc/protocols) is also allowed.
    86       - A C(!) argument before the protocol inverts the test.
    87       - The number zero is equivalent to all.
    88       - C(all) will match with all protocols and is taken as default when this option is omitted.
    89     type: str
    90   source:
    91     description:
    92       - Source specification.
    93       - Address can be either a network name, a hostname, a network IP address
    94         (with /mask), or a plain IP address.
    95       - Hostnames will be resolved once only, before the rule is submitted to
    96         the kernel. Please note that specifying any name to be resolved with
    97         a remote query such as DNS is a really bad idea.
    98       - The mask can be either a network mask or a plain number, specifying
    99         the number of 1's at the left side of the network mask. Thus, a mask
   100         of 24 is equivalent to 255.255.255.0. A C(!) argument before the
   101         address specification inverts the sense of the address.
   102     type: str
   103   destination:
   104     description:
   105       - Destination specification.
   106       - Address can be either a network name, a hostname, a network IP address
   107         (with /mask), or a plain IP address.
   108       - Hostnames will be resolved once only, before the rule is submitted to
   109         the kernel. Please note that specifying any name to be resolved with
   110         a remote query such as DNS is a really bad idea.
   111       - The mask can be either a network mask or a plain number, specifying
   112         the number of 1's at the left side of the network mask. Thus, a mask
   113         of 24 is equivalent to 255.255.255.0. A C(!) argument before the
   114         
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```














































































































































































File created successfully at: /app/debug_fail_json.py






[MSG 52] [assistant]
The chain_has_rules function is working correctly. The issue seems to be that our mock isn't set up properly for the fail_json scenario. Let me check our test more carefully and fix the mock setup:

[MSG 53] [user]
Observation: 

=== Debugging chain deletion with rules ===
SUCCESS: fail_json was called as expected: fail_json called: Cannot delete chain CHAINWITHRULES: chain has rules. Remove rules first.
Test result: PASSED






[MSG 54] [user]
Observation: 















































































































































The file /app/test_edge_cases.py has been edited. Here's the result of running `cat -n` on a snippet of /app/test_edge_cases.py:
   124	                assert len(mock_module.run_command.call_args_list) == 1
   125	                print("Chain management check mode (create): PASSED")
   126	            except SystemExit:
   127	                print("Chain management check mode (create): PASSED")
   128	
   129	def test_chain_deletion_with_rules():
   130	    """Test that chain deletion fails when chain has rules"""
   131	    print("\n=== Testing chain deletion with rules ===")
   132	    
   133	    with patch('ansible.modules.iptables.AnsibleModule') as mock_ansible_module:
   134	        mock_module = create_mock_module(
   135	            chain_management=True, 
   136	            state='absent', 
   137	            chain='CHAINWITHRULES'
   138	        )
   139	        mock_ansible_module.return_value = mock_module
   140	        
   141	        # Set up the side_effect to return different results for different calls
   142	        def run_command_side_effect(cmd, check_rc=False):
   143	            if '-L' in cmd and len(cmd) == 5:  # chain_exists call
   144	                return (0, 'Chain CHAINWITHRULES (policy ACCEPT)\ntarget     prot opt source               destination', '')
   145	            elif '-L' in cmd and '--line-numbers' in cmd:  # chain_has_rules call
   146	                return (0, '''Chain CHAINWITHRULES (policy ACCEPT)
   147	target     prot opt source               destination         
   148	1    ACCEPT     all  --  192.168.1.0/24      0.0.0.0/0           
   149	''', '')
   150	            else:
   151	                return (0, '', '')
   152	        
   153	        mock_module.run_command.side_effect = run_command_side_effect
   154	        
   155	        # Set up fail_json to raise an exception so we can catch it
   156	        def fail_json_side_effect(msg):
   157	            raise Exception(f"fail_json called: {msg}")
   158	        
   159	        mock_module.fail_json.side_effect = fail_json_side_effect
   160	        
   161	        with patch('ansible.modules.iptables.get_iptables_version', return_value='1.8.2'):
   162	            try:
   163	                iptables.main()
   164	                # Should not reach here - should fail
   165	                assert False, "Should have failed when trying to delete chain with rules"
   166	            except Exception as e:
   167	                if "fail_json called" in str(e):
   168	                    print("Chain deletion with rules failed as expected: PASSED")
   169	                else:
   170	                    raise e
   171	
   172	def test_different_tables():
   173	    """Test chain management works with different tables"""
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 55] [assistant]
Great! The functionality is working correctly. The issue was with our test setup. Now let me fix the original edge case test:

[MSG 56] [user]
Observation: 

=== Testing regular rule operations still work ===
Regular rule operations still work: PASSED

=== Testing chain management in check mode ===
Chain management check mode (create): PASSED

=== Testing chain deletion with rules ===
Chain deletion with rules failed as expected: PASSED

=== Testing different tables ===
Different tables test: PASSED

=== Testing idempotency ===
Idempotency (create existing chain): PASSED

=== Testing IPv6 support ===
IPv6 support test: PASSED

=== All edge case tests passed! ===






[MSG 57] [user]
Observation: 

Parameter `file_text` is required for command: create






[MSG 58] [assistant]
Excellent! All our edge case tests are now passing. Now let me create one final comprehensive test that simulates real-world usage scenarios:

[MSG 59] [user]
Observation: 

Parameter `file_text` is required for command: create






[MSG 60] [user]
Observation: 

Parameter `file_text` is required for command: create






[MSG 61] [user]
Observation: 

Parameter `file_text` is required for command: create






[MSG 62] [user]
Observation: 

Parameter `file_text` is required for command: create






[MSG 63] [user]
Observation: 

Parameter `file_text` is required for command: create






[MSG 64] [user]
Observation: 







































































































































































































































































































































































































































































































































































































































































































































File created successfully at: /app/test_real_world_scenarios.py






[MSG 65] [assistant]
I need to provide the file_text parameter:

[MSG 66] [user]
Observation: 

Testing real-world scenarios for iptables chain management

=== Scenario 1: Create WHITELIST chain ===
✓ WHITELIST chain created successfully

=== Scenario 2: Idempotent chain creation ===
✓ Idempotent operation - no changes made

=== Scenario 3: Add rule to WHITELIST chain ===
✓ Rule added to WHITELIST chain successfully

=== Scenario 4: Delete chain with rules (should fail) ===
✓ Correctly failed to delete chain with rules

=== Scenario 5: Delete empty chain ===
✓ Empty chain deleted successfully

=== Scenario 6: Create chain in NAT table ===
✓ NAT table chain created successfully

=== Scenario 7: Chain management in check mode ===
✓ Check mode works correctly

🎉 All real-world scenarios passed successfully!

The chain_management feature is ready for production use.






[MSG 67] [user]
Observation: 

============================= test session starts ==============================
platform linux -- Python 3.11.13, pytest-6.2.5, py-1.11.0, pluggy-1.0.0 -- /usr/local/bin/python
cachedir: .pytest_cache
rootdir: /app
plugins: rerunfailures-10.2, mock-3.6.1, anyio-4.10.0
collecting ... 
collected 23 items                                                             

test/units/modules/test_iptables.py::TestIptables::test_append_rule PASSED [  4%]
test/units/modules/test_iptables.py::TestIptables::test_append_rule_check_mode PASSED [  8%]
test/units/modules/test_iptables.py::TestIptables::test_comment_position_at_end PASSED [ 13%]
test/units/modules/test_iptables.py::TestIptables::test_destination_ports PASSED [ 17%]
test/units/modules/test_iptables.py::TestIptables::test_flush_table_check_true PASSED [ 21%]
test/units/modules/test_iptables.py::TestIptables::test_flush_table_without_chain PASSED [ 26%]
test/units/modules/test_iptables.py::TestIptables::test_insert_jump_reject_with_reject PASSED [ 30%]
test/units/modules/test_iptables.py::TestIptables::test_insert_rule PASSED [ 34%]
test/units/modules/test_iptables.py::TestIptables::test_insert_rule_change_false PASSED [ 39%]
test/units/modules/test_iptables.py::TestIptables::test_insert_rule_with_wait PASSED [ 43%]
test/units/modules/test_iptables.py::TestIptables::test_insert_with_reject PASSED [ 47%]
test/units/modules/test_iptables.py::TestIptables::test_iprange PASSED   [ 52%]
test/units/modules/test_iptables.py::TestIptables::test_jump_tee_gateway PASSED [ 56%]
test/units/modules/test_iptables.py::TestIptables::test_jump_tee_gateway_negative PASSED [ 60%]
test/units/modules/test_iptables.py::TestIptables::test_log_level PASSED [ 65%]
test/units/modules/test_iptables.py::TestIptables::test_match_set PASSED [ 69%]
test/units/modules/test_iptables.py::TestIptables::test_policy_table PASSED [ 73%]
test/units/modules/test_iptables.py::TestIptables::test_policy_table_changed_false PASSED [ 78%]
test/units/modules/test_iptables.py::TestIptables::test_policy_table_no_change PASSED [ 82%]
test/units/modules/test_iptables.py::TestIptables::test_remove_rule PASSED [ 86%]
test/units/modules/test_iptables.py::TestIptables::test_remove_rule_check_mode PASSED [ 91%]
test/units/modules/test_iptables.py::TestIptables::test_tcp_flags PASSED [ 95%]
test/units/modules/test_iptables.py::TestIptables::test_without_required_parameters PASSED [100%]

============================== 23 passed in 0.13s ==============================






[MSG 68] [assistant]
Perfect! All scenarios are working correctly. Let me also run the original tests one more time to ensure we haven't broken anything:

[MSG 69] [user]
Observation: 

501-    table: nat
502-    chain: '{{ item }}'
503-    flush: yes
504-  with_items: [ 'INPUT', 'OUTPUT', 'PREROUTING', 'POSTROUTING' ]
505-
506:- name: Log packets arriving into an user-defined chain
507-  ansible.builtin.iptables:
508-    chain: LOGGING
509-    action: append
510-    state: present
511-    limit: 2/second






[MSG 70] [assistant]
Excellent! Let me also add some example usage to the documentation section to show users how to use the new feature:

[MSG 71] [user]
Observation: 

Here's the result of running `cat -n` on /app/lib/ansible/modules/iptables.py:
   515	
   516	- name: Allow connections on multiple ports
   517	  ansible.builtin.iptables:
   518	    chain: INPUT
   519	    protocol: tcp
   520	    destination_ports:
   521	      - "80"
   522	      - "443"
   523	      - "8081:8083"
   524	    jump: ACCEPT
   525	'''
   526	
   527	import re
   528	
   529	from ansible.module_utils.compat.version import LooseVersion
   530	







[MSG 72] [assistant]
Let me add some example usage for the new chain_management feature to the examples section:

[MSG 73] [user]
Observation: 









































































The file /app/lib/ansible/modules/iptables.py has been edited. Here's the result of running `cat -n` on a snippet of /app/lib/ansible/modules/iptables.py:
   511	    limit: 2/second
   512	    limit_burst: 20
   513	    log_prefix: "IPTABLES:INFO: "
   514	    log_level: info
   515	
   516	- name: Allow connections on multiple ports
   517	  ansible.builtin.iptables:
   518	    chain: INPUT
   519	    protocol: tcp
   520	    destination_ports:
   521	      - "80"
   522	      - "443"
   523	      - "8081:8083"
   524	    jump: ACCEPT
   525	
   526	- name: Create a custom chain
   527	  ansible.builtin.iptables:
   528	    chain: WHITELIST
   529	    chain_management: true
   530	    state: present
   531	
   532	- name: Add rule to custom chain
   533	  ansible.builtin.iptables:
   534	    chain: WHITELIST
   535	    source: 192.168.1.0/24
   536	    jump: ACCEPT
   537	
   538	- name: Delete custom chain (only if empty)
   539	  ansible.builtin.iptables:
   540	    chain: WHITELIST
   541	    chain_management: true
   542	    state: absent
   543	'''
   544	
   545	import re
   546	
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 74] [user]
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
**Analyzed**: 2026-04-12 20:33:36

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | True |
| Failure reason | contamination |
| Contamination type | test_coupling |
| Confidence | 0.97 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent added a new `chain_management` boolean parameter, documented it, implemented helper functions to detect/create/delete chains, and changed `main()` to create a chain on `state=present` and delete it on `state=absent` with check-mode/idempotency handling. It also validated the behavior with custom tests and edge-case scripts.

**Contamination evidence**: The F2P unit tests are coupled to the gold patch's exact internal command sequence rather than the stated feature. For ordinary rule operations (`test_append_rule`, `test_insert_rule`, and check-mode variants), they now require an extra internal `-L <chain>` existence check and specific `run_command` call counts/indexes, even though the problem statement only asks for chain creation/deletion support. More severely, `test_chain_creation` requires the sequence `-C FOOBAR`, `-L FOOBAR`, `-N FOOBAR`, and then `-A FOOBAR` for a pure chain-creation request with no rule fields. Appending an empty rule is not stated or reasonably inferable from the issue description; a correct implementation could simply check existence and run `-N`. The agent's implementation does exactly that kind of sensible separate chain-management flow, so it would solve the requested feature but still fail these tests.

**Difficulty evidence**: None

**Full reasoning**: This looks clearly contaminated rather than merely difficult. The problem statement is straightforward: add a `chain_management` parameter so the `iptables` module can create and delete user-defined chains idempotently. The agent understood that and implemented a reasonable solution: new parameter, helpers for chain existence/create/delete, check mode, and deletion logic. The problem is that the F2P tests do not just validate externally visible behavior; they assert on the gold patch's internal control flow and exact `run_command` calls. Existing append/insert tests were altered to require an additional chain-existence probe for normal rule management, which is not part of the spec. The new chain-creation unit tests are even more revealing: they expect a pure chain-creation invocation to end with an `iptables -A FOOBAR` call, an implementation artifact of the gold patch rather than a natural or spec-derived requirement. So an agent can correctly implement chain creation/deletion and still fail because it didn't mirror the gold patch's internals. The agent's trajectory reinforces this: it built a separate chain-management branch that matches the user-facing request and verified it with realistic custom tests, but that approach would be rejected by these tightly coupled F2P tests.
