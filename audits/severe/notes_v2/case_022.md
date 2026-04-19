# Case #22 Re-Audit Notes (v2)

**Instance**: `instance_tutao__tutanota-219bc8f05d7b980e038bc1524cb021bf56397a1b-vee878bb72091875e912c52fc32bc60ec3760227b`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

**Title:** Inconsistent message handling in `EventBusClient` affects reliable WebSocket updates

**Description**

The `EventBusClient` in `src/api/worker/EventBusClient.ts` does not handle incoming WebSocket messages in a consistent way.  

Internal naming conventions make the message handler difficult to use predictably, and the way message types are distinguished relies on ad-hoc strings.  

Because of this, entity update messages are not guaranteed to be processed in strict order, and unread ...

**Type**: ts | **Repo**: tutao/tutanota
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 1 |
| Gold patch files | 1 |
| Gold patch size | 9876 chars |
| Test patch size | 930 chars |
| Test patch files | 1 |
| F2P tests | 78 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
test/api/worker/EventBusClientTest.ts
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 9dfb7c231f98a2d3bf48a99577d8a55cfdb2480b
git clean -fd 
git checkout 9dfb7c231f98a2d3bf48a99577d8a55cfdb2480b 
git checkout 219bc8f05d7b980e038bc1524cb021bf56397a1b -- test/api/worker/EventBusClientTest.ts
```

## 3. Trajectory Evidence

### Resolution Rate: 7/14 (50%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | PASS | 44 |
| Claude Sonnet 4 - paper | FAIL | 18 |
| Gemini 2.5 Pro Preview - paper | FAIL | 13 |
| GPT-4o - paper | FAIL | 38 |
| GPT-5 High - paper | FAIL | 31 |
| GPT OSS - paper | PASS | 51 |
| Kimi - paper | FAIL | 46 |
| Claude 4.5 Sonnet - 10132025 | PASS | 83 |
| Claude 4 Sonnet - 10132025 | PASS | 34 |
| GPT-5 - 10132025 | PASS | 52 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 6 |
| GPT-5 Codex -- debug-oct22 | FAIL | 109 |
| GLM-4.5 -- 10222025 | PASS | 32 |
| Claude 4.5 Haiku -- 10222025 | PASS | 68 |

### Representative Trajectory: GPT-5 High - paper
- **Resolved**: False
- **Turns**: 31
- **Total tokens**: ~66072
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
/app/app-android
/app/app-android/app
/app/app-android/test
/app/app-android/gradle
/app/app-android/gradle.properties
/app/app-android/build.gradle
/app/app-android/settings.gradle
/app/app-android/gradlew
/app/Ios.Jenkinsfile
/app/LICENSE.txt
/app/src
/app/src/calendar
/app/src/native
/app/src/settings
/app/src/ApplicationPaths.ts
/app/src/translations
/app/src/polyfill.ts
/app/src/RootView.ts
/app/src/misc
/app/src/search
/app/src/types.d.ts
/app/src/templates
/app/src/knowledgebase
/app/src/gui
/app/src/global.d.ts
/app/src/login
/app/src/app.ts
/app/src/serviceworker
/app/src/subscription
/app/src/braintree.html
/app/src/desktop
/app/src/sharing
/app/src/api
/app/src/support
/app/src/contacts
/app/src/file
/app/src/mail
/app/jenkins-lib
/app/jenkins-lib/util.groovy
/app/package-lock.json
/app/make.js
/app/types
/app/types/globals.d.ts
/app/types/ospec.d.ts
/app/third-party.txt
/app/bump-version.js
/app/tsconfig.json
/app/doc
/app/doc/Overview.svg
/app/doc/BUILDING.md
/app/doc/theming.md
/app/doc/notifications.md
/app/doc/events.md
/app/doc/HACKING.md
/app/Desktop.Jenkinsfile
/app/tsconfig_common.json
/app/android.js
/app/Android.Jenkinsfile
/app/resources
/app/resources/favicon
/app/resources/scripts
/app/resources/desktop-icons
/app/resources/images
/app/resources/encoded
/app/tutao-pub.pem
/app/app-ios
/app/app-ios/fastlane
/app/app-ios/tutanotaTests
/app/app-ios/tutanota copy2-Info.plist
/app/app-ios/tutanota copy-Info.plist
/app/app-ios/tutanota
/app/app-ios/tutanota.xcodeproj
/app/start-desktop.sh
/app/webapp.js
/app/desktop.js
/app/package.json
/app/tutao-pub-test.pem
/app/Webapp.Jenkinsfile
/app/packages
/app/packages/tutanota-utils
/app/packages/tutanota-crypto
/app/packages/tutanota-build-server
/app/packages/tutanota-test-utils
/app/test
/app/test/TestBuilder.js
/app/test/test.js
/app/test/types
/app/test/api
/app/test/tsconfig.json
/app/test/client
/app/buildSrc
/app/buildSrc/publish.js
/app/buildSrc/createGithubReleasePage.js
/app/buildSrc/windows-installer.nsh
/app/buildSrc/createHtml.js
/app/buildSrc/prepareMobileBuild.js
/app/buildSrc/updateLibs.js
/app/buildSrc/signDesktopClients.js
/app/buildSrc/LaunchHtml.js
/app/buildSrc/nativeLibraryRollupPlugin.js
/app/buildSrc/mac-entitlements.plist
/app/buildSrc/DevBuild.js
/app/buildSrc/RollupUtils.js
/app/buildSrc/notarize.cjs
/app/buildSrc/winsigner.cjs
/app/buildSrc/buildWebapp.js
/app/buildSrc/nativeLibraryProvider.js
/app/buildSrc/installerSigner.js
/app/buildSrc/graph.js
/app/buildSrc/RollupPlugins.js
/app/buildSrc/buildUtils.js
/app/buildSrc/RollupDebugConfig.js
/app/buildSrc/index.template.js
/app/buildSrc/electron-package-json-template.js
/app/buildSrc/env.js
/app/buildSrc/RollupConfig.js
/app/buildSrc/fixFdroidDeps.js
/app/buildSrc/fetchDictionaries.js
/app/buildSrc/Builder.js
/app/buildSrc/DesktopBuilder.js
/app/README.md
/app/node_modules
/app/node_modules/napi-build-utils
/app/node_modules/ecdsa-sig-formatter
/app/node_modules/code-point-at
/app/node_modules/deep-extend
/app/node_modules/merge-stream
/app/node_modules/http-signature
/app/node_modules/rcedit
/app/node_modules/btoa-lite
/app/node_modules/registry-url
/app/node_modules/prepend-http
/app/node_modules/lru-cache
/app/node_modules/which
/app/node_modules/type-fest
/app/node_modules/is-glob
/app/node_modules/serve-static
/app/node_modules/argparse
/app/node_modules/chokidar
/app/node_modules/config-chain
/app/node_modules/ansi-regex
/app/node_modules/get-caller-file
/app/node_modules/har-schema
/app/node_modules/@malept
/app/node_modules/parseurl
/app/node_modules/buffer-from
/app/node_modules/source-map-fast
/app/node_modules/encoding
/app/node_modules/responselike
/app/node_modules/widest-line
/app/node_modules/sourcemap-codec
/app/node_modules/is-regexp
/app/node_modules/vary
/app/node_modules/buffer
/app/node_modules/strip-json-comments
/app/node_modules/serialize-javascript
/app/node_modules/has-yarn
/app/node_modules/read-config-file
/app/node_modules/bytes
/app/node_modules/uri-js
/app/node_modules/is-reference
/app/node_modules/is-binary-path
/app/node_modules/semver-compare
/app/node_modules/gauge
/app/node_modules/ini
/app/node_modules/testdouble
/app/node_modules/is-extglob
/app/node_modules/yallist
/app/node_modules/lodash.isplainobject
/app/node_modules/semver-diff
/app/node_modules/fill-range
/app/node_modules/map-stream
/app/node_modules/http-cache-semantics
/app/node_modules/zx
/app/node_modules/load-json-file
/app/node_modules/esprima
/app/node_modules/on-finished
/app/node_modules/@nodelib
/app/node_modules/serialize-error
/app/node_modules/micromatch
/app/node_modules/chownr
/app/node_modules/pako
/app/node_modules/buffer-equal
/app/node_modules/crc-32
/app/node_modules/make-dir
/app/node_modules/cfb
/app/node_modules/estree-walker
/app/node_modules/caseless
/app/node_modules/tar-fs
/app/node_modules/get-stream
/app/node_modules/is-obj
/app/node_modules/to-regex-range
/app/node_modules/signal-exit
/app/node_modules/deepmerge
/app/node_modules/electron-publish
/app/node_modules/json-stringify-safe
/app/node_modules/stringify-object-es5
/app/node_modules/unpipe
/app/node_modules/terser
/app/node_modules/lodash.once
/app/node_modules/@sindresorhus
/app/node_modules/typedarray
/app/node_modules/bluebird
/app/node_modules/accepts
/app/node_modules/buffer-fill
/app/node_modules/rollup-plugin-terser
/app/node_modules/qrcode-svg
/app/node_modules/jwa
/app/node_modules/latest-version
/app/node_modules/asn1
/app/node_modules/isarray
/app/node_modules/js-tokens
/app/node_modules/lodash.includes
/app/node_modules/proto-list
/app/node_modules/pupa
/app/node_modules/matcher
/app/node_modules/keytar
/app/node_modules/boxen
/app/node_modules/read-pkg
/app/node_modules/nollup
/app/node_modules/@rollup
/app/node_modules/object-keys
/app/node_modules/octokit
/app/node_modules/extsprintf
/app/node_modules/app-builder-bin
/app/node_modules/prebuild-install
/app/node_modules/methods
/app/node_modules/ajv
/app/node_modules/cross-spawn
/app/node_modules/theredoc
/app/node_modules/glob-parent
/app/node_modules/tr46
/app/node_modules/universal-user-agent
/app/node_modules/supports-color
/app/node_modules/path-key
/app/node_modules/verror
/app/node_modules/json-schema
/app/node_modules/systemjs
/app/node_modules/ipaddr.js
/app/node_modules/data-uri-to-buffer
/app/node_modules/ignore
/app/node_modules/node-fetch
/app/node_modules/universalify
/app/node_modules/quibble
/app/node_modules/is-fullwidth-code-point
/app/node_modules/lie
/app/node_modules/spdx-expression-parse
/app/node_modules/path-type
/app/node_modules/detect-libc
/app/node_modules/yargs-parser
/app/node_modules/error-ex
/app/node_modules/cross-spawn-windows-exe
/app/node_modules/raw-body
/app/node_modules/chalk
/app/node_modules/toidentifier
/app/node_modules/merge2
/app/node_modules/keyv
/app/node_modules/is-plain-obj
/app/node_modules/ejs
/app/node_modules/async
/app/node_modules/p-locate
/app/node_modules/escalade
/app/node_modules/is-typedarray
/app/node_modules/@tutao
/app/node_modules/compare-version
/app/node_modules/reusify
/app/node_modules/content-disposition
/app/node_modules/ansi-styles
/app/node_modules/json-buffer
/app/node_modules/detect-node
/app/node_modules/safer-buffer
/app/node_modules/fetch-blob
/app/node_modules/globalthis
/app/node_modules/fast-json-stable-stringify
/app/node_modules/sumchecker
/app/node_modules/dir-compare
/app/node_modules/path-to-regexp
/app/node_modules/source-map-support
/app/node_modules/global-dirs
/app/node_modules/buffer-alloc-unsafe
/app/node_modules/escape-string-regexp
/app/node_modules/fs-constants
/app/node_modules/jsonfile
/app/node_modules/delayed-stream
/app/node_modules/dotenv
/app/node_modules/body-parser
/app/node_modules/end-of-stream
/app/node_modules/lodash.isinteger
/app/node_modules/lodash.isequal
/app/node_modules/strip-ansi
/app/node_modules/wrappy
/app/node_modules/buffer-equ
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
README.md                   test/
Webapp.Jenkinsfile          third-party.txt
android.js                  tsconfig.json
app-android/                tsconfig_common.json
app-ios/                    tutao-pub-test.pem
buildSrc/                   tutao-pub.pem
bump-version.js             types/
desktop.js                  webapp.js
doc/                        

.editorconfig               fdroid-metadata-workaround/
.git/                       jenkins-lib/
.github/                    libs/
.gitignore                  make.js
.npmrc                      node_modules/
.nvmrc                      package-lock.json
.vscode/                    package.json
Android.Jenkinsfile         packages/
Desktop.Jenkinsfile         resources/
Ios.Jenkinsfile             src/
LICENSE.txt                 start-desktop.sh
README.md                   test/
Webapp.Jenkinsfile          third-party.txt
android.js                  tsconfig.json
app-android/                tsconfig_common.json
app-ios/                    tutao-pub-test.pem
buildSrc/                   tutao-pub.pem
bump-version.js             types/
desktop.js                  webapp.js
doc/                        

.editorconfig               fdroid-metadata-workaround/
.git/                       jenkins-lib/
.github/                    libs/
.gitignore                  make.js
.npmrc                      node_modules/
.nvmrc                      package-lock.json
.vscode/                    package.json
Android.Jenkinsfile         packages/
Desktop.Jenkinsfile         resources/
Ios.Jenkinsfile             src/
LICENSE.txt                 start-desktop.sh
README.md                   test/
Webapp.Jenkinsfile          third-party.txt
android.js                  tsconfig.json
app-android/                tsconfig_common.json
app-ios/                    tutao-pub-test.pem
buildSrc/                   tutao-pub.pem
bump-version.js             types/
desktop.js                  webapp.js
doc/                        


.editorconfig               fdroid-metadata-workaround/
.git/                       jenkins-lib/
.github/                    libs/
.gitignore                  make.js
.npmrc                      node_modules/
.nvmrc                      package-lock.json
.vscode/                    package.json
Android.Jenkinsfile         packages/
Desktop.Jenkinsfile         resources/
Ios.Jenkinsfile             src/
LICENSE.txt                 start-desktop.sh
README.md                   test/
Webapp.Jenkinsfile          third-party.txt
android.js                  tsconfig.json
app-android/                tsconfig_common.json
app-ios/                    tutao-pub-test.pem
buildSrc/                   tutao-pub.pem
bump-version.js             types/
desktop.js                  webapp.js
doc/                        

.editorconfig               fdroid-metadata-workaround/
.git/                       jenkins-lib/
.github/                    libs/
.gitignore                  make.js
.npmrc                      node_modules/
.nvmrc                      package-lock.json
.vscode/                    package.json
Android.Jenkinsfile         packages/
Desktop.Jenkinsfile         resources/
Ios.Jenkinsfile             src/
LICENSE.txt                 start-desktop.sh
README.md                   test/
Webapp.Jenkinsfile          third-party.txt
android.js                  tsconfig.json
app-android/                tsconfig_common.json
app-ios/                    tutao-pub-test.pem
buildSrc/                   tutao-pub.pem
bump-version.js             types/
desktop.js                  webapp.js
doc/                        

.editorconfig               fdroid-metadata-workaround/
.git/                       jenkins-lib/
.github/                    libs/
.gitignore                  make.js
.npmrc                      node_modules/
.nvmrc                      package-lock.json
.vscode/                    package.json
Android.Jenkinsfile         packages/
Desktop.Jenkinsfile         resources/
Ios.Jenkinsfile             src/
LICENSE.txt                 start-desktop.sh
README.md                   test/
Webapp.Jenkinsfile          third-party.txt
android.js                  tsconfig.json
app-android/                tsconfig_common.json
app-ios/                    tutao-pub-test.pem
buildSrc/                   tutao-pub.pem
bump-version.js             types/
desktop.js                  webapp.js
doc/                        


.editorconfig               fdroid-metadata-workaround/
.git/                       jenkins-lib/
.github/                    libs/
.gitignore                  make.js
.npmrc                      node_modules/
.nvmrc                      package-lock.json
.vscode/                    package.json
Android.Jenkinsfile         packages/
Desktop.Jenkinsfile         resources/
Ios.Jenkinsfile             src/
LICENSE.txt                 start-desktop.sh
README.md                   test/
Webapp.Jenkinsfile          third-party.txt
android.js                  tsconfig.json
app-android/                tsconfig_common.json
app-ios/                    tutao-pub-test.pem
buildSrc/                   tutao-pub.pem
bump-version.js             types/
desktop.js                  webapp.js
doc/                        

.editorconfig               fdroid-metadata-work

[MSG 26] [user]
Observation: 




testing version: 3.93.5
Called with forceRestart
No build server running, starting a new one
Spawning build server process with args: /app/packages/tutanota-build-server/dist/BuildServerStarter.js,-d,/tmp/tutanota-build-server/root/test,--spaRedirect,--watchFolders,/app/api:/app/client:/src,/app/TestBuilder.js and options: {"detached":true,"serialization":"json","stdio":["ignore","pipe","pipe"]}
Server: Failed to run build server:  Error [ERR_MODULE_NOT_FOUND]: Cannot find module '/app/TestBuilder.js' imported from /app/packages/tutanota-build-server/dist/BuildServer.js
    at new NodeError (node:internal/errors:387:5)
    at finalizeResolution (node:internal/modules/esm/resolve:330:11)
    at moduleResolve (node:internal/modules/esm/resolve:907:10)
    at defaultResolve (node:internal/modules/esm/resolve:1115:11)
    at nextResolve (node:internal/modules/esm/loader:163:28)
    at ESMLoader.resolve (node:internal/modules/esm/loader:841:30)
    at ESMLoader.getModuleJob (node:internal/modules/esm/loader:424:18)
    at ESMLoader.import (node:internal/modules/esm/loader:525:22)
    at importModuleDynamically (node:internal/modules/esm/translators:110:35)
    at importModuleDynamicallyCallback (node:internal/process/esm_loader:35:14) {
  code: 'ERR_MODULE_NOT_FOUND'
}

build finished!
node:internal/modules/cjs/loader:1031
  throw err;
  ^

Error: Cannot find module '/app/build/bootstrapTests-api.js'
    at Function.Module._resolveFilename (node:internal/modules/cjs/loader:1028:15)
    at Function.Module._load (node:internal/modules/cjs/loader:873:27)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:81:12)
    at node:internal/main/run_main_module:22:47 {
  code: 'MODULE_NOT_FOUND',
  requireStack: []
}
Exit code: 1





[MSG 27] [user]
Observation: 
Here's the result of running `cat -n` on /app/package.json:
     1	{
     2	        "name": "tutanota",
     3	        "version": "3.93.5",
     4	        "license": "GPL-3.0",
     5	        "repository": {
     6	                "type": "git",
     7	                "url": "https://github.com/tutao/tutanota.git"
     8	        },
     9	        "type": "module",
    10	        "exports": {
    11	                "./*": "./build/prebuilt/*",
    12	                "./buildSrc/*": "./buildSrc/*"
    13	        },
    14	        "scripts": {
    15	                "build-packages": "npm run build -ws",
    16	                "start": "./start-desktop.sh",
    17	                "test": "npm run build-packages; npm run --if-present test -ws && cd test && node --icu-data-dir=../node_modules/full-icu test api -c && node --icu-data-dir=../node_modules/full-icu test client",
    18	                "testapi": "cd test && node --icu-data-dir=../node_modules/full-icu test api",
    19	                "testclient": "cd test && node --icu-data-dir=../node_modules/full-icu test client",
    20	                "types": "tsc",
    21	                "prebuild": "npm run build-packages && tsc --noEmit false --outDir build/prebuilt --declaration true --declarationMap true --incremental true && cp src/*.d.ts build/prebuilt"
    22	        },
    23	        "dependencies": {
    24	                "@tutao/oxmsg": "0.0.9-beta.0",
    25	                "@tutao/tutanota-crypto": "3.93.5",
    26	                "@tutao/tutanota-utils": "3.93.5",
    27	                "@types/better-sqlite3": "7.4.2",
    28	                "@types/dompurify": "2.3.0",
    29	                "@types/linkifyjs": "2.1.4",
    30	                "@types/luxon": "1.27.1",
    31	                "@types/mithril": "2.0.8",
    32	                "@types/node-forge": "1.0.0",
    33	                "@types/qrcode-svg": "1.1.1",
    34	                "@types/systemjs": "6.1.1",
    35	                "@types/winreg": "1.2.31",
    36	                "better-sqlite3": "7.5.0",
    37	                "cborg": "1.5.4",
    38	                "dompurify": "2.3.0",
    39	                "electron": "16.0.9",
    40	                "electron-updater": "4.6.5",
    41	                "jszip": "3.7.0",
    42	                "keytar": "github:tutao/node-keytar#12593c5809c9ed6bfc063ed3e862dd85a1506aca",
    43	                "linkifyjs": "3.0.5",
    44	                "luxon": "1.28.0",
    45	                "mithril": "2.0.4",
    46	                "node-forge": "1.2.1",
    47	                "qrcode-svg": "1.0.0",
    48	                "squire-rte": "1.11.1",
    49	                "systemjs": "6.10.2",
    50	                "winreg": "1.2.4"
    51	        },
    52	        "devDependencies": {
    53	                "@octokit/auth-token": "2.5.0",
    54	                "@octokit/rest": "18.12.0",
    55	                "@rollup/plugin-commonjs": "18.1.0",
    56	                "@rollup/plugin-json": "4.1.0",
    57	                "@rollup/plugin-node-resolve": "13.1.3",
    58	                "@rollup/plugin-typescript": "8.3.0",
    59	                "@tutao/tutanota-build-server": "3.93.5",
    60	                "@tutao/tutanota-test-utils": "3.93.5",
    61	                "body-parser": "1.19.0",
    62	                "chokidar": "3.5.2",
    63	                "commander": "5.0.0-2",
    64	                "electron-builder": "22.14.5",
    65	                "electron-notarize": "1.1.1",
    66	                "electron-packager": "15.4.0",
    67	                "fs-extra": "10.0.0",
    68	                "full-icu": "1.3.4",
    69	                "glob": "7.1.7",
    70	                "js-yaml": "3.13.1",
    71	                "node-gyp": "6.1.0",
    72	                "nollup": "0.18.7",
    73	                "octokit": "1.3.0",
    74	                "ospec": "https://github.com/tutao/ospec.git#0472107629ede33be4c4d19e89f237a6d7b0cb11",
    75	                "rollup": "2.63.0",
    76	                "rollup-plugin-terser": "7.0.2",
    77	                "rollup-plugin-visualizer": "5.5.2",
    78	                "testdouble": "3.16.4",
    79	                "typescript": "4.5.4",
    80	                "xhr2": "0.2.1",
    81	                "zx": "5.1.0"
    82	        },
    83	        "workspaces": [
    84	                "./packages/*"
    85	        ],
    86	        "engines": {
    87	                "npm": ">=7.0.0"
    88	        }
    89	}
    90	





[MSG 28] [user]
Observation: 





























File created successfully at: /app/repro_check.py




[MSG 29] [user]
Observation: 
FAIL: missing _onMessage signature
Pattern: _onMessage\s*=\s*async\s*\(\s*message\s*:\s*MessageEvent<\s*string\s*>\s*\)\s*:\s*Promise<void>




[MSG 30] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **HIGH RESOLUTION** (7/14 = 50%) — weak/no contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → LIKELY_CLEAN
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: GPT-5 High - paper
**Analyzed**: 2026-04-12 19:07:12

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | None |
| Confidence | 0.74 |
| **Verdict** | **LIKELY_CLEAN** |

**Agent approach**: The agent inspected `EventBusClient`, `EventQueue`, and the corresponding test file to understand how websocket messages were handled and how sequencing was supposed to work. It appears to have noticed the expected `_onMessage` naming change, but it got stuck on tooling/build issues and never produced a code patch.

**Contamination evidence**: None

**Difficulty evidence**: The visible F2P test changes are limited to `EventBusClientTest` and check behaviors that are directly described in the prompt: entity updates being processed sequentially and unread counter updates being forwarded consistently. The only API-shape expectation is `_onMessage`, but the prompt explicitly mentions making internal naming consistent and the class already contains `_onOpen`, so `_onMessage` is reasonably inferable from context rather than undiscoverable.

**Full reasoning**: This does not show strong contamination evidence. The tests do touch an internal method name (`_onMessage`), which is somewhat coupled to implementation, but the problem statement itself explicitly calls out inconsistent internal naming and says the message handler should be invocable reliably without changing the external API. Given the existing `_onOpen` method, renaming `_message` to `_onMessage` is a natural and locally inferable fix, not an arbitrary hidden requirement. The substantive behaviors under test—serial processing of entity updates and consistent delivery of unread counter updates—are exactly the stated requirements. Crucially, the agent never submitted a plausible alternate fix that solved the spec and was then rejected by tests for secret reasons; instead it mostly explored files, ran into build/test harness path problems, and timed out. So this looks like an agent execution failure on a fair task, not benchmark contamination.
