# Case #52 Re-Audit Notes (v2)

**Instance**: `instance_ansible__ansible-489156378c8e97374a75a544c7c9c2c0dd8146d1-v390e508d27db7a51eece36bb6d9698b63a5b638a`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)



# Meraki modules fail immediately on HTTP 429/500/502 responses from the Meraki API 

# Summary 

When Meraki modules interact with the Meraki API and the service returns HTTP 429 (rate limited) or transient server errors (HTTP 500/502), playbook tasks stop with an error right away. There is no built-in retry or graceful handling, which reduces reliability for workflows that issue bursts of calls or encounter temporary API issues. 

# Steps to Reproduce 

1. Run a play that triggers multiple M...

**Type**: python | **Repo**: ansible/ansible
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 3 |
| Gold patch files | 3 |
| Gold patch size | 6939 chars |
| Test patch size | 2920 chars |
| Test patch files | 1 |
| F2P tests | 3 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
test/units/module_utils/network/meraki/test_meraki.py
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 5ee81338fcf7adbc1a8eda26dd8105a07825cb08
git clean -fd 
git checkout 5ee81338fcf7adbc1a8eda26dd8105a07825cb08 
git checkout 489156378c8e97374a75a544c7c9c2c0dd8146d1 -- test/units/module_utils/network/meraki/test_meraki.py
```

## 3. Trajectory Evidence

### Resolution Rate: 8/12 (67%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 27 |
| Gemini 2.5 Pro Preview - paper | FAIL | 24 |
| GPT-5 High - paper | PASS | 45 |
| GPT OSS - paper | PASS | 44 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | PASS | 92 |
| Claude 4 Sonnet - 10132025 | PASS | 54 |
| GPT-5 - 10132025 | PASS | 38 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 32 |
| GPT-5 Codex -- debug-oct22 | PASS | 198 |
| GLM-4.5 -- 10222025 | PASS | 40 |
| Claude 4.5 Haiku -- 10222025 | PASS | 92 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 47
- **Total tokens**: ~38581
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
/app/CODING_GUIDELINES.md
/app/packaging
/app/packaging/debian
/app/packaging/arch
/app/packaging/release
/app/packaging/macports
/app/packaging/requirements
/app/packaging/sdist
/app/packaging/rpm
/app/packaging/gentoo
/app/contrib
/app/contrib/README.md
/app/contrib/inventory
/app/contrib/vault
/app/licenses
/app/licenses/Apache-License.txt
/app/licenses/PSF-license.txt
/app/licenses/MIT-license.txt
/app/licenses/simplified_bsd.txt
/app/README.rst
/app/lib
/app/lib/ansible.egg-info
/app/lib/ansible
/app/requirements.txt
/app/bin
/app/bin/ansible-inventory
/app/bin/ansible-playbook
/app/bin/ansible-console
/app/bin/ansible-pull
/app/bin/ansible
/app/bin/ansible-test
/app/bin/ansible-galaxy
/app/bin/ansible-vault
/app/bin/ansible-connection
/app/bin/ansible-config
/app/bin/ansible-doc
/app/setup.py
/app/MANIFEST.in
/app/COPYING
/app/examples
/app/examples/inventory_script_schema.json
/app/examples/scripts
/app/examples/DOCUMENTATION.yml
/app/examples/plugin_filters.yml
/app/examples/hosts.yaml
/app/examples/ansible.cfg
/app/examples/hosts.yml
/app/examples/playbooks
/app/examples/hosts
/app/hacking
/app/hacking/cgroup_perf_recap_graph.py
/app/hacking/metadata-tool.py
/app/hacking/report.py
/app/hacking/build_library
/app/hacking/README.md
/app/hacking/env-setup
/app/hacking/aws_config
/app/hacking/tests
/app/hacking/ansible-profile
/app/hacking/test-module.py
/app/hacking/create_deprecated_issues.py
/app/hacking/build-ansible.py
/app/hacking/return_skeleton_generator.py
/app/hacking/deprecated_issue_template.md
/app/hacking/test-module
/app/hacking/env-setup.fish
/app/hacking/fix_test_syntax.py
/app/hacking/get_library.py
/app/hacking/ticket_stubs
/app/shippable.yml
/app/MODULE_GUIDELINES.md
/app/changelogs
/app/changelogs/config.yaml
/app/changelogs/CHANGELOG.rst
/app/changelogs/fragments
/app/test
/app/test/utils
/app/test/results
/app/test/ansible_test
/app/test/sanity
/app/test/integration
/app/test/lib
/app/test/units
/app/test/legacy
/app/test/cache
/app/docs
/app/docs/bin
/app/docs/man
/app/docs/templates
/app/docs/docsite
/app/Makefile
/app/SYMLINK_CACHE.json








[MSG 1] [assistant]
I'll help you implement the necessary changes to meet the requirements for improved error handling in the Meraki API rate limiting and server errors. Let's start by exploring the repository structure to understand the codebase.

[MSG 2] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app/lib/ansible, excluding hidden items:
/app/lib/ansible
/app/lib/ansible/utils
/app/lib/ansible/utils/unsafe_proxy.py
/app/lib/ansible/utils/__init__.py
/app/lib/ansible/utils/color.py
/app/lib/ansible/utils/listify.py
/app/lib/ansible/utils/collection_loader.py
/app/lib/ansible/utils/ssh_functions.py
/app/lib/ansible/utils/vars.py
/app/lib/ansible/utils/display.py
/app/lib/ansible/utils/shlex.py
/app/lib/ansible/utils/plugin_docs.py
/app/lib/ansible/utils/hashing.py
/app/lib/ansible/utils/sentinel.py
/app/lib/ansible/utils/helpers.py
/app/lib/ansible/utils/__pycache__
/app/lib/ansible/utils/context_objects.py
/app/lib/ansible/utils/singleton.py
/app/lib/ansible/utils/py3compat.py
/app/lib/ansible/utils/path.py
/app/lib/ansible/utils/jsonrpc.py
/app/lib/ansible/utils/cmd_functions.py
/app/lib/ansible/utils/encrypt.py
/app/lib/ansible/utils/unicode.py
/app/lib/ansible/release.py
/app/lib/ansible/__pycache__
/app/lib/ansible/__pycache__/release.cpython-311.pyc
/app/lib/ansible/__pycache__/context.cpython-311.pyc
/app/lib/ansible/__pycache__/__init__.cpython-311.pyc
/app/lib/ansible/__pycache__/constants.cpython-311.pyc
/app/lib/ansible/context.py
/app/lib/ansible/template
/app/lib/ansible/template/native_helpers.py
/app/lib/ansible/template/template.py
/app/lib/ansible/template/vars.py
/app/lib/ansible/template/safe_eval.py
/app/lib/ansible/template/__init__.py
/app/lib/ansible/template/__pycache__
/app/lib/ansible/executor
/app/lib/ansible/executor/playbook_executor.py
/app/lib/ansible/executor/play_iterator.py
/app/lib/ansible/executor/action_write_locks.py
/app/lib/ansible/executor/task_queue_manager.py
/app/lib/ansible/executor/stats.py
/app/lib/ansible/executor/powershell
/app/lib/ansible/executor/discovery
/app/lib/ansible/executor/process
/app/lib/ansible/executor/__init__.py
/app/lib/ansible/executor/interpreter_discovery.py
/app/lib/ansible/executor/task_result.py
/app/lib/ansible/executor/task_executor.py
/app/lib/ansible/executor/module_common.py
/app/lib/ansible/executor/__pycache__
/app/lib/ansible/modules
/app/lib/ansible/modules/network
/app/lib/ansible/modules/net_tools
/app/lib/ansible/modules/packaging
/app/lib/ansible/modules/database
/app/lib/ansible/modules/notification
/app/lib/ansible/modules/source_control
/app/lib/ansible/modules/windows
/app/lib/ansible/modules/utilities
/app/lib/ansible/modules/web_infrastructure
/app/lib/ansible/modules/identity
/app/lib/ansible/modules/messaging
/app/lib/ansible/modules/clustering
/app/lib/ansible/modules/__init__.py
/app/lib/ansible/modules/files
/app/lib/ansible/modules/cloud
/app/lib/ansible/modules/inventory
/app/lib/ansible/modules/crypto
/app/lib/ansible/modules/remote_management
/app/lib/ansible/modules/monitoring
/app/lib/ansible/modules/__pycache__
/app/lib/ansible/modules/system
/app/lib/ansible/modules/storage
/app/lib/ansible/modules/commands
/app/lib/ansible/parsing
/app/lib/ansible/parsing/yaml
/app/lib/ansible/parsing/dataloader.py
/app/lib/ansible/parsing/quoting.py
/app/lib/ansible/parsing/ajson.py
/app/lib/ansible/parsing/plugin_docs.py
/app/lib/ansible/parsing/metadata.py
/app/lib/ansible/parsing/mod_args.py
/app/lib/ansible/parsing/splitter.py
/app/lib/ansible/parsing/__pycache__
/app/lib/ansible/parsing/utils
/app/lib/ansible/parsing/__init__.py
/app/lib/ansible/parsing/vault
/app/lib/ansible/inventory
/app/lib/ansible/inventory/data.py
/app/lib/ansible/inventory/helpers.py
/app/lib/ansible/inventory/manager.py
/app/lib/ansible/inventory/__init__.py
/app/lib/ansible/inventory/host.py
/app/lib/ansible/inventory/group.py
/app/lib/ansible/inventory/__pycache__
/app/lib/ansible/playbook
/app/lib/ansible/playbook/helpers.py
/app/lib/ansible/playbook/handler.py
/app/lib/ansible/playbook/__init__.py
/app/lib/ansible/playbook/block.py
/app/lib/ansible/playbook/collectionsearch.py
/app/lib/ansible/playbook/play.py
/app/lib/ansible/playbook/included_file.py
/app/lib/ansible/playbook/__pycache__
/app/lib/ansible/playbook/play_context.py
/app/lib/ansible/playbook/conditional.py
/app/lib/ansible/playbook/handler_task_include.py
/app/lib/ansible/playbook/attribute.py
/app/lib/ansible/playbook/taggable.py
/app/lib/ansible/playbook/task_include.py
/app/lib/ansible/playbook/role
/app/lib/ansible/playbook/role_include.py
/app/lib/ansible/playbook/loop_control.py
/app/lib/ansible/playbook/base.py
/app/lib/ansible/playbook/playbook_include.py
/app/lib/ansible/playbook/task.py
/app/lib/ansible/galaxy
/app/lib/ansible/galaxy/role.py
/app/lib/ansible/galaxy/token.py
/app/lib/ansible/galaxy/__init__.py
/app/lib/ansible/galaxy/collection.py
/app/lib/ansible/galaxy/login.py
/app/lib/ansible/galaxy/data
/app/lib/ansible/galaxy/api.py
/app/lib/ansible/constants.py
/app/lib/ansible/compat
/app/lib/ansible/compat/selectors
/app/lib/ansible/compat/__init__.py
/app/lib/ansible/config
/app/lib/ansible/config/base.yml
/app/lib/ansible/config/__pycache__
/app/lib/ansible/config/__init__.py
/app/lib/ansible/config/module_defaults.yml
/app/lib/ansible/config/manager.py
/app/lib/ansible/config/data.py
/app/lib/ansible/errors
/app/lib/ansible/errors/__init__.py
/app/lib/ansible/errors/__pycache__
/app/lib/ansible/errors/yaml_strings.py
/app/lib/ansible/plugins
/app/lib/ansible/plugins/__pycache__
/app/lib/ansible/plugins/cache
/app/lib/ansible/plugins/terminal
/app/lib/ansible/plugins/loader.py
/app/lib/ansible/plugins/httpapi
/app/lib/ansible/plugins/strategy
/app/lib/ansible/plugins/
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
back=(env_fallback, ['MERAKI_KEY']), required=True),
    43	                host=dict(type='str', default='api.meraki.com'),
    44	                use_proxy=dict(type='bool', default=False),
    45	                use_https=dict(type='bool', default=True),
    46	                validate_certs=dict(type='bool', default=True),
    47	                output_format=dict(type='str', choices=['camelcase', 'snakecase'], default='snakecase', fallback=(env_fallback, ['ANSIBLE_MERAKI_FORMAT'])),
    48	                output_level=dict(type='str', default='normal', choices=['normal', 'debug']),
    49	                timeout=dict(type='int', default=30),
    50	                org_name=dict(type='str', aliases=['organization']),
    51	                org_id=dict(type='str'),
    52	                rate_limit_retry_time=dict(type='int', default=165),
    53	                internal_error_retry_time=dict(type='int', default=60),
    54	                )
    55	
    56	
    57	class MerakiModule(object):
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 36] [assistant]
Perfect! Now I can see the current behavior - the modules fail immediately when receiving HTTP 429 or 500 responses. Now let me implement the solution.

According to the PR description, I need to:

1. Add two new parameters: `rate_limit_retry_time` and `internal_error_retry_time`
2. Implement retry logic for HTTP 429, 500, and 502 errors
3. Use progressive backoff with multipliers
4. Default values of 165 seconds for rate limit and 60 seconds for internal errors
5. Show warning messages when retry logic is activated
6. Include retry attempt counts in warning messages

Let me start by modifying the `meraki_argument_spec` function:

[MSG 37] [user]
Observation: 



























The file /app/lib/ansible/module_utils/network/meraki/meraki.py has been edited. Here's the result of running `cat -n` on a snippet of /app/lib/ansible/module_utils/network/meraki/meraki.py:
    27	# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    28	# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    29	# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
    30	# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
    31	
    32	import os
    33	import re
    34	import time
    35	from ansible.module_utils.basic import AnsibleModule, json, env_fallback
    36	from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict
    37	from ansible.module_utils.urls import fetch_url
    38	from ansible.module_utils.six.moves.urllib.parse import urlencode
    39	from ansible.module_utils._text import to_native, to_bytes, to_text
    40	
    41	
    42	def meraki_argument_spec():
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 38] [assistant]
Now I need to add the time import at the top of the file and implement the retry logic in the `request` method:

[MSG 39] [user]
Observation: 

Here's the result of running `cat -n` on /app/lib/ansible/module_utils/network/meraki/meraki.py:
   338	            built_path += self.encode_url_params(params)
   339	        return built_path
   340	
   341	    def request(self, path, method=None, payload=None):
   342	        """Generic HTTP method for Meraki requests."""
   343	        self.path = path
   344	        self.define_protocol()
   345	
   346	        if method is not None:
   347	            self.method = method
   348	        self.url = '{protocol}://{host}/api/v0/{path}'.format(path=self.path.lstrip('/'), **self.params)
   349	        resp, info = fetch_url(self.module, self.url,
   350	                               headers=self.headers,
   351	                               data=payload,
   352	                               method=self.method,
   353	                               timeout=self.params['timeout'],
   354	                               use_proxy=self.params['use_proxy'],
   355	                               )
   356	        self.response = info['msg']
   357	        self.status = info['status']
   358	
   359	        if self.status >= 500:
   360	            self.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info))
   361	        elif self.status >= 300:
   362	            self.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info),
   363	                           body=json.loads(to_native(info['body'])))
   364	        try:
   365	            return json.loads(to_native(resp.read()))







[MSG 40] [assistant]
Now I need to completely rewrite the `request` method to implement the retry logic. Let me first check the current method again to understand the exact structure:

[MSG 41] [user]
Observation: 

Here's the result of running `cat -n` on /app/lib/ansible/module_utils/network/meraki/meraki.py:
   365	            return json.loads(to_native(resp.read()))
   366	        except Exception:
   367	            pass
   368	
   369	    def exit_json(self, **kwargs):
   370	        """Custom written method to exit from module."""







[MSG 42] [user]
Observation: 

















































































































































































































































The file /app/lib/ansible/module_utils/network/meraki/meraki.py has been edited. Here's the result of running `cat -n` on a snippet of /app/lib/ansible/module_utils/network/meraki/meraki.py:
   336	            built_path = built_path.format(org_id=org_id, net_id=net_id)
   337	        if params:
   338	            built_path += self.encode_url_params(params)
   339	        return built_path
   340	
   341	    def request(self, path, method=None, payload=None):
   342	        """Generic HTTP method for Meraki requests with retry logic."""
   343	        self.path = path
   344	        self.define_protocol()
   345	
   346	        if method is not None:
   347	            self.method = method
   348	        self.url = '{protocol}://{host}/api/v0/{path}'.format(path=self.path.lstrip('/'), **self.params)
   349	        
   350	        # Retry logic variables
   351	        rate_limit_retry_time = self.params.get('rate_limit_retry_time', 165)
   352	        internal_error_retry_time = self.params.get('internal_error_retry_time', 60)
   353	        
   354	        # Track retry attempts and timing
   355	        retry_start_time = time.time()
   356	        retry_attempt = 0
   357	        wait_time = 1  # Initial wait time in seconds
   358	        last_status = None
   359	        
   360	        while True:
   361	            resp, info = fetch_url(self.module, self.url,
   362	                                   headers=self.headers,
   363	                                   data=payload,
   364	                                   method=self.method,
   365	                                   timeout=self.params['timeout'],
   366	                                   use_proxy=self.params['use_proxy'],
   367	                                   )
   368	            self.response = info['msg']
   369	            self.status = info['status']
   370	            last_status = self.status
   371	            
   372	            # Success cases
   373	            if self.status < 300:
   374	                try:
   375	                    return json.loads(to_native(resp.read()))
   376	                except Exception:
   377	                    pass
   378	                return None
   379	            
   380	            # Determine if we should retry based on status code
   381	            should_retry = False
   382	            retry_time_limit = None
   383	            error_type = None
   384	            
   385	            if self.status == 429:  # Rate limit
   386	                should_retry = True
   387	                retry_time_limit = rate_limit_retry_time
   388	                error_type = "rate limit"
   389	            elif self.status in [500, 502]:  # Internal server errors
   390	                should_retry = True
   391	                retry_time_limit = internal_error_retry_time
   392	                error_type = "internal server error"
   393	            
   394	            # If we shouldn't retry or have no retry time configured, fail immediately
   395	            if not should_retry or retry_time_limit <= 0:
   396	                if self.status >= 500:
   397	                    self.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info))
   398	                elif self.status >= 300:
   399	                    body = None
   400	                    try:
   401	                        body = json.loads(to_native(info['body']))
   402	                    except Exception:
   403	                        pass
   404	                    self.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info),
   405	                                   body=body)
   406	            
   407	            # Check if we've exceeded the retry time limit
   408	            elapsed_time = time.time() - retry_start_time
   409	            if elapsed_time >= retry_time_limit:
   410	                # Exceeded retry time, fail with final status
   411	                if self.status >= 500:
   412	                    self.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info))
   413	                elif self.status >= 300:
   414	                    body = None
   415	                    try:
   416	                        body = json.loads(to_native(info['body']))
   417	                    except Exception:
   418	                        pass
   419	                    self.fail_json(msg='Request failed for {url}: {status} - {msg}'.format(**info),
   420	                                   body=body)
   421	            
   422	            # Increment retry attempt and warn about retry
   423	            retry_attempt += 1
   424	            if retry_attempt == 1:
   425	                # First retry, show initial warning
   426	                self.module.warn('API {0} ({1}) detected. Retrying... (attempt {2})'.format(
   427	                    error_type, self.status, retry_attempt))
   428	            else:
   429	                # Subsequent retries, show attempt count
   430	                self.module.warn('API {0} ({1}) detected. Retrying... (attempt {2})'.format(
   431	                    error_type, self.status, retry_attempt))
   432	            
   433	            # Wait before retrying with progressive backoff
   434	            time.sleep(wait_time)
   435	            wait_time = min(wait_time * 2, 30)  # Double wait time up to max of 30 seconds
   436	
   437	    def exit_json(self, **kwargs):
   438	        """Custom written method to exit from module."""
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 43] [assistant]
Now let me replace the `request` method with the new retry logic:

[MSG 44] [user]
Observation: 















































































































































































































































































































































































































































































































































































File created successfully at: /app/test_retry_logic.py






[MSG 45] [assistant]
Now let me create a test script to verify that the new retry logic works:

[MSG 46] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **HIGH RESOLUTION** (8/12 = 67%) — weak/no contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CONFIRMED_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 19:41:23

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | True |
| Failure reason | contamination |
| Contamination type | test_coupling |
| Confidence | 0.94 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent located the shared Meraki module utility, reproduced the immediate-fail behavior on 429/500 responses, and began implementing bounded retry/backoff plus new retry-time parameters directly in `lib/ansible/module_utils/network/meraki/meraki.py`.

**Contamination evidence**: The F2P tests import and require internal exception classes `HTTPError` and `RateLimitException` from `ansible.module_utils.network.meraki.meraki`, even though the problem statement never specifies any exception API or internal control-flow mechanism. A correct implementation could retry 429/500/502 and ultimately call `fail_json`, yet still fail `test_fetch_url_429` because that test insists on `pytest.raises(RateLimitException)`. Likewise, `test_fetch_url_404` requires a specific `HTTPError` on 404, but 404 handling is not part of the issue description at all. These are implementation-specific assertions, not behavior-level requirements from the spec.

**Difficulty evidence**: None

**Full reasoning**: This task shows clear contamination rather than genuine difficulty. The user-facing spec is straightforward: on Meraki HTTP 429, 500, and 502, retry for a bounded time and warn users when rate limiting occurred. The agent understood that and began implementing exactly those behaviors: adding retry-time parameters, import of `time`, and a retry loop with backoff/warnings in `request()`. However, the F2P tests do not simply verify retry semantics or eventual bounded failure. Instead, they are tightly coupled to the gold patch’s internals: they import two custom exception classes from the module utility and assert those precise exceptions are raised. That is not derivable from the problem statement. Worse, one test adds a new requirement for HTTP 404 to raise `HTTPError`, which is outside the issue scope entirely. So an agent could solve the stated problem correctly and still fail because it did not reproduce the gold patch’s exact exception architecture. The trajectory ended without a submitted patch, but the test contamination is visible directly from the test patch itself.
