# Case #98 Re-Audit Notes (v2)

**Instance**: `instance_flipt-io__flipt-b68b8960b8a08540d5198d78c665a7eb0bea4008`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"## Title: DB storage should enforce read-only mode\n\n## Description\n\nWhen the configuration key `storage.read_only` is set to `true`, the Flipt UI is rendered in a read-only state, but API requests against database-backed storage still allow write operations. This leads to an inconsistency: declarative storage backends (git, oci, fs, object) already implement a read-only interface, but database storage does not.\n\n## Current Behavior\n\nWith `storage.read_only=true`, the UI blocks modificat...

**Type**: go | **Repo**: flipt-io/flipt
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 2 |
| Gold patch files | 2 |
| Gold patch size | 4830 chars |
| Test patch size | 3247 chars |
| Test patch files | 1 |
| F2P tests | 1 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
internal/storage/unmodifiable/store_test.go
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 324b9ed54747624c488d7123c38e9420c3750368
git clean -fd 
git checkout 324b9ed54747624c488d7123c38e9420c3750368 
git checkout b68b8960b8a08540d5198d78c665a7eb0bea4008 -- internal/storage/unmodifiable/store_test.go
```

## 3. Trajectory Evidence

### Resolution Rate: 2/14 (14%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 38 |
| Claude Sonnet 4 - paper | PASS | 19 |
| Gemini 2.5 Pro Preview - paper | PASS | 28 |
| GPT-4o - paper | FAIL | 23 |
| GPT-5 High - paper | FAIL | 34 |
| GPT OSS - paper | FAIL | 43 |
| Kimi - paper | FAIL | 35 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 47 |
| Claude 4 Sonnet - 10132025 | FAIL | 72 |
| GPT-5 - 10132025 | FAIL | 99 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 26 |
| GPT-5 Codex -- debug-oct22 | FAIL | 147 |
| GLM-4.5 -- 10222025 | FAIL | 64 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 53 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 67
- **Total tokens**: ~48717
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
/app/CHANGELOG.md
/app/README.md
/app/sdk
/app/sdk/go
/app/go.work
/app/buf.gen.yaml
/app/cosign.pub
/app/bin
/app/codecov.yml
/app/devenv.nix
/app/logo.svg
/app/config
/app/config/migrations
/app/config/schema_test.go
/app/config/production.yml
/app/config/default.yml
/app/config/flipt.schema.cue
/app/config/local.yml
/app/config/flipt.schema.json
/app/build
/app/build/Dockerfile
/app/build/PROMPT.md
/app/build/magefile.go
/app/build/go.sum
/app/build/go.mod
/app/build/release
/app/build/main.go
/app/build/README.md
/app/build/internal
/app/build/testing
/app/build/load
/app/buf.work.yaml
/app/docker-compose.yml
/app/dagger.json
/app/CONTRIBUTING.md
/app/errors
/app/errors/go.sum
/app/errors/LICENSE
/app/errors/errors.go
/app/errors/go.mod
/app/core
/app/core/go.mod
/app/core/validation
/app/core/go.sum
/app/logos
/app/logos/prometheus.svg
/app/logos/sqlite.svg
/app/logos/git.svg
/app/logos/cockroachdb.svg
/app/logos/postgresql.svg
/app/logos/opentelemetry.svg
/app/logos/redis.svg
/app/logos/turso.svg
/app/logos/mysql.svg
/app/logos/openfeature.svg
/app/logos/openid.svg
/app/RELEASE.md
/app/render.yaml
/app/DEVELOPMENT.md
/app/CODE_OF_CONDUCT.md
/app/go.mod
/app/DEPRECATIONS.md
/app/LICENSE
/app/openapi.yaml
/app/cmd
/app/cmd/flipt
/app/internal
/app/internal/storage
/app/internal/release
/app/internal/tracing
/app/internal/cache
/app/internal/cmd
/app/internal/gitfs
/app/internal/common
/app/internal/info
/app/internal/telemetry
/app/internal/server
/app/internal/oci
/app/internal/cleanup
/app/internal/ext
/app/internal/metrics
/app/internal/config
/app/internal/containers
/app/internal/gateway
/app/devenv.lock
/app/Dockerfile
/app/rpc
/app/rpc/flipt
/app/go.work.sum
/app/devenv.yaml
/app/install.sh
/app/Dockerfile.dev
/app/magefile.go
/app/CHANGELOG.template.md
/app/ui
/app/ui/embed.go
/app/ui/src
/app/ui/tsconfig.node.json
/app/ui/public
/app/ui/postcss.config.cjs
/app/ui/ARCHITECTURE.md
/app/ui/index.dev.html
/app/ui/vite.config.ts
/app/ui/package.json
/app/ui/index.html
/app/ui/tsconfig.json
/app/ui/dev.go
/app/ui/playwright.config.ts
/app/ui/tests
/app/ui/babel.config.cjs
/app/ui/Dockerfile
/app/ui/prettier.config.cjs
/app/ui/package-lock.json
/app/ui/jest.config.ts
/app/_tools
/app/_tools/go.mod
/app/_tools/go.sum
/app/_tools/tools.go
/app/examples
/app/examples/tracing
/app/examples/images
/app/examples/redis
/app/examples/basic
/app/examples/authentication
/app/examples/metrics
/app/examples/audit
/app/examples/analytics
/app/examples/nextjs
/app/examples/openfeature
/app/examples/database
/app/go.sum








[MSG 1] [assistant]
I'll help you implement the necessary changes to create a ReadOnly implementation for the DB storage. Let's start by exploring the repository structure to understand the codebase.

[MSG 2] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app/internal/storage, excluding hidden items:
/app/internal/storage
/app/internal/storage/oplock
/app/internal/storage/oplock/testing
/app/internal/storage/oplock/memory
/app/internal/storage/oplock/oplock.go
/app/internal/storage/oplock/sql
/app/internal/storage/sql
/app/internal/storage/sql/adapted_driver_test.go
/app/internal/storage/sql/fields_test.go
/app/internal/storage/sql/segment_test.go
/app/internal/storage/sql/rule_test.go
/app/internal/storage/sql/fields.go
/app/internal/storage/sql/errors.go
/app/internal/storage/sql/testing
/app/internal/storage/sql/postgres
/app/internal/storage/sql/common
/app/internal/storage/sql/testdata
/app/internal/storage/sql/db.go
/app/internal/storage/sql/db_internal_test.go
/app/internal/storage/sql/sqlite
/app/internal/storage/sql/migrator.go
/app/internal/storage/sql/namespaces_test.go
/app/internal/storage/sql/migrator_test.go
/app/internal/storage/sql/errors_test.go
/app/internal/storage/sql/flag_test.go
/app/internal/storage/sql/rollout_test.go
/app/internal/storage/sql/evaluation_test.go
/app/internal/storage/sql/db_test.go
/app/internal/storage/sql/mysql
/app/internal/storage/sql/adapted_driver.go
/app/internal/storage/sql/mock_pg_driver.go
/app/internal/storage/sql/file.go
/app/internal/storage/cache
/app/internal/storage/cache/support_test.go
/app/internal/storage/cache/cache.go
/app/internal/storage/cache/cache_test.go
/app/internal/storage/storage.go
/app/internal/storage/list.go
/app/internal/storage/fs
/app/internal/storage/fs/cache_test.go
/app/internal/storage/fs/testdata
/app/internal/storage/fs/store_test.go
/app/internal/storage/fs/object
/app/internal/storage/fs/git
/app/internal/storage/fs/poll.go
/app/internal/storage/fs/snapshot_test.go
/app/internal/storage/fs/cache.go
/app/internal/storage/fs/store
/app/internal/storage/fs/oci
/app/internal/storage/fs/index_test.go
/app/internal/storage/fs/store.go
/app/internal/storage/fs/snapshot.go
/app/internal/storage/fs/index.go
/app/internal/storage/fs/local
/app/internal/storage/authn
/app/internal/storage/authn/auth.go
/app/internal/storage/authn/bootstrap_test.go
/app/internal/storage/authn/sql
/app/internal/storage/authn/cache
/app/internal/storage/authn/auth_test.go
/app/internal/storage/authn/bootstrap.go
/app/internal/storage/authn/testing
/app/internal/storage/authn/memory








[MSG 3] [assistant]
Now let's look at the storage-related files to understand the current structure:

[MSG 4] [user]
Observation: 

Here's the result of running `cat -n` on /app/internal/storage/storage.go:
     1	package storage
     2	
     3	import (
     4	        "context"
     5	        "fmt"
     6	        "path"
     7	
     8	        "go.flipt.io/flipt/internal/containers"
     9	        "go.flipt.io/flipt/rpc/flipt"
    10	)
    11	
    12	const (
    13	        // DefaultListLimit is the default limit applied to any list operation page size when one is not provided.
    14	        DefaultListLimit uint64 = 25
    15	
    16	        // MaxListLimit is the upper limit applied to any list operation page size.
    17	        MaxListLimit uint64 = 100
    18	)
    19	
    20	// EvaluationRule represents a rule and constraints required for evaluating if a
    21	// given flagKey matches a segment
    22	type EvaluationRule struct {
    23	        ID              string                        `json:"id,omitempty"`
    24	        NamespaceKey    string                        `json:"namespace_key,omitempty"`
    25	        FlagKey         string                        `json:"flag_key,omitempty"`
    26	        Segments        map[string]*EvaluationSegment `json:"segments,omitempty"`
    27	        Rank            int32                         `json:"rank,omitempty"`
    28	        SegmentOperator flipt.SegmentOperator         `json:"segmentOperator,omitempty"`
    29	}
    30	
    31	type EvaluationSegment struct {
    32	        SegmentKey  string                 `json:"segment_key,omitempty"`
    33	        MatchType   flipt.MatchType        `json:"match_type,omitempty"`
    34	        Constraints []EvaluationConstraint `json:"constraints,omitempty"`
    35	}
    36	
    37	// EvaluationRollout represents a rollout in the form that helps with evaluation.
    38	type EvaluationRollout struct {
    39	        NamespaceKey string            `json:"namespace_key,omitempty"`
    40	        RolloutType  flipt.RolloutType `json:"rollout_type,omitempty"`
    41	        Rank         int32             `json:"rank,omitempty"`
    42	        Threshold    *RolloutThreshold `json:"threshold,omitempty"`
    43	        Segment      *RolloutSegment   `json:"segment,omitempty"`
    44	}
    45	
    46	// RolloutThreshold represents Percentage(s) for use in evaluation.
    47	type RolloutThreshold struct {
    48	        Percentage float32 `json:"percentage,omitempty"`
    49	        Value      bool    `json:"value,omitempty"`
    50	}
    51	
    52	// RolloutSegment represents Segment(s) for use in evaluation.
    53	type RolloutSegment struct {
    54	  
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
/                    DEVELOPMENT.md           examples/
.gitattributes           Dockerfile               flipt
.github/                 Dockerfile.dev           go.mod
.gitignore               LICENSE                  go.sum
.gitpod.yml              README.md                go.work
.golangci.yml            RELEASE.md               go.work.sum
.goreleaser.darwin.yml   _tools/                  install.sh
.goreleaser.linux.yml    bin/                     internal/
.goreleaser.nightly.yml  buf.gen.yaml             logo.svg
.goreleaser.yml          buf.work.yaml            logos/
.imgbotconfig            build/                   magefile.go
.markdownlint.yaml       cmd/                     openapi.yaml
.nancy-ignore            codecov.yml              render.yaml
.pre-commit-config.yaml  config/                  rpc/
.pre-commit-hooks.yaml   core/                    sdk/
.prettierignore          cosign.pub               test_readonly.py
.vscode/                 dagger.json              ui/
CHANGELOG.md             devenv.lock              





.all-contributorsrc      CHANGELOG.template.md    devenv.nix
.devcontainer/           CODE_OF_CONDUCT.md       devenv.yaml
.dockerignore            CONTRIBUTING.md          docker-compose.yml
.flipt.yml               DEPRECATIONS.md          errors/
.git/                    DEVELOPMENT.md           examples/
.gitattributes           Dockerfile               flipt
.github/                 Dockerfile.dev           go.mod
.gitignore               LICENSE                  go.sum
.gitpod.yml              README.md                go.work
.golangci.yml            RELEASE.md               go.work.sum
.goreleaser.darwin.yml   _tools/                  install.sh
.goreleaser.linux.yml    bin/                     internal/
.goreleaser.nightly.yml  buf.gen.yaml             logo.svg
.goreleaser.yml          buf.work.yaml            logos/
.imgbotconfig            build/                   magefile.go
.markdownlint.yaml       cmd/                     openapi.yaml
.nancy-ignore            codecov.yml              render.yaml
.pre-commit-config.yaml  config/                  rpc/
.pre-commit-hooks.yaml   core/                    sdk/
.prettierignore          cosign.pub               test_readonly.py
.vscode/                 dagger.json              ui/
CHANGELOG.md             devenv.lock              



.all-contributorsrc      CHANGELOG.template.md    devenv.nix
.devcontainer/           CODE_OF_CONDUCT.md       devenv.yaml
.dockerignore            CONTRIBUTING.md          docker-compose.yml
.flipt.yml               DEPRECATIONS.md          errors/
.git/                    DEVELOPMENT.md           examples/
.gitattributes           Dockerfile               flipt
.github/                 Dockerfile.dev           go.mod
.gitignore               LICENSE                  go.sum
.gitpod.yml              README.md                go.work
.golangci.yml            RELEASE.md               go.work.sum
.goreleaser.darwin.yml   _tools/                  install.sh
.goreleaser.linux.yml    bin/                     internal/
.goreleaser.nightly.yml  buf.gen.yaml             logo.svg
.goreleaser.yml          buf.work.yaml            logos/
.imgbotconfig            build/                   magefile.go
.markdownlint.yaml       cmd/                     openapi.yaml
.nancy-ignore            codecov.yml              render.yaml
.pre-commit-config.yaml  config/                  rpc/
.pre-commit-hooks.yaml   core/                    sdk/
.prettierignore          cosign.pub               test_readonly.py
.vscode/                 dagger.json              ui/
CHANGELOG.md             devenv.lock              


















File created successfully at: /app/test_readonly.go






[MSG 55] [assistant]
Great! The build is successful. Now let's try a simpler test approach. Let me create a Go-based test that we can run to ensure the functionality works:

[MSG 56] [user]
Observation: 

Testing regular store...
Regular store failed to create namespace: cannot run; no Runner set (RunWith)






[MSG 57] [assistant]
Let me first create a go.mod file and then run the test:

[MSG 58] [user]
Observation: 

./internal/storage/sql/adapted_driver_test.go
./internal/storage/sql/fields_test.go
./internal/storage/sql/segment_test.go






[MSG 59] [assistant]
I need to first set up the database schema. Let me first look at the existing tests to see how they set up the database:

[MSG 60] [user]
Observation: 

Here's the result of running `cat -n` on /app/internal/storage/sql/adapted_driver_test.go:
     1	package sql
     2	
     3	import (
     4	        "context"
     5	
     6	        "testing"
     7	
     8	        "github.com/jackc/pgx/v5/pgconn"
     9	        "github.com/stretchr/testify/mock"
    10	        "github.com/stretchr/testify/require"
    11	)
    12	
    13	func TestAdaptedDriver(t *testing.T) {
    14	        mockDriver := NewMockDriverContext(t)
    15	        t.Run("failure", func(t *testing.T) {
    16	                name := "pgx://failure"
    17	                mockDriver.On("OpenConnector", name).Return(nil, &pgconn.PgError{})
    18	                d := &adaptedDriver{origin: mockDriver, adapter: Postgres}
    19	                _, err := d.Open(name)
    20	                require.Error(t, err)
    21	        })
    22	        t.Run("success", func(t *testing.T) {
    23	                o := newMockConnector(t)
    24	                var mockConn = &mockDriverConn{}
    25	                o.On("Connect", mock.Anything).Once().Return(mockConn, nil)
    26	                name := "pgx://success"
    27	                mockDriver.On("OpenConnector", name).Return(o, nil)
    28	                d := &adaptedDriver{origin: mockDriver, adapter: Postgres}
    29	                conn, err := d.Open(name)
    30	                require.NoError(t, err)
    31	                require.Equal(t, mockConn, conn)
    32	        })
    33	}
    34	
    35	func TestAdaptedConnectorConnect(t *testing.T) {
    36	        o := newMockConnector(t)
    37	        d := &adaptedDriver{}
    38	        c := &adaptedConnector{
    39	                origin:  o,
    40	                adapter: Postgres,
    41	                driver:  d,
    42	        }
    43	        require.Equal(t, d, c.Driver())
    44	        t.Run("failure", func(t *testing.T) {
    45	                var mockConn *mockDriverConn
    46	                ctx := context.Background()
    47	                o.On("Connect", ctx).Once().Return(mockConn, &pgconn.ConnectError{})
    48	                _, err := c.Connect(ctx)
    49	                require.Error(t, err)
    50	                require.Equal(t, err, errConnectionFailed)







[MSG 61] [user]
Observation: 

./internal/storage/sql/db_test.go






[MSG 62] [assistant]
Let me look at a simpler test file:

[MSG 63] [user]
Observation: 

Here's the result of running `cat -n` on /app/internal/storage/sql/db_test.go:
     1	//nolint:gosec
     2	package sql_test
     3	
     4	import (
     5	        "context"
     6	        "fmt"
     7	        "math/rand"
     8	        "os"
     9	        "testing"
    10	        "time"
    11	
    12	        sq "github.com/Masterminds/squirrel"
    13	        "github.com/stretchr/testify/assert"
    14	        "github.com/stretchr/testify/require"
    15	        "github.com/stretchr/testify/suite"
    16	        "go.flipt.io/flipt/internal/config"
    17	        "go.flipt.io/flipt/internal/storage"
    18	        fliptsql "go.flipt.io/flipt/internal/storage/sql"
    19	        "go.flipt.io/flipt/internal/storage/sql/mysql"
    20	        "go.flipt.io/flipt/internal/storage/sql/postgres"
    21	        "go.flipt.io/flipt/internal/storage/sql/sqlite"
    22	        fliptsqltesting "go.flipt.io/flipt/internal/storage/sql/testing"
    23	        "go.flipt.io/flipt/rpc/flipt"
    24	        "go.uber.org/zap/zaptest"
    25	
    26	        _ "github.com/golang-migrate/migrate/v4/source/file"
    27	)
    28	
    29	func TestOpen(t *testing.T) {
    30	        tests := []struct {
    31	                name    string
    32	                cfg     config.DatabaseConfig
    33	                driver  fliptsql.Driver
    34	                wantErr bool
    35	        }{
    36	                {
    37	                        name: "sqlite url",
    38	                        cfg: config.DatabaseConfig{
    39	                                URL:             "file:/flipt.db",
    40	                                MaxOpenConn:     5,
    41	                                ConnMaxLifetime: 30 * time.Minute,
    42	                        },
    43	                        driver: fliptsql.SQLite,
    44	                },
    45	                {
    46	                        name: "sqlite url (without slash)",
    47	                        cfg: config.DatabaseConfig{
    48	                                URL:             "file:flipt.db",
    49	                                MaxOpenConn:     5,
    50	                                ConnMaxLifetime: 30 * time.Minute,
    51	                        },
    52	                        driver: fliptsql.SQLite,
    53	                },
    54	                {
    55	                        name: "libsql url",
    56	                        cfg: config.DatabaseConfig{
    57	                                URL:             "libsql://file:/flipt.db",
    58	                                MaxOpenConn:     5,
    59	                                ConnMaxLifetime: 30 * time.Minute,
    60	                        },
    61	                        driver: fliptsql.LibSQL,
    62	                },
    63	                {
    64	                        name: "libsql with http",
    65	                        cfg: config.DatabaseConfig{
    66	                                URL:             "http://127.0.0.1:8000",
    67	                                MaxOpenConn:     5,
    68	                                ConnMaxLifetime: 30 * time.Minute,
    69	                        },
    70	                        driver: fliptsql.LibSQL,
    71	                },
    72	                {
    73	                        name: "libsql with https",
    74	                        cfg: config.DatabaseConfig{
    75	                                URL:             "https://turso.remote",
    76	                                MaxOpenConn:     5,
    77	                                ConnMaxLifetime: 30 * time.Minute,
    78	                        },
    79	                        driver: fliptsql.LibSQL,
    80	                },
    81	                {
    82	                        name: "postgres url",
    83	                        cfg: config.DatabaseConfig{
    84	                                URL: "postgres://postgres@localhost:5432/flipt?sslmode=disable",
    85	                        },
    86	                        driver: fliptsql.Postgres,
    87	                },
    88	                {
    89	                        name: "mysql url",
    90	                        cfg: config.DatabaseConfig{
    91	                                URL: "mysql://mysql@localhost:3306/flipt",
    92	                        },
    93	                        driver: fliptsql.MySQL,
    94	                },
    95	                {
    96	                        name: "cockroachdb url",
    97	                        cfg: config.DatabaseConfig{
    98	                                URL: "cockroachdb://cockroachdb@localhost:26257/flipt?sslmode=disable",
    99	                        },
   100	                        driver: fliptsql.CockroachDB,







[MSG 64] [user]
Observation: 

Here's the files and directories up to 2 levels deep in /app/internal/storage/sql/testing, excluding hidden items:
/app/internal/storage/sql/testing
/app/internal/storage/sql/testing/testing.go








[MSG 65] [assistant]
Let me look at how the testing suite is set up:

[MSG 66] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **LOW RESOLUTION** (2/14 = 14%) — moderate contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CONFIRMED_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 20:59:08

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | True |
| Failure reason | contamination |
| Contamination type | test_coupling |
| Confidence | 0.97 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent inspected the storage interfaces, config, and gRPC server wiring, recognized that DB storage needed a read-only wrapper analogous to the filesystem store, created an `internal/storage/unmodifiable` wrapper, and modified `internal/cmd/grpc.go` to wrap the store when `cfg.Storage.IsReadOnly()` is true.

**Contamination evidence**: The only F2P test, `TestModificationMethods`, imports `internal/storage/unmodifiable`, constructs `NewStore(fs.NewStore(nil))`, and asserts `require.ErrorIs(..., errReadOnly)` for every mutating method. The problem statement never specifies a package named `unmodifiable`, a constructor `NewStore`, or an unexported sentinel error `errReadOnly`. A correct fix that blocks writes at the API layer, via middleware/interceptors, or by changing SQL store implementations directly would satisfy the stated bug report but still fail this test. The test also uses an FS store rather than exercising database-backed API behavior, so it is validating the gold patch's internal mechanism rather than the user-visible requirement.

**Difficulty evidence**: None

**Full reasoning**: This task is severely contaminated. The user-facing spec is about enforcing read-only mode for database-backed storage so that API write operations are blocked when `storage.read_only=true`. But the F2P coverage does not check that behavior end-to-end. Instead, it hard-codes the gold patch's internal design: a new `internal/storage/unmodifiable` package, a `NewStore` wrapper constructor, and a specific sentinel error variable `errReadOnly`. Those are not derivable from the problem statement. An agent could implement a fully correct solution by rejecting writes in server handlers, with a gRPC interceptor, or by teaching the SQL stores themselves to deny mutations, and would still fail this test. Conversely, an implementation could pass the test by adding the wrapper methods without actually integrating them into DB-backed API execution. The representative agent clearly understood the problem and was moving toward the gold implementation, but the benchmark's F2P test is still unfair because it is tightly coupled to patch internals rather than the stated behavior.
