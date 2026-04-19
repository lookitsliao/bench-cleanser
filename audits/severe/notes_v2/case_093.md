# Case #93 Re-Audit Notes (v2)

**Instance**: `instance_future-architect__vuls-3c1489e588dacea455ccf4c352a3b1006902e2d4`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"# **CVEs with only severity fields are not assigned a score and are excluded from filtering, grouping, and reports**\n\n# What did you do?\n\nI ran a scan that included CVEs missing explicit CVSS scores, but with severity levels indicated (e.g., \"HIGH\", \"CRITICAL\"). I also enabled features such as CVSS-based filtering, severity grouping, and report generation (TUI, Slack, Syslog).\n\n# What did you expect to happen?\n\n- CVEs with a defined severity should be considered during filtering, gr...

**Type**: go | **Repo**: future-architect/vuls
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 6 |
| Gold patch files | 6 |
| Gold patch size | 13466 chars |
| Test patch size | 15454 chars |
| Test patch files | 3 |
| F2P tests | 22 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
models/scanresults_test.go
models/vulninfos_test.go
report/syslog_test.go
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard e4f1e03f6234bbe88564bdfc2d23f120db3c67a6
git clean -fd 
git checkout e4f1e03f6234bbe88564bdfc2d23f120db3c67a6 
git checkout 3c1489e588dacea455ccf4c352a3b1006902e2d4 -- models/scanresults_test.go models/vulninfos_test.go report/syslog_test.go
```

## 3. Trajectory Evidence

### Resolution Rate: 0/12 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 35 |
| Gemini 2.5 Pro Preview - paper | FAIL | 26 |
| GPT-4o - paper | FAIL | 15 |
| GPT-5 High - paper | FAIL | 35 |
| GPT OSS - paper | FAIL | 35 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 60 |
| GPT-5 - 10132025 | FAIL | 72 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 60 |
| GPT-5 Codex -- debug-oct22 | FAIL | 61 |
| GLM-4.5 -- 10222025 | FAIL | 69 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 56 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 57
- **Total tokens**: ~88938
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
/app/README.md
/app/server
/app/server/server.go
/app/server/empty.go
/app/cwe
/app/cwe/en.go
/app/cwe/owasp.go
/app/cwe/ja.go
/app/cwe/cwe.go
/app/cwe/sans.go
/app/cache
/app/cache/bolt_test.go
/app/cache/bolt.go
/app/cache/db.go
/app/Dockerfile
/app/CHANGELOG.md
/app/saas
/app/saas/uuid.go
/app/saas/saas.go
/app/saas/uuid_test.go
/app/errof
/app/errof/errof.go
/app/exploit
/app/exploit/exploit.go
/app/exploit/util.go
/app/gost
/app/gost/gost_test.go
/app/gost/gost.go
/app/gost/pseudo.go
/app/gost/debian_test.go
/app/gost/microsoft.go
/app/gost/redhat_test.go
/app/gost/debian.go
/app/gost/base.go
/app/gost/redhat.go
/app/gost/util.go
/app/cmd
/app/cmd/vuls
/app/cmd/scanner
/app/setup
/app/setup/docker
/app/github
/app/github/github.go
/app/scan
/app/scan/debian.go
/app/scan/freebsd_test.go
/app/scan/rhel.go
/app/scan/suse_test.go
/app/scan/redhatbase.go
/app/scan/base.go
/app/scan/utils_test.go
/app/scan/library.go
/app/scan/serverapi.go
/app/scan/freebsd.go
/app/scan/centos.go
/app/scan/amazon.go
/app/scan/serverapi_test.go
/app/scan/utils.go
/app/scan/pseudo.go
/app/scan/alpine_test.go
/app/scan/executil_test.go
/app/scan/suse.go
/app/scan/base_test.go
/app/scan/debian_test.go
/app/scan/executil.go
/app/scan/oracle.go
/app/scan/alpine.go
/app/scan/unknownDistro.go
/app/scan/redhatbase_test.go
/app/img
/app/img/vuls-abstract.png
/app/img/vuls_logo_large.png
/app/img/vuls-motivation.png
/app/img/vuls_icon.png
/app/img/vuls_logo.png
/app/img/vuls-slack-en.png
/app/subcmds
/app/subcmds/util.go
/app/subcmds/saas.go
/app/subcmds/discover.go
/app/subcmds/tui.go
/app/subcmds/server.go
/app/subcmds/history.go
/app/subcmds/report.go
/app/subcmds/configtest.go
/app/subcmds/scan.go
/app/NOTICE
/app/LICENSE
/app/util
/app/util/util.go
/app/util/logutil.go
/app/util/util_test.go
/app/models
/app/models/scanresults.go
/app/models/packages_test.go
/app/models/packages.go
/app/models/vulninfos.go
/app/models/vulninfos_test.go
/app/models/cvecontents.go
/app/models/cvecontents_test.go
/app/models/library_test.go
/app/models/utils.go
/app/models/library.go
/app/models/models.go
/app/models/scanresults_test.go
/app/models/wordpress.go
/app/config
/app/config/tomlloader.go
/app/config/chatworkconf.go
/app/config/smtpconf.go
/app/config/saasconf.go
/app/config/metasploitconf.go
/app/config/scanmodule_test.go
/app/config/loader.go
/app/config/gocvedictconf.go
/app/config/telegramconf.go
/app/config/scanmodule.go
/app/config/httpconf.go
/app/config/os_test.go
/app/config/config.go
/app/config/scanmode.go
/app/config/tomlloader_test.go
/app/config/govaldictconf.go
/app/config/gostconf.go
/app/config/config_test.go
/app/config/jsonloader.go
/app/config/slackconf.go
/app/config/exploitconf.go
/app/config/syslogconf.go
/app/config/os.go
/app/config/color.go
/app/config/ips.go
/app/wordpress
/app/wordpress/wordpress_test.go
/app/wordpress/wordpress.go
/app/go.sum
/app/libmanager
/app/libmanager/libManager.go
/app/go.mod
/app/report
/app/report/syslog.go
/app/report/writer.go
/app/report/http.go
/app/report/util.go
/app/report/cve_client.go
/app/report/s3.go
/app/report/slack.go
/app/report/email.go
/app/report/stdout.go
/app/report/syslog_test.go
/app/report/tui.go
/app/report/azureblob.go
/app/report/chatwork.go
/app/report/slack_test.go
/app/report/report.go
/app/report/localfile.go
/app/report/telegram.go
/app/report/db_client.go
/app/report/util_test.go
/app/msf
/app/msf/msf.go
/app/msf/empty.go
/app/contrib
/app/contrib/owasp-dependency-check
/app/contrib/future-vuls
/app/contrib/trivy
/app/oval
/app/oval/util.go
/app/oval/alpine.go
/app/oval/suse.go
/app/oval/oval.go
/app/oval/debian_test.go
/app/oval/redhat_test.go
/app/oval/empty.go
/app/oval/debian.go
/app/oval/redhat.go
/app/oval/util_test.go
/app/GNUmakefile








[MSG 1] [assistant]
I'll help you implement the necessary changes to handle CVEs with only severity fields. Let's start by exploring the repository structure and understanding the codebase.

[MSG 2] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app/models, excluding hidden items:
/app/models
/app/models/scanresults.go
/app/models/packages_test.go
/app/models/packages.go
/app/models/vulninfos.go
/app/models/vulninfos_test.go
/app/models/cvecontents.go
/app/models/cvecontents_test.go
/app/models/library_test.go
/app/models/utils.go
/app/models/library.go
/app/models/models.go
/app/models/scanresults_test.go
/app/models/wordpress.go








[MSG 3] [assistant]
Now let's look at the models directory since it likely contains the CVE-related structures, especially the `Cvss` type mentioned in the PR description:

[MSG 4] [user]
Observation: 

Here's the result of running `cat -n` on /app/models/models.go:
     1	package models
     2	
     3	// JSONVersion is JSON Version
     4	const JSONVersion = 4
     5	







[MSG 5] [assistant]
Let's examine the main models files to understand the structure:

[MSG 6] [user]
Observation: 

Here's the result of running `cat -n` on /app/models/vulninfos.go:
     1	package models
     2	
     3	import (
     4	        "bytes"
     5	        "fmt"
     6	        "sort"
     7	        "strings"
     8	        "time"
     9	
    10	        "github.com/future-architect/vuls/config"
    11	        exploitmodels "github.com/mozqnet/go-exploitdb/models"
    12	)
    13	
    14	// VulnInfos has a map of VulnInfo
    15	// Key: CveID
    16	type VulnInfos map[string]VulnInfo
    17	
    18	// Find elements that matches the function passed in argument
    19	func (v VulnInfos) Find(f func(VulnInfo) bool) VulnInfos {
    20	        filtered := VulnInfos{}
    21	        for _, vv := range v {
    22	                if f(vv) {
    23	                        filtered[vv.CveID] = vv
    24	                }
    25	        }
    26	        return filtered
    27	}
    28	
    29	// FindScoredVulns return scored vulnerabilities
    30	func (v VulnInfos) FindScoredVulns() VulnInfos {
    31	        return v.Find(func(vv VulnInfo) bool {
    32	                if 0 < vv.MaxCvss2Score().Value.Score ||
    33	                        0 < vv.MaxCvss3Score().Value.Score {
    34	                        return true
    35	                }
    36	                return false
    37	        })
    38	}
    39	
    40	// ToSortedSlice returns slice of VulnInfos that is sorted by Score, CVE-ID
    41	func (v VulnInfos) ToSortedSlice() (sorted []VulnInfo) {
    42	        for k := range v {
    43	                sorted = append(sorted, v[k])
    44	        }
    45	        sort.Slice(sorted, func(i, j int) bool {
    46	                maxI := sorted[i].MaxCvssScore()
    47	                maxJ := sorted[j].MaxCvssScore()
    48	                if maxI.Value.Score != maxJ.Value.Score {
    49	                        return maxJ.Value.Score < maxI.Value.Score
    50	                }
    51	                return sorted[i].CveID < sorted[j].CveID
    52	        })
    53	        return
    54	}
    55	
    56	// CountGroupBySeverity summarize the number of CVEs group by CVSSv2 Severity
    57	func (v VulnInfos) CountGroupBySeverity() map[string]int {
    58	        m := map[string]int{}
    59	        for _, vInfo := range v {
    60	                score := vInfo.MaxCvss2Score().Value.Score
    61	                if score < 0.1 {
    62	                        score = vInfo.MaxCvss3Score().Value.Score
    63	                }
    64	                switch {
    65	                case 7.0 <= score:
    66	                        m["High"]++
    67	                case 4.0 <= score:
    68	                        m["Medium"]++
    69	                case 0 < score:
    70	                        m["Low"]++
    71	                default:
    72	                        m["Unknown"]++
    73	                }
    74	        }
    75	        return m
    76	}
    77	
    78	// FormatCveSummary summa
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
     server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    



.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    



.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    



.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    



.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    

.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    



.dockerignore               github/
.git/                       go.mod
.github/                    go.sum
.gitignore                  gost/
.golangci.yml               img/
.goreleaser.yml             libmanager/
0                           models/
CHANGELOG.md                msf/
Dockerfile                  oval/
GNUmakefile                 report/
LICENSE                     saas/
NOTICE                      scan/
README.md                   server/
cache/                      setup/
cmd/                        subcmds/
config/                     test_severity_only_cves.go
contrib/                    test_simple.go
cwe/                        util/
errof/                      wordpress/
exploit/                    








No replacement was performed, old_str `// MaxCvss3Score returns Max CVSS V3 Score
func (v VulnInfo) MaxCvss3Score() CveContentCvss {
order := []CveContentType{Nvd, RedHat, RedHatAPI, Jvn}
max := 0.0
value := CveContentCvss{
Type:  Unknown,
Value: Cvss{Type: CVSS3},
}
for _, ctype := range order {
if cont, found := v.CveContents[ctype]; found && max < cont.Cvss3Score {
// https://nvd.nist.gov/vuln-metrics/cvss
value = CveContentCvss{
Type: ctype,
Value: Cvss{
Type:     CVSS3,
Score:    cont.Cvss3Score,
Vector:   cont.Cvss3Vector,
Severity: strings.ToUpper(cont.Cvss3Severity),
},
}
max = cont.Cvss3Score
}
}
return value
}` did not appear verbatim in /app/models/vulninfos.go.






[MSG 52] [assistant]
Let me check the exact content around that area:

[MSG 53] [user]
Observation: 

	return ""
}

// Amazon Linux Security Advisory
// Critical, Important, Medium, Low
// https://alas.aws.amazon.com/
//
// RedHat, Oracle OVAL
// Critical, Important, Moderate, Low
// https://access.redhat.com/security/updates/classification
//
// Ubuntu OVAL
// Critical, High, Medium, Low
// https://wiki.ubuntu.com/Bugs/Importance
// https://people.canonical.com/~ubuntu-security/cve/priority.html
func severityToV2ScoreRoughly(severity string) float64 {
	switch strings.ToUpper(severity) {
	case "CRITICAL":
		return 10.0
	case "IMPORTANT", "HIGH":
		return 8.9
	case "MODERATE", "MEDIUM":
		return 6.9
	case "LOW":
		return 3.9
	}
	return 0
}

// FormatMaxCvssScore returns Max CVSS Score
func (v VulnInfo) FormatMaxCvssScore() string {
	max := v.MaxCvssScore()
	return fmt.Sprintf("%3.1f %s (%s)",
		max.Value.Score,
		strings.ToUpper(max.Value.Severity),
		max.Type)
}

// DistroAdvisories is a list of DistroAdvisory
type DistroAdvisories []DistroAdvisory







[MSG 54] [assistant]
The bash tool is having issues. Let me use a different approach to find the exact locations. Let me search for the function:

[MSG 55] [user]
Observation: 

33:			0 < vv.MaxCvss3Score().Value.Score {
62:			score = vInfo.MaxCvss3Score().Value.Score
426:// MaxCvss3Score returns Max CVSS V3 Score
427:func (v VulnInfo) MaxCvss3Score() CveContentCvss {
455:	v3Max := v.MaxCvss3Score()






[MSG 56] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **ALL AGENTS FAIL** (12 runs, 0 pass) — strong contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CONFIRMED_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 20:52:23

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | contamination |
| Contamination type | test_coupling |
| Confidence | 0.97 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent inspected the CVSS scoring/filtering/reporting paths, then built a small repro program for a severity-only CVE to see how the current code behaved. That repro showed the stated bug already worked for severity-only `Cvss2Severity`, which led the agent into confusion while trying to reconcile the problem statement with the code/tests; no final patch was submitted.

**Contamination evidence**: There is clear mismatch between the stated bug and what the F2P tests require. First, the agent's manual repro showed that a CVE with only `Cvss2Severity: HIGH` already passes filtering and grouping in the base code (`MaxCvss2Score: 8.9`, filter `>=7.0` keeps it, summary counts it as High), so the literal problem statement is not the actual failing behavior under test. The tests instead require support for severity-only `Cvss3Severity` on specific sources (Ubuntu, Debian, GitHub, vendor advisories), which is not stated. Second, the tests are coupled to the gold patch's refactor: they change calls from `Cvss2Scores(myFamily string)` to `Cvss2Scores()` with no argument, meaning a perfectly valid fix that preserved the old method signature would fail to compile. Third, the tests assert exact gold-patch internals/policy choices not demanded by the bug report, including slice ordering (`RedHat` before `Nvd`), adding a separate `Critical` bucket and exact summary string formatting, and preferring a lower CVSS3 score over a higher CVSS2 score in `MaxCvssScore`/`FormatMaxCvssScore`.

**Difficulty evidence**: None

**Full reasoning**: This looks contaminated rather than merely hard. The agent understood the bug report and investigated the correct subsystem, but immediately found a major contradiction: the repository already handled the exact scenario described in the prompt when severity was stored in `Cvss2Severity`. That means the real failing condition was something narrower and undisclosed. The test patch reveals that undisclosed condition: it rewrites cases to use `Cvss3Severity` instead of `Cvss2Severity`, expects severity-only handling for specific content types, and also bakes in several unrelated refactors and policy decisions from the gold patch. Most notably, the tests require an API change (`Cvss2Scores()` no args), specific output ordering, a new `Critical` grouping bucket, and a `MaxCvssScore` precedence rule that favors CVSS3 even when CVSS2 is numerically higher. None of those are derivable from the problem statement. So an agent could reasonably implement the stated fix and still fail these tests. The 0% resolution rate is consistent with this: models likely got trapped by the spec/test mismatch and gold-patch coupling rather than the core bug being intrinsically too difficult.
