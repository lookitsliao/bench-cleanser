# Case #50 Re-Audit Notes (v2)

**Instance**: `instance_gravitational__teleport-c782838c3a174fdff80cafd8cd3b1aa4dae8beb2`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"# `ClusterConfig` caching issues with Pre-v7 Remote Clusters. \n\n## Description.\n\nWhen a 6.2 leaf cluster connects to a 7.0 root, the leaf logs RBAC denials for reading `cluster_networking_config` and `cluster_audit_config`, and the root repeatedly re-inits the cache (“watcher is closed”). This happens because pre-v7 proxies do not expose the RFD-28 resources and still rely on the legacy monolithic `ClusterConfig`. The caching policy incorrectly watches the split resources for old remotes, a...

**Type**: go | **Repo**: gravitational/teleport
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 6 |
| Gold patch files | 6 |
| Gold patch size | 16040 chars |
| Test patch size | 8718 chars |
| Test patch files | 1 |
| F2P tests | 1 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
lib/cache/cache_test.go
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard d96ea00a00c897ce2fed9f8dca92ca17932d8d02
git clean -fd 
git checkout d96ea00a00c897ce2fed9f8dca92ca17932d8d02 
git checkout c782838c3a174fdff80cafd8cd3b1aa4dae8beb2 -- lib/cache/cache_test.go
```

## 3. Trajectory Evidence

### Resolution Rate: 0/14 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 46 |
| Claude Sonnet 4 - paper | FAIL | 20 |
| Gemini 2.5 Pro Preview - paper | FAIL | 24 |
| GPT-4o - paper | FAIL | 44 |
| GPT-5 High - paper | FAIL | 42 |
| GPT OSS - paper | FAIL | 44 |
| Kimi - paper | FAIL | 39 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 86 |
| Claude 4 Sonnet - 10132025 | FAIL | 109 |
| GPT-5 - 10132025 | FAIL | 81 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 46 |
| GPT-5 Codex -- debug-oct22 | FAIL | 120 |
| GLM-4.5 -- 10222025 | FAIL | 76 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 96 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 79
- **Total tokens**: ~34681
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
/app/metrics.go
/app/docs
/app/docs/preflight.md
/app/docs/img
/app/docs/pages
/app/docs/postrelease.md
/app/docs/prerelease.md
/app/docs/README.md
/app/docs/config.json
/app/docs/testplan.md
/app/CODE_OF_CONDUCT.md
/app/fixtures
/app/fixtures/assets.zip
/app/fixtures/keys
/app/fixtures/login.defs
/app/fixtures/trusted_clusters
/app/fixtures/ci-teleport-rbac
/app/fixtures/certs
/app/gravitational.asc
/app/bpf
/app/bpf/restrictedsession
/app/bpf/vmlinux.h
/app/bpf/enhancedrecording
/app/bpf/helpers.h
/app/integration
/app/integration/app_integration_test.go
/app/integration/kube_integration_test.go
/app/integration/port_forwarding_test.go
/app/integration/db_integration_test.go
/app/integration/utmp_integration_test.go
/app/integration/terminal_test.go
/app/integration/integration_test.go
/app/integration/integration.go
/app/integration/helpers.go
/app/build.assets
/app/build.assets/Makefile
/app/build.assets/rpm
/app/build.assets/Dockerfile-centos6
/app/build.assets/pam
/app/build.assets/charts
/app/build.assets/rpm-sign
/app/build.assets/Dockerfile-arm-fips
/app/build.assets/Dockerfile-arm
/app/build.assets/Dockerfile-fips
/app/build.assets/build-package.sh
/app/build.assets/Dockerfile
/app/build.assets/webapps
/app/build.assets/profile
/app/build.assets/README.md
/app/build.assets/Dockerfile-cron
/app/build.assets/locale.gen
/app/build.assets/Dockerfile-centos6-fips
/app/build.assets/install
/app/README.md
/app/docker
/app/docker/teleport-lab.yml
/app/docker/docker-compose.yml
/app/docker/README.md
/app/docker/one-proxy.yaml
/app/docker/one-node.yaml
/app/docker/env.file
/app/docker/two-role-admin.yaml
/app/docker/two-tc.yaml
/app/docker/sshd
/app/docker/two-auth.yaml
/app/docker/one.yaml
/app/docker/teleport-quickstart.yml
/app/docker/teleport
/app/docker/teleport-ent-quickstart.yml
/app/docker/Dockerfile
/app/docker/two-node.yaml
/app/docker/ansible
/app/docker/two-proxy.yaml
/app/docker/Makefile
/app/LICENSE
/app/Makefile
/app/api
/app/api/client
/app/api/types
/app/api/constants
/app/api/defaults
/app/api/utils
/app/api/go.mod
/app/api/go.sum
/app/api/identityfile
/app/api/version.go
/app/api/metadata
/app/api/profile
/app/go.mod
/app/constants.go
/app/e
/app/build
/app/build/tsh
/app/build/teleport
/app/build/tctl
/app/webassets
/app/webassets/LICENSE
/app/webassets/teleport
/app/webassets/README.md
/app/webassets/e
/app/CONTRIBUTING.md
/app/examples
/app/examples/systemd
/app/examples/go-client
/app/examples/upstart
/app/examples/gke-auth
/app/examples/etcd
/app/examples/aws
/app/examples/README.md
/app/examples/bench
/app/examples/launchd
/app/examples/jwt
/app/examples/chart
/app/examples/local-cluster
/app/examples/k8s-auth
/app/examples/resources
/app/assets
/app/assets/monitoring
/app/assets/aws
/app/tool
/app/tool/teleport
/app/tool/tctl
/app/tool/tsh
/app/lib
/app/lib/runtimeflags.go
/app/lib/events
/app/lib/asciitable
/app/lib/config
/app/lib/session
/app/lib/auth
/app/lib/multiplexer
/app/lib/system
/app/lib/services
/app/lib/backend
/app/lib/jwt
/app/lib/cache
/app/lib/shell
/app/lib/plugin
/app/lib/limiter
/app/lib/secret
/app/lib/sshca
/app/lib/client
/app/lib/pam
/app/lib/modules
/app/lib/httplib
/app/lib/teleagent
/app/lib/fixtures
/app/lib/restrictedsession
/app/lib/web
/app/lib/fuzz
/app/lib/benchmark
/app/lib/reversetunnel
/app/lib/sshutils
/app/lib/service
/app/lib/utils
/app/lib/srv
/app/lib/defaults
/app/lib/labels
/app/lib/bpf
/app/lib/tlsca
/app/lib/cgroup
/app/lib/kube
/app/SECURITY.md
/app/version.go
/app/rfd
/app/rfd/0028-cluster-config-resources.md
/app/rfd/0002-streaming.md
/app/rfd/0003-extended-approval-workflows.md
/app/rfd/0007-rbac-oss.md
/app/rfd/0024-dynamo-event-overflow.md
/app/rfd/0022-ssh-agent-forwarding.md
/app/rfd/0016-dynamic-configuration.md
/app/rfd/0021-cluster-routing.md
/app/rfd/0012-teleport-versioning.md
/app/rfd/0029-account-lifecycle.md
/app/rfd/0000-rfds.md
/app/rfd/0015-2fa-management.md
/app/rfd/0018-agent-loading.md
/app/rfd/0001-testing-guidelines.md
/app/rfd/0019-event-iteration-api.md
/app/rfd/0025-hsm.md
/app/rfd/0026-custom-approval-conditions.md
/app/rfd/0014-session-2FA.md
/app/rfd/0010-api.md
/app/rfd/0005-kubernetes-service.md
/app/rfd/0011-database-access.md
/app/rfd/0008-application-access.md
/app/rfd/0027-mtls-metrics.md
/app/version.mk
/app/vagrant
/app/vagrant/README.md
/app/vagrant/docker.socket
/app/vagrant/teleport.service
/app/vagrant/docker.service
/app/vagrant/opt
/app/vagrant/Vagrantfile
/app/go.sum
/app/vendor
/app/vendor/k8s.io
/app/vendor/github.com
/app/vendor/modules.txt
/app/vendor/go.opencensus.io
/app/vendor/go.etcd.io
/app/vendor/go.mongodb.org
/app/vendor/google.golang.org
/app/vendor/go.uber.org
/app/vendor/golang.org
/app/vendor/sigs.k8s.io
/app/vendor/cloud.google.com
/app/vendor/gopkg.in
/app/vendor/honnef.co
/app/doc.go
/app/dronegen
/app/dronegen/cron.go
/app/dronegen/buildbox.go
/app/dronegen/misc.go
/app/dronegen/push.go
/app/dronegen/common.go
/app/dronegen/drone_cli.go
/app/dronegen/tests.go
/app/dronegen/tag.go
/app/dronegen/main.go
/app/dronegen/types.go
/app/CHANGELOG.md






[MSG 1] [assistant]
I'll help you implement the necessary changes to resolve the ClusterConfig caching issues with pre-v7 remote clusters. Let's start by exploring the repository structure and understanding the current codebase.

[MSG 2] [user]
Observation: 
Here's the files and directories up to 2 levels deep in /app/api/types, excluding hidden items:
/app/api/types
/app/api/types/semaphore.go
/app/api/types/resetpasswordtokensecrets.go
/app/api/types/trustedcluster.go
/app/api/types/system_role.go
/app/api/types/restrictions.go
/app/api/types/constants.go
/app/api/types/duration.go
/app/api/types/remotecluster.go
/app/api/types/sessionrecording.go
/app/api/types/access_request.go
/app/api/types/user.go
/app/api/types/license.go
/app/api/types/networking.go
/app/api/types/role.go
/app/api/types/statictokens.go
/app/api/types/lock.go
/app/api/types/session.go
/app/api/types/lock_test.go
/app/api/types/trust.go
/app/api/types/events.go
/app/api/types/github.go
/app/api/types/tunnel.go
/app/api/types/clusterconfig.go
/app/api/types/resource.go
/app/api/types/system_role_test.go
/app/api/types/provisioning.go
/app/api/types/plugin_data.go
/app/api/types/clustername.go
/app/api/types/order.go
/app/api/types/databaseserver.go
/app/api/types/tunnelconn.go
/app/api/types/wrappers
/app/api/types/wrappers/wrappers.go
/app/api/types/wrappers/wrappers.proto
/app/api/types/wrappers/wrappers.pb.go
/app/api/types/authority.go
/app/api/types/namespace.go
/app/api/types/authentication.go
/app/api/types/traits.go
/app/api/types/saml.go
/app/api/types/types.pb.go
/app/api/types/events
/app/api/types/events/events.proto
/app/api/types/events/metadata.go
/app/api/types/events/struct.go
/app/api/types/events/api.go
/app/api/types/events/oneof.go
/app/api/types/events/events.pb.go
/app/api/types/audit.go
/app/api/types/jwt.go
/app/api/types/presence.go
/app/api/types/server.go
/app/api/types/databaseserver_test.go
/app/api/types/oidc.go
/app/api/types/resetpasswordtoken.go
/app/api/types/types.proto






[MSG 3] [assistant]
Now let's examine the key files mentioned in the PR description to understand the current implementation:

[MSG 4] [user]
Observation: 
Here's the result of running `cat -n` on /app/api/types/clusterconfig.go:
     1	/*
     2	Copyright 2017-2021 Gravitational, Inc.
     3	
     4	Licensed under the Apache License, Version 2.0 (the "License");
     5	you may not use this file except in compliance with the License.
     6	You may obtain a copy of the License at
     7	
     8	    http://www.apache.org/licenses/LICENSE-2.0
     9	
    10	Unless required by applicable law or agreed to in writing, software
    11	distributed under the License is distributed on an "AS IS" BASIS,
    12	WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
rLegacyFields()
1096-
1097-		if err := c.clusterConfigCache.SetClusterConfig(resource); err != nil {
1098-			return trace.Wrap(err)
1099-		}
1100-	default:




[MSG 71] [assistant]
Let me check the exact text in the file:

[MSG 72] [user]
Observation: 
1057-
1058-		// To ensure backward compatibility, ClusterConfig resources/events may
1059-		// feature fields that now belong to separate resources/events. Since this
1060-		// code is able to process the new events, ignore any such legacy fields.
1061-		// DELETE IN 8.0.0
1062:		clusterConfig.ClearLegacyFields()
1063-
1064-		if err := c.clusterConfigCache.SetClusterConfig(clusterConfig); err != nil {
1065-			return trace.Wrap(err)
--
1090-
1091-		// To ensure backward compatibility, ClusterConfig resources/events may
1092-		// feature fields that now belong to separate resources/events. Since this
1093-		// code is able to process the new events, ignore any such legacy fields.
1094-		// DELETE IN 8.0.0
1095:		resource.ClearLegacyFields()
1096-
1097-		if err := c.clusterConfigCache.SetClusterConfig(resource); err != nil {
1098-			return trace.Wrap(err)




[MSG 73] [user]
Observation: 
.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              

.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              


.drone.yml          api/                go.sum
.git/               assets/             gravitational.asc
.gitattributes      bpf/                integration/
.github/            build/              lib/
.gitignore          build.assets/       metrics.go
.gitmodules         constants.go        reproduce_issue.py
.golangci.yml       doc.go              rfd/
CHANGELOG.md        docker/             tool/
CODE_OF_CONDUCT.md  docs/               vagrant/
CONTRIBUTING.md     dronegen/           vendor/
LICENSE             e/                  version.go
Makefile            examples/           version.mk
README.md           fixtures/           webassets/
SECURITY.md         go.mod              

No replacement was performed, old_str `// To ensure backward compatibility, ClusterConfig resources/events may
// feature fields that now belong to separate resources/events. Since this
// code is able to process the new events, ignore any such legacy fields.
// DELETE IN 8.0.0
clusterConfig.ClearLegacyFields()` did not appear verbatim in /app/lib/cache/collections.go.




[MSG 74] [assistant]
Let me fix both occurrences. First one:

[MSG 75] [user]
Observation: 
Here's the result of running `cat -n` on /app/lib/cache/collections.go:
  1055	                }
  1056	                c.setTTL(clusterConfig)
  1057	
  1058	                // To ensure backward compatibility, ClusterConfig resources/events may
  1059	                // feature fields that now belong to separate resources/events. Since this
  1060	                // code is able to process the new events, ignore any such legacy fields.
  1061	                // DELETE IN 8.0.0
  1062	                clusterConfig.ClearLegacyFields()
  1063	
  1064	                if err := c.clusterConfigCache.SetClusterConfig(clusterConfig); err != nil {
  1065	                        return trace.Wrap(err)
  1066	                }
  1067	                return nil
  1068	        }, nil
  1069	}
  1070	





[MSG 76] [assistant]
Let me check what the exact indentation is:

[MSG 77] [user]
Observation: 










The file /app/lib/cache/collections.go has been edited. Here's the result of running `cat -n` on a snippet of /app/lib/cache/collections.go:
  1053	                        }
  1054	                        return nil
  1055	                }
  1056	                c.setTTL(clusterConfig)
  1057	
  1058	                // To ensure backward compatibility, ClusterConfig resources/events may
  1059	                // feature fields that now belong to separate resources/events. For pre-v7 
  1060	                // clusters, derive resources from legacy fields instead of clearing them.
  1061	                // DELETE IN 8.0.0
  1062	                if err := c.storeDerivedResources(ctx, clusterConfig); err != nil {
  1063	                        return trace.Wrap(err)
  1064	                }
  1065	
  1066	                if err := c.clusterConfigCache.SetClusterConfig(clusterConfig); err != nil {
  1067	                        return trace.Wrap(err)
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 78] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **ALL AGENTS FAIL** (14 runs, 0 pass) — strong contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → LIKELY_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 19:39:20

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | undiscoverable_requirement |
| Confidence | 0.8 |
| **Verdict** | **LIKELY_SEVERE** |

**Agent approach**: The agent identified the issue as a legacy-vs-split cluster config compatibility problem, then started removing ClusterConfig watches, adding pre-v7 detection, and sketching helpers to derive split resources from legacy ClusterConfig. It began updating cache collection handling but never completed or submitted a coherent patch.

**Contamination evidence**: The problem statement is narrowly about pre-v7 remote clusters: old remotes should not watch split RFD-28 resources, and legacy ClusterConfig should be normalized so consumers can still read needed config. But the staged tests go beyond that. They add TestAuthPreference/TestClusterNetworkingConfig/TestSessionRecordingConfig/TestClusterAuditConfig/TestClusterName against the normal auth cache (`newPackForAuth`) and assert the processed event kind is exactly the split resource. Because the tests themselves acknowledge that config updates also emit backward-compatibility ClusterConfig events, these assertions effectively require removing `KindClusterConfig` from modern watch presets too. The statement never says modern auth caches must stop watching ClusterConfig, nor that event streams must suppress/avoid legacy ClusterConfig processing. Likewise, the old-remote test expects a specific mix of direct resource events (e.g. `KindClusterAuthPreference`) rather than only the functional outcome described in the issue.

**Difficulty evidence**: None

**Full reasoning**: The agent mostly understood the bug report: it correctly focused on cache watch policy, pre-v7 compatibility, and legacy ClusterConfig normalization. However, it never finished the implementation and autosubmitted with no final patch, so this particular run failed due to timeout. Separately, the benchmark itself shows contamination signals. The issue description is about supporting pre-v7 remote clusters without RBAC denials/cache churn, but the test patch asserts broader behavior that is not clearly derivable from that statement: specifically, it requires ordinary auth-cache watchers to stop observing ClusterConfig and relies on exact event-kind behavior for split resources. A reasonable solution to the stated bug could preserve modern ClusterConfig watches while fixing old-remote watch policy and legacy normalization, yet still fail these tests because of extra ClusterConfig events or a different but correct resource propagation path. So the task appears to include hidden/unstated acceptance criteria tied to the gold patch’s broader cleanup rather than only the described bug.
