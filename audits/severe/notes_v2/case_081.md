# Case #81 Re-Audit Notes (v2)

**Instance**: `instance_tutao__tutanota-09c2776c0fce3db5c6e18da92b5a45dce9f013aa-vbc0d9ba8f0071fbe982809910959a6ff8884dbbf`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

## Title

Lack of progress tracking during calendar imports

## Description

Before the change, calendar imports did not provide continuous and specific feedback on the progress of the operation. For long or complex imports, the system displayed generic indicators that did not distinguish between concurrent operations, leaving the user without visibility into the status or remaining duration of their own import.

## Impact

The lack of progress per operation degraded the user experience: percept...

**Type**: ts | **Repo**: tutao/tutanota
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 7 |
| Gold patch files | 7 |
| Gold patch size | 18487 chars |
| Test patch size | 1723 chars |
| Test patch files | 1 |
| F2P tests | 1 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
test/tests/api/worker/facades/CalendarFacadeTest.ts
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 70c37c09d61793fb8a34df626c6b9687b115ecb9
git clean -fd 
git checkout 70c37c09d61793fb8a34df626c6b9687b115ecb9 
git checkout 09c2776c0fce3db5c6e18da92b5a45dce9f013aa -- test/tests/api/worker/facades/CalendarFacadeTest.ts
```

## 3. Trajectory Evidence

### Resolution Rate: 2/14 (14%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 33 |
| Claude Sonnet 4 - paper | FAIL | 21 |
| Gemini 2.5 Pro Preview - paper | FAIL | 27 |
| GPT-4o - paper | FAIL | 37 |
| GPT-5 High - paper | FAIL | 46 |
| GPT OSS - paper | FAIL | 51 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | PASS | 78 |
| Claude 4 Sonnet - 10132025 | FAIL | 98 |
| GPT-5 - 10132025 | FAIL | 37 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 89 |
| GPT-5 Codex -- debug-oct22 | FAIL | 119 |
| GLM-4.5 -- 10222025 | FAIL | 58 |
| Claude 4.5 Haiku -- 10222025 | PASS | 72 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 58
- **Total tokens**: ~45184
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
/app/schemas
/app/schemas/accounting.json
/app/schemas/usage.json
/app/schemas/storage.json
/app/schemas/tutanota.json
/app/schemas/gossip.json
/app/schemas/sys.json
/app/schemas/monitor.json
/app/schemas/base.json
/app/ci
/app/ci/Webapp.Jenkinsfile
/app/ci/SqlcipherAndroid.Jenkinsfile
/app/ci/jenkins-lib
/app/ci/OpenSSL.Jenkinsfile
/app/ci/Android.Jenkinsfile
/app/ci/Ios.Jenkinsfile
/app/ci/Desktop.Jenkinsfile
/app/ci/IosRenewCerts.Jenkinsfile
/app/make.js
/app/LICENSE.txt
/app/third-party.txt
/app/libs
/app/libs/linkify.js
/app/libs/purify.js
/app/libs/libs.d.ts
/app/libs/qrcode.js
/app/libs/cborg.js
/app/libs/s.js
/app/libs/stream.js
/app/libs/linkify-html.js
/app/libs/luxon.js
/app/libs/squire-raw.js
/app/libs/jszip.js
/app/libs/mithril.js
/app/webapp.js
/app/src
/app/src/settings
/app/src/serviceworker
/app/src/login
/app/src/braintree.html
/app/src/contacts
/app/src/types.d.ts
/app/src/mail
/app/src/RootView.ts
/app/src/native
/app/src/global.d.ts
/app/src/termination
/app/src/misc
/app/src/offline
/app/src/app.ts
/app/src/translations
/app/src/gui
/app/src/knowledgebase
/app/src/templates
/app/src/api
/app/src/search
/app/src/subscription
/app/src/desktop
/app/src/ApplicationPaths.ts
/app/src/file
/app/src/sharing
/app/src/support
/app/src/polyfill.ts
/app/src/calendar
/app/node_modules
/app/node_modules/is-number
/app/node_modules/npmlog
/app/node_modules/is-binary-path
/app/node_modules/is-plain-object
/app/node_modules/qs
/app/node_modules/http-errors
/app/node_modules/p-limit
/app/node_modules/jszip
/app/node_modules/randombytes
/app/node_modules/on-finished
/app/node_modules/mime-db
/app/node_modules/browser-process-hrtime
/app/node_modules/universal-user-agent
/app/node_modules/import-fresh
/app/node_modules/make-fetch-happen
/app/node_modules/yauzl
/app/node_modules/cross-spawn-windows-exe
/app/node_modules/console-control-strings
/app/node_modules/is-arrayish
/app/node_modules/isexe
/app/node_modules/humanize-ms
/app/node_modules/globalthis
/app/node_modules/theredoc
/app/node_modules/cookie-signature
/app/node_modules/rollup-plugin-terser
/app/node_modules/author-regex
/app/node_modules/negotiator
/app/node_modules/@gar
/app/node_modules/esbuild-linux-64
/app/node_modules/util-deprecate
/app/node_modules/minipass-pipeline
/app/node_modules/env-paths
/app/node_modules/fast-glob
/app/node_modules/through
/app/node_modules/escape-html
/app/node_modules/strip-ansi
/app/node_modules/xml-name-validator
/app/node_modules/chokidar
/app/node_modules/defer-to-connect
/app/node_modules/is-module
/app/node_modules/asar
/app/node_modules/yargs
/app/node_modules/dotenv
/app/node_modules/napi-build-utils
/app/node_modules/fs.realpath
/app/node_modules/cacheable-lookup
/app/node_modules/minipass-collect
/app/node_modules/pify
/app/node_modules/minimist
/app/node_modules/mithril
/app/node_modules/typescript
/app/node_modules/y18n
/app/node_modules/event-stream
/app/node_modules/mkdirp
/app/node_modules/fromentries
/app/node_modules/string_decoder
/app/node_modules/responselike
/app/node_modules/json-schema-traverse
/app/node_modules/strip-outer
/app/node_modules/jws
/app/node_modules/mime
/app/node_modules/json-stable-stringify-without-jsonify
/app/node_modules/buffer
/app/node_modules/tar-stream
/app/node_modules/read-config-file
/app/node_modules/glob
/app/node_modules/octokit
/app/node_modules/serve-static
/app/node_modules/dotenv-expand
/app/node_modules/esprima
/app/node_modules/xhr2
/app/node_modules/entities
/app/node_modules/reusify
/app/node_modules/qrcode-svg
/app/node_modules/infer-owner
/app/node_modules/body-parser
/app/node_modules/inflight
/app/node_modules/eslint-config-prettier
/app/node_modules/builtin-modules
/app/node_modules/unpipe
/app/node_modules/ignore
/app/node_modules/function-bind
/app/node_modules/dir-compare
/app/node_modules/duplexer
/app/node_modules/eslint-scope
/app/node_modules/split
/app/node_modules/fs-extra
/app/node_modules/async-exit-hook
/app/node_modules/detect-node
/app/node_modules/sprintf-js
/app/node_modules/wrappy
/app/node_modules/json5
/app/node_modules/path-to-regexp
/app/node_modules/whatwg-mimetype
/app/node_modules/detect-libc
/app/node_modules/es6-error
/app/node_modules/read-pkg
/app/node_modules/type-fest
/app/node_modules/v8-compile-cache
/app/node_modules/filelist
/app/node_modules/truncate-utf8-bytes
/app/node_modules/clean-stack
/app/node_modules/jwa
/app/node_modules/serialize-error
/app/node_modules/temp-file
/app/node_modules/flatted
/app/node_modules/@npmcli
/app/node_modules/electron-builder
/app/node_modules/xmlbuilder
/app/node_modules/global-agent
/app/node_modules/callsites
/app/node_modules/querystring
/app/node_modules/agentkeepalive
/app/node_modules/delayed-stream
/app/node_modules/minimatch
/app/node_modules/color-support
/app/node_modules/has-symbols
/app/node_modules/yocto-queue
/app/node_modules/is-ci
/app/node_modules/emoji-regex
/app/node_modules/file-entry-cache
/app/node_modules/keyv
/app/node_modules/magic-string
/app/node_modules/abbrev
/app/node_modules/get-package-info
/app/node_modules/spdx-expression-parse
/app/node_modules/normalize-url
/app/node_modules/agent-base
/app/node_modules/espree
/app/node_modules/xml2js
/app/node_modules/json-buffer
/app/node_modules/lodash.isequal
/app/node_modules/esutils
/app/node_modules/@humanwhocodes
/app/node_modules/media-typer
/app/node_modules/tough-cookie
/app/node_modules/fast-levenshtein
/app/node_modules/semver-compare
/app/node_modules/shebang-command
/app/node_modules/rollup
/app/node_modules/wide-align
/app/node_modules/simple-update-notifier
/app/node_modules/@nodelib
/app/node_modules/w3c-hr-time
/app/node_modules/uuid
/app/node_modules/combined-stream
/app/node_modules/@eslint
/app/node_modules/quibble
/app/node_modules/fs-minipass
/app/node_modules/ssri
/app/node_modules/ospec
/app/node_modules/parse-json
/app/node_modules/utf8-byte-length
/app/node_modules/open
/app/node_modules/sumchecker
/app/node_modules/globby
/app/node_modules/is-wsl
/app/node_modules/rxjs
/app/node_modules/data-urls
/app/node_modules/adler-32
/app/node_modules/tmp-promise
/app/node_modules/once
/app/node_modules/lodash
/app/node_modules/ini
/app/node_modules/esbuild
/app/node_modules/universal-github-app-jwt
/app/node_modules/p-map
/app/node_modules/punycode
/app/node_modules/fresh
/app/node_modules/@octokit
/app/node_modules/estree-walker
/app/node_modules/domexception
/app/node_modules/ejs
/app/node_modules/js-tokens
/app/node_modules/concat-map
/app/node_modules/bytes
/app/node_modules/is-arguments
/app/node_modules/hosted-git-info
/app/node_modules/utils-merge
/app/node_modules/lodash.isboolean
/app/node_modules/lodash.get
/app/node_modules/@tootallnate
/app/node_modules/util
/app/node_modules/uri-js
/app/node_modules/dompurify
/app/node_modules/ajv
/app/node_modules/asynckit
/app/node_modules/socks-proxy-agent
/app/node_modules/tar-fs
/app/node_modules/are-we-there-yet
/app/node_modules/inherits
/app/node_modules/is-reference
/app/node_modules/builder-util-runtime
/app/node_modules/mime-types
/app/node_modules/process-nextick-args
/app/node_modules/gauge
/app/node_modules/chalk
/app/node_modules/validate-npm-package-license
/app/node_modules/object-keys
/app/node_modules/graceful-readlink
/app/node_modules/end-of-stream
/app/node_modules/yaml
/app/node_modules/simple-concat
/app/node_modules/eslint-utils
/app/node_modules/rc
/app/node_modules/has-flag
/app/node_modules/lazy-val
/app/node_modules/eslint
/app/node_modules/minipass-flush
/app/node_modules/read-pkg-up
/app/node_modules/has-unicode
/app/node_modules/source-map-support
/app/node_modules/bluebird
/app/node_modules/formdata-polyfill
/app/node_modules/err-code
/app/node_modules/json-stringify-safe
/app/node_modules/https-proxy-agent
/app/node_modules/is-extglob
/app/node_modules/path-parse
/app/node_modules/prettier
/app/node_modules/delegates
/app/node_modules
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
src/api/main/MainLocator.ts:
   392	                this.userManagementFacade = userManagementFacade
   393	                this.contactFormFacade = contactFormFacade
   394	                this.deviceEncryptionFacade = deviceEncryptionFacade
   395	                this.serviceExecutor = serviceExecutor
   396	                this.eventController = new EventController(logins)
   397	                this.progressTracker = new ProgressTracker()
   398	                this.operationProgressTracker = new OperationProgressTracker()
   399	                this.search = new SearchModel(this.searchFacade)
   400	                this.entityClient = new EntityClient(restInterface)
   401	                this.cryptoFacade = cryptoFacade
   402	                this.cacheStorage = cacheStorage
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 40] [user]
Observation: 

No replacement was performed, old_str `import type { ExposedProgressTracker } from "../main/ProgressTracker"` did not appear verbatim in /app/src/api/worker/WorkerImpl.ts.




[MSG 41] [assistant]
## Step 3: Update WorkerImpl to include operationProgressTracker in MainInterface

[MSG 42] [user]
Observation: 
Here's the result of running `cat -n` on /app/src/api/worker/WorkerImpl.ts:
     1	import type { Commands } from "../common/MessageDispatcher"
     2	import { errorToObj, MessageDispatcher, Request, WorkerTransport } from "../common/MessageDispatcher"
     3	import { CryptoError } from "../common/error/CryptoError"
     4	import { BookingFacade } from "./facades/BookingFacade"
     5	import { NotAuthenticatedError } from "../common/error/RestError"
     6	import { ProgrammingError } from "../common/error/ProgrammingError"
     7	import { initLocator, locator, resetLocator } from "./WorkerLocator"
     8	import { assertWorkerOrNode, isMainOrNode } from "../common/Env"
     9	import type { ContactFormFacade } from "./facades/ContactFormFacade"
    10	import type { BrowserData } from "../../misc/ClientConstants"
    11	import type { InfoMessage } from "../common/CommonTypes"
    12	import { CryptoFacade } from "./crypto/CryptoFacade"
    13	import { delay, lazyMemoized } from "@tutao/tutanota-utils"
    14	import { urlify } from "./Urlifier"
    15	import type { GiftCardFacade } from "./facades/GiftCardFacade"
    16	import type { LoginFacade } from "./facades/LoginFacade"
    17	import type { CustomerFacade } from "./facades/CustomerFacade"
    18	import type { GroupManagementFacade } from "./facades/GroupManagementFacade"
    19	import { ConfigurationDatabase } from "./facades/ConfigurationDatabase"
    20	import { CalendarFacade } from "./facades/CalendarFacade"
    21	import { MailFacade } from "./facades/MailFacade"
    22	import { ShareFacade } from "./facades/ShareFacade"
    23	import { CounterFacade } from "./facades/CounterFacade"
    24	import { Indexer } from "./search/Indexer"
    25	import { SearchFacade } from "./search/SearchFacade"
    26	import { MailAddressFacade } from "./facades/MailAddressFacade"
    27	import { FileFacade } from "./facades/FileFacade.js"
    28	import { UserManagementFacade } from "./facades/UserManagementFacade"
    29	import { exposeLocal, exposeRemote } from "../common/WorkerProxy"
    30	import type { SearchIndexStateInfo } from "./search/SearchTypes"





[MSG 43] [assistant]
Let me first check the WorkerImpl file structure:

[MSG 44] [user]
Observation: 
44:import { ExposedProgressTracker } from "../main/ProgressTracker.js"
92:	readonly progressTracker: ExposedProgressTracker




[MSG 45] [user]
Observation: 
Here's the result of running `cat -n` on /app/src/api/worker/WorkerImpl.ts:
    40	import { BlobAccessTokenFacade } from "./facades/BlobAccessTokenFacade.js"
    41	import { WebsocketConnectivityListener } from "../../misc/WebsocketConnectivityModel.js"
    42	import { EventBusClient } from "./EventBusClient.js"
    43	import { EntropyFacade } from "./facades/EntropyFacade.js"
    44	import { ExposedProgressTracker } from "../main/ProgressTracker.js"
    45	import { ExposedEventController } from "../main/EventController.js"
    46	
    47	assertWorkerOrNode()
    48	
    49	export interface WorkerRandomizer {
    50	        generateRandomNumber(numBytes: number): Promise<number>





[MSG 46] [user]
Observation: 



The file /app/src/api/worker/WorkerImpl.ts has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/worker/WorkerImpl.ts:
    39	import { LoginListener } from "../main/LoginListener"
    40	import { BlobAccessTokenFacade } from "./facades/BlobAccessTokenFacade.js"
    41	import { WebsocketConnectivityListener } from "../../misc/WebsocketConnectivityModel.js"
    42	import { EventBusClient } from "./EventBusClient.js"
    43	import { EntropyFacade } from "./facades/EntropyFacade.js"
    44	import { ExposedProgressTracker } from "../main/ProgressTracker.js"
    45	import { ExposedOperationProgressTracker } from "../main/OperationProgressTracker.js"
    46	import { ExposedEventController } from "../main/EventController.js"
    47	
    48	assertWorkerOrNode()
    49	
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 47] [user]
Observation: 
Here's the result of running `cat -n` on /app/src/api/worker/WorkerImpl.ts:
    88	
    89	/** Interface for the "main"/webpage context of the app, interface for the worker client. */
    90	export interface MainInterface {
    91	        readonly loginListener: LoginListener
    92	        readonly wsConnectivityListener: WebsocketConnectivityListener
    93	        readonly progressTracker: ExposedProgressTracker
    94	        readonly eventController: ExposedEventController
    95	}
    96	
    97	type WorkerRequest = Request<WorkerRequestType>
    98	





[MSG 48] [assistant]
Now let's add the operationProgressTracker to the MainInterface:

[MSG 49] [user]
Observation: 













The file /app/src/api/worker/WorkerImpl.ts has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/worker/WorkerImpl.ts:
    84	        readonly random: WorkerRandomizer
    85	        readonly eventBus: ExposedEventBus
    86	        readonly entropyFacade: EntropyFacade
    87	}
    88	
    89	/** Interface for the "main"/webpage context of the app, interface for the worker client. */
    90	export interface MainInterface {
    91	        readonly loginListener: LoginListener
    92	        readonly wsConnectivityListener: WebsocketConnectivityListener
    93	        readonly progressTracker: ExposedProgressTracker
    94	        readonly operationProgressTracker: ExposedOperationProgressTracker
    95	        readonly eventController: ExposedEventController
    96	}
    97	
    98	type WorkerRequest = Request<WorkerRequestType>
    99	
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 50] [user]
Observation: 
Here's the result of running `cat -n` on /app/src/api/main/WorkerClient.ts:
   110	                        facade: exposeLocal<MainInterface, MainRequestType>({
   111	                                get loginListener() {
   112	                                        return locator.loginListener
   113	                                },
   114	                                get wsConnectivityListener() {
   115	                                        return locator.connectivityModel
   116	                                },
   117	                                get progressTracker() {
   118	                                        return locator.progressTracker
   119	                                },
   120	                                get eventController() {
   121	                                        return locator.eventController
   122	                                }
   123	                        }),
   124	                }
   125	        }
   126	
   127	        getWorkerInterface(): WorkerInterface {
   128	                return exposeRemote<WorkerInterface>(async (request) => this._postRequest(request))
   129	        }
   130	





[MSG 51] [assistant]
## Step 4: Update WorkerClient to expose operationProgressTracker

[MSG 52] [user]
Observation: 





























The file /app/src/api/main/WorkerClient.ts has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/main/WorkerClient.ts:
   105	                        },
   106	                        infoMessage: (message: MainRequest) => {
   107	                                this.infoMessages(downcast(message.args[0]))
   108	                                return Promise.resolve()
   109	                        },
   110	                        facade: exposeLocal<MainInterface, MainRequestType>({
   111	                                get loginListener() {
   112	                                        return locator.loginListener
   113	                                },
   114	                                get wsConnectivityListener() {
   115	                                        return locator.connectivityModel
   116	                                },
   117	                                get progressTracker() {
   118	                                        return locator.progressTracker
   119	                                },
   120	                                get operationProgressTracker() {
   121	                                        return locator.operationProgressTracker
   122	                                },
   123	                                get eventController() {
   124	                                        return locator.eventController
   125	                                }
   126	                        }),
   127	                }
   128	        }
   129	
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 53] [user]
Observation: 
Here's the result of running `cat -n` on /app/src/api/main/WorkerClient.ts:
   125	                                }
   126	                        }),
   127	                }
   128	        }
   129	
   130	        getWorkerInterface(): WorkerInterface {
   131	                return exposeRemote<WorkerInterface>(async (request) => this._postRequest(request))
   132	        }
   133	
   134	        restRequest(...args: Parameters<RestClient["request"]>): Promise<any | null> {
   135	                return this._postRequest(new Request("restRequest", Array.from(arguments)))
   136	        }
   137	
   138	        /** @private visible for tests */
   139	        async _postRequest(msg: Request<WorkerRequestType>): Promise<any> {
   140	                await this.initialized





[MSG 54] [assistant]
Now let's add a getter method to WorkerClient to access the operationProgressTracker:

[MSG 55] [user]
Observation: 












The file /app/src/api/main/WorkerClient.ts has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/main/WorkerClient.ts:
   125	                                }
   126	                        }),
   127	                }
   128	        }
   129	
   130	        getWorkerInterface(): WorkerInterface {
   131	                return exposeRemote<WorkerInterface>(async (request) => this._postRequest(request))
   132	        }
   133	
   134	        getOperationProgressTracker(): ExposedOperationProgressTracker {
   135	                return this.getWorkerInterface().operationProgressTracker
   136	        }
   137	
   138	        restRequest(...args: Parameters<RestClient["request"]>): Promise<any | null> {
   139	                return this._postRequest(new Request("restRequest", Array.from(arguments)))
   140	        }
   141	
Review the changes and make sure they are as expected. Edit the file again if necessary.




[MSG 56] [assistant]
Let's add the getter method just after the getWorkerInterface method:

[MSG 57] [user]
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
**Analyzed**: 2026-04-12 20:37:49

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | test_coupling |
| Confidence | 0.98 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent correctly identified that the fix required per-operation progress rather than the existing global worker progress, and it began wiring a new OperationProgressTracker through MainLocator, WorkerImpl, and WorkerClient. It created the new tracker class and added interface exposure, but timed out before finishing the CalendarFacade/dialog integration.

**Contamination evidence**: The F2P test patch does not test the user-facing requirement from the problem statement. Instead, it updates CalendarFacade tests to call the internal helper `_saveCalendarEvents(eventsWrapper, () => Promise.resolve())`, thereby requiring a new callback parameter on a private/internal method. The problem statement never mentions `CalendarFacade`, `_saveCalendarEvents`, a callback-based progress API, or any required method signature. A valid implementation of per-import progress could use a different internal design and still satisfy the stated behavior, but these tests would fail because they are coupled to the gold patch's internal refactor.

**Difficulty evidence**: None

**Full reasoning**: This task is contaminated. The issue described is purely behavioral and user-facing: calendar imports should expose continuous, operation-specific progress and mark completion cleanly. But the fail-to-pass tests are not checking that behavior. They are pre-staged from the gold commit and only modify an existing unit test suite so that it calls a specific internal method, `_saveCalendarEvents`, with an extra callback argument. That means the tests require the candidate patch to adopt the gold patch's exact internal API shape. An agent could reasonably solve the stated problem by implementing per-operation progress in another way—for example by extending the existing worker progress channel, adding operation IDs elsewhere, or keeping `_saveCalendarEvents` unchanged and routing progress externally—and still be rejected. The representative agent actually understood the intended feature and started implementing essentially the same architecture, but it timed out before completion. Its failure was not evidence that the task is inherently hard; the stronger signal is that the F2P tests themselves are coupled to undisclosed internals rather than the spec.
