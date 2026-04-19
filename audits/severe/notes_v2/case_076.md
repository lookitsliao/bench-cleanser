# Case #76 Re-Audit Notes (v2)

**Instance**: `instance_NodeBB__NodeBB-445b70deda20201b7d9a68f7224da751b3db728c-v4fbcfae8b15e4ce5d132c408bca69ebb9cf146ed`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"## Title:  \n\nInvalid input handling and response consistency in chats and users API  \n\n#### Description:  \n\nSome API endpoints related to chats and users do not consistently validate missing or malformed input data, leading to unexpected or misleading responses. Tests assert that these endpoints must fail fast with a clear error message when required data is absent, and must return correct data when valid input is provided.  \n\n### Step to Reproduce:  \n\n1. Call the chats API to fetch a...

**Type**: js | **Repo**: NodeBB/NodeBB
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 2 |
| Gold patch files | 2 |
| Gold patch size | 2556 chars |
| Test patch size | 7601 chars |
| Test patch files | 1 |
| F2P tests | 4 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
test/messaging.js
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 565ca3cc3b78d6e5177b7834d496927b96b6c88c
git clean -fd 
git checkout 565ca3cc3b78d6e5177b7834d496927b96b6c88c 
git checkout 445b70deda20201b7d9a68f7224da751b3db728c -- test/messaging.js
```

## 3. Trajectory Evidence

### Resolution Rate: 0/13 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 37 |
| Claude Sonnet 4 - paper | FAIL | 13 |
| Gemini 2.5 Pro Preview - paper | FAIL | 21 |
| GPT-4o - paper | FAIL | 22 |
| GPT-5 High - paper | FAIL | 29 |
| GPT OSS - paper | FAIL | 19 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 119 |
| GPT-5 - 10132025 | FAIL | 49 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 30 |
| GPT-5 Codex -- debug-oct22 | FAIL | 84 |
| GLM-4.5 -- 10222025 | FAIL | 26 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 85 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 60
- **Total tokens**: ~30461
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
/app/loader.js
/app/logs
/app/logs/webinstall.log
/app/webpack.dev.js
/app/package-lock.json
/app/commitlint.config.js
/app/app.js
/app/docker-compose.yml
/app/require-main.js
/app/build
/app/build/export
/app/build/public
/app/build/cache-buster
/app/build/active_plugins.json
/app/src
/app/src/install.js
/app/src/widgets
/app/src/search.js
/app/src/emailer.js
/app/src/cacheCreate.js
/app/src/promisify.js
/app/src/social.js
/app/src/events.js
/app/src/file.js
/app/src/upgrades
/app/src/pagination.js
/app/src/views
/app/src/cache
/app/src/user
/app/src/settings.js
/app/src/posts
/app/src/categories
/app/src/password.js
/app/src/database
/app/src/routes
/app/src/analytics.js
/app/src/middleware
/app/src/languages.js
/app/src/utils.js
/app/src/start.js
/app/src/prestart.js
/app/src/logger.js
/app/src/image.js
/app/src/messaging
/app/src/admin
/app/src/notifications.js
/app/src/upgrade.js
/app/src/cli
/app/src/constants.js
/app/src/groups
/app/src/webserver.js
/app/src/meta
/app/src/pubsub.js
/app/src/flags.js
/app/src/cache.js
/app/src/navigation
/app/src/socket.io
/app/src/als.js
/app/src/controllers
/app/src/api
/app/src/topics
/app/src/rewards
/app/src/password_worker.js
/app/src/plugins
/app/src/coverPhoto.js
/app/src/translator.js
/app/src/privileges
/app/src/slugify.js
/app/src/helpers.js
/app/src/sitemap.js
/app/src/batch.js
/app/public
/app/public/src
/app/public/logo.png
/app/public/openapi
/app/public/favicon.ico
/app/public/language
/app/public/vendor
/app/public/503.html
/app/public/scss
/app/public/uploads
/app/public/images
/app/install
/app/install/package.json
/app/install/docker
/app/install/databases.js
/app/install/web.js
/app/install/data
/app/webpack.installer.js
/app/node_modules
/app/node_modules/which-collection
/app/node_modules/log-symbols
/app/node_modules/glob
/app/node_modules/winston
/app/node_modules/bson
/app/node_modules/fetch-blob
/app/node_modules/is-callable
/app/node_modules/string.prototype.trimstart
/app/node_modules/readdir-glob
/app/node_modules/sass-embedded
/app/node_modules/arrify
/app/node_modules/core-util-is
/app/node_modules/package-json-from-dist
/app/node_modules/webidl-conversions
/app/node_modules/one-time
/app/node_modules/text-decoder
/app/node_modules/object-assign
/app/node_modules/asn1js
/app/node_modules/cbor
/app/node_modules/u2f
/app/node_modules/html-to-text
/app/node_modules/available-typed-arrays
/app/node_modules/type-check
/app/node_modules/through2
/app/node_modules/spider-detector
/app/node_modules/lines-and-columns
/app/node_modules/asynckit
/app/node_modules/stream-parser
/app/node_modules/enhanced-resolve
/app/node_modules/wrappy
/app/node_modules/nodebb-theme-peace
/app/node_modules/set-proto
/app/node_modules/connect-mongo
/app/node_modules/yallist
/app/node_modules/xtend
/app/node_modules/@apidevtools
/app/node_modules/json5
/app/node_modules/istanbul-reports
/app/node_modules/side-channel-weakmap
/app/node_modules/utf8
/app/node_modules/tslib
/app/node_modules/parseley
/app/node_modules/@ioredis
/app/node_modules/get-stream
/app/node_modules/sylvester
/app/node_modules/shebang-regex
/app/node_modules/object-inspect
/app/node_modules/selderee
/app/node_modules/express-session
/app/node_modules/object.pick
/app/node_modules/bytes
/app/node_modules/resolve-dir
/app/node_modules/http-errors
/app/node_modules/os-homedir
/app/node_modules/websocket-extensions
/app/node_modules/read
/app/node_modules/merge-descriptors
/app/node_modules/indent-string
/app/node_modules/istanbul-lib-source-maps
/app/node_modules/electron-to-chromium
/app/node_modules/acorn-jsx
/app/node_modules/array.prototype.flat
/app/node_modules/commander
/app/node_modules/fizzy-ui-utils
/app/node_modules/get-package-type
/app/node_modules/deep-is
/app/node_modules/file-loader
/app/node_modules/string-template
/app/node_modules/anymatch
/app/node_modules/jest-worker
/app/node_modules/locate-path
/app/node_modules/uid2
/app/node_modules/compress-commons
/app/node_modules/pkginfo
/app/node_modules/data-view-buffer
/app/node_modules/lodash.includes
/app/node_modules/array.prototype.findlastindex
/app/node_modules/is-typedarray
/app/node_modules/redisearch
/app/node_modules/dot-prop
/app/node_modules/merge-stream
/app/node_modules/http-parser-js
/app/node_modules/har-validator
/app/node_modules/loader-utils
/app/node_modules/eslint-config-airbnb-base
/app/node_modules/multiparty
/app/node_modules/find-cache-dir
/app/node_modules/type-is
/app/node_modules/markdown-it-checkbox
/app/node_modules/tinycon
/app/node_modules/nopt
/app/node_modules/delegate
/app/node_modules/nodebb-plugin-ntfy
/app/node_modules/environment
/app/node_modules/textcomplete
/app/node_modules/webpack-sources
/app/node_modules/callsites
/app/node_modules/compression
/app/node_modules/array-slice
/app/node_modules/combined-stream
/app/node_modules/busboy
/app/node_modules/abbrev
/app/node_modules/pg-types
/app/node_modules/log-driver
/app/node_modules/text-table
/app/node_modules/textcomplete.contenteditable
/app/node_modules/memory-pager
/app/node_modules/randombytes
/app/node_modules/markdown-it
/app/node_modules/grunt-contrib-watch
/app/node_modules/espree
/app/node_modules/@colors
/app/node_modules/html-entities
/app/node_modules/foreground-child
/app/node_modules/pidtree
/app/node_modules/jquery-deserialize
/app/node_modules/global-prefix
/app/node_modules/tunnel-agent
/app/node_modules/passport-strategy
/app/node_modules/optionator
/app/node_modules/wrap-ansi-cjs
/app/node_modules/gaze
/app/node_modules/supports-color
/app/node_modules/engine.io-parser
/app/node_modules/brorand
/app/node_modules/lodash.uniq
/app/node_modules/safe-regex-test
/app/node_modules/js-tokens
/app/node_modules/nodebb-plugin-emoji
/app/node_modules/varint
/app/node_modules/get-intrinsic
/app/node_modules/side-channel-list
/app/node_modules/clone
/app/node_modules/strip-final-newline
/app/node_modules/possible-typed-array-names
/app/node_modules/ieee754
/app/node_modules/decimal.js
/app/node_modules/log-rotate
/app/node_modules/xmlhttprequest-ssl
/app/node_modules/object.groupby
/app/node_modules/is-weakref
/app/node_modules/deffy
/app/node_modules/html-encoding-sniffer
/app/node_modules/test-exclude
/app/node_modules/linkify-it
/app/node_modules/fn.name
/app/node_modules/through
/app/node_modules/autoprefixer
/app/node_modules/binary-extensions
/app/node_modules/strip-bom
/app/node_modules/lodash.isfunction
/app/node_modules/@eslint
/app/node_modules/cluster-key-slot
/app/node_modules/dunder-proto
/app/node_modules/istanbul-lib-report
/app/node_modules/hmac-drbg
/app/node_modules/json2csv
/app/node_modules/quick-lru
/app/node_modules/rss
/app/node_modules/os-tmpdir
/app/node_modules/express
/app/node_modules/typedarray-to-buffer
/app/node_modules/sass
/app/node_modules/lazystream
/app/node_modules/lodash.isplainobject
/app/node_modules/levn
/app/node_modules/terser
/app/node_modules/grunt
/app/node_modules/istanbul-lib-coverage
/app/node_modules/queue-microtask
/app/node_modules/neo-async
/app/node_modules/fast-deep-equal
/app/node_modules/flat
/app/node_modules/jsonfile
/app/node_modules/node-releases
/app/node_modules/typed-array-length
/app/node_modules/istanbul-lib-processinfo
/app/node_modules/is-binary-path
/app/node_modules/ajv
/app/node_modules/@peculiar
/app/node_modules/web-streams-polyfill
/app/node_modules/is-symbol
/app/node_modules/is-arrayish
/app/node_modules/mousetrap
/app/node_modules/cli-cursor
/app/node_modules/nodebb-plugin-mentions
/app/node_modules/node-jose
/app/node_modules/esquery
/app/node_modules/lodash.isarguments
/app/node_modules/is-typed-array
/app/node_modules/methods
/app/node_modules/braces
/app/node_modules/readable-stream
/app/node_modules/call-bind-apply-helpers
/app/node_modules/log-update
/app/node_modules/compare-func
/app/node_modules/is-path-inside
/app/node_modules/underscore.string
/app/node_modules/dijkstrajs
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
 34	
    35	        session[field] = now;
    36	        return false;
    37	}
    38	
    39	chatsAPI.list = async (caller, { uid, start, stop, page, perPage }) => {
    40	        // Validate that at least one pagination parameter is provided
    41	        if (!start && !stop && !page && start !== 0 && stop !== 0) {
    42	                throw new Error('[[error:invalid-data]]');
    43	        }
    44	
    45	        if (!start && !stop && page) {
    46	                winston.warn('[api/chats] Sending `page` and `perPage` to .list() is deprecated in favour of `start` and `stop`. The deprecated parameters will be removed in v4.');
    47	                start = Math.max(0, page - 1) * perPage;
    48	                stop = start + perPage - 1;
    49	        }
    50	
    51	        // Default uid to caller's uid if not provided
    52	        return await messaging.getRecentChats(caller.uid, uid || caller.uid, start, stop);
    53	};
    54	
    55	chatsAPI.create = async function (caller, data) {
    56	        if (await rateLimitExceeded(caller, 'lastChatRoomCreateTime')) {
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 52] [assistant]
Now I understand the current implementation. Let me implement the required validation changes. Based on the PR description:

1. `chatsAPI.list` - Must validate that at least one of `start`, `stop`, or `page` is provided, if `uid` is not provided, default to caller's UID
2. `chatsAPI.listMessages` - Must validate that `roomId` is provided, handle cases where `uid` or `start` are not passed by defaulting `uid` to caller's UID and `start` to `0`
3. `chatsAPI.getMessage` - Must validate that both `mid` and `roomId` are provided
4. `chatsAPI.getRawMessage` - Must validate that both `mid` and `roomId` are provided  
5. `usersAPI.getPrivateRoomId` - Must validate that `uid` is provided

Let's start with the changes:

[MSG 53] [user]
Observation: 







































































































































The file /app/src/api/chats.js has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/chats.js:
   319	        }
   320	
   321	        return await messaging.toggleOwner(uid, roomId, state);
   322	};
   323	
   324	chatsAPI.listMessages = async (caller, { uid, roomId, start, direction = null }) => {
   325	        // Validate that roomId is provided
   326	        if (!roomId) {
   327	                throw new Error('[[error:invalid-data]]');
   328	        }
   329	
   330	        // Default uid to caller's uid if not provided
   331	        if (uid === undefined) {
   332	                uid = caller.uid;
   333	        }
   334	
   335	        // Default start to 0 if not provided
   336	        if (start === undefined) {
   337	                start = 0;
   338	        }
   339	
   340	        const count = 50;
   341	        let stop = start + count - 1;
   342	        if (direction === 1 || direction === -1) {
   343	                const msgCount = await db.getObjectField(`chat:room:${roomId}`, 'messageCount');
   344	                start = msgCount - start;
   345	                if (direction === 1) {
   346	                        start -= count + 1;
   347	                }
   348	                stop = start + count - 1;
   349	                start = Math.max(0, start);
   350	                if (stop <= -1) {
   351	                        return { messages: [] };
   352	                }
   353	                stop = Math.max(0, stop);
   354	        }
   355	
   356	        const messages = await messaging.getMessages({
   357	                callerUid: caller.uid,
   358	                uid,
   359	                roomId,
   360	                start,
   361	                count: stop - start + 1,
   362	        });
   363	
   364	        return { messages };
   365	};
   366	
   367	chatsAPI.getPinnedMessages = async (caller, { start, roomId }) => {
   368	        start = parseInt(start, 10) || 0;
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 54] [user]
Observation: 























The file /app/src/api/chats.js has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/chats.js:
   372	        }
   373	        const messages = await messaging.getPinnedMessages(roomId, caller.uid, start, start + 49);
   374	        return { messages };
   375	};
   376	
   377	chatsAPI.getMessage = async (caller, { mid, roomId }) => {
   378	        // Validate that both mid and roomId are provided
   379	        if (!mid || !roomId) {
   380	                throw new Error('[[error:invalid-data]]');
   381	        }
   382	
   383	        const messages = await messaging.getMessagesData([mid], caller.uid, roomId, false);
   384	        return messages.pop();
   385	};
   386	
   387	chatsAPI.getRawMessage = async (caller, { mid, roomId }) => {
   388	        const [isAdmin, canViewMessage, inRoom] = await Promise.all([
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 55] [user]
Observation: 































































The file /app/src/api/chats.js has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/chats.js:
   382	
   383	        const messages = await messaging.getMessagesData([mid], caller.uid, roomId, false);
   384	        return messages.pop();
   385	};
   386	
   387	chatsAPI.getRawMessage = async (caller, { mid, roomId }) => {
   388	        // Validate that both mid and roomId are provided
   389	        if (!mid || !roomId) {
   390	                throw new Error('[[error:invalid-data]]');
   391	        }
   392	
   393	        const [isAdmin, canViewMessage, inRoom] = await Promise.all([
   394	                user.isAdministrator(caller.uid),
   395	                messaging.canViewMessage(mid, roomId, caller.uid),
   396	                messaging.isUserInRoom(caller.uid, roomId),
   397	        ]);
   398	
   399	        if (!isAdmin && (!inRoom || !canViewMessage)) {
   400	                throw new Error('[[error:not-allowed]]');
   401	        }
   402	
   403	        const content = await messaging.getMessageField(mid, 'content');
   404	        return { content };
   405	};
   406	
   407	chatsAPI.getIpAddress = async (caller, { mid }) => {
   408	        const allowed = await privileges.global.can('view:users:info', caller.uid);
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 56] [user]
Observation: 







































The file /app/src/api/users.js has been edited. Here's the result of running `cat -n` on a snippet of /app/src/api/users.js:
   145	usersAPI.getStatus = async (caller, { uid }) => {
   146	        const status = await db.getObjectField(`user:${uid}`, 'status');
   147	        return { status };
   148	};
   149	
   150	usersAPI.getPrivateRoomId = async (caller, { uid }) => {
   151	        // Validate that uid is provided
   152	        if (!uid) {
   153	                throw new Error('[[error:invalid-data]]');
   154	        }
   155	
   156	        let roomId = await messaging.hasPrivateChat(caller.uid, uid);
   157	        roomId = parseInt(roomId, 10);
   158	
   159	        return {
   160	                roomId: roomId > 0 ? roomId : null,
   161	        };
   162	};
   163	
   164	usersAPI.changePassword = async function (caller, data) {
   165	        await user.changePassword(caller.uid, Object.assign(data, { ip: caller.ip }));
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 57] [user]
Observation: 





















































































































































































































































































The file /app/reproduce_issue.js has been edited. Here's the result of running `cat -n` on a snippet of /app/reproduce_issue.js:
     1	'use strict';
     2	
     3	// Script to test the updated validation logic
     4	
     5	// Manually inspect the functions to see their current validation logic
     6	const fs = require('fs');
     7	const path = require('path');
     8	
     9	function analyzeFile(filePath, functions) {
    10	    console.log(`\n📄 Analyzing ${filePath}:`);
    11	    const content = fs.readFileSync(filePath, 'utf8');
    12	    
    13	    functions.forEach(funcName => {
    14	        console.log(`\n🔍 Function: ${funcName}`);
    15	        
    16	        // Find the function definition
    17	        const regex = new RegExp(`${funcName}\\s*=\\s*async.*?\\{([\\s\\S]*?)\\n\\};`, 'm');
    18	        const match = content.match(regex);
    19	        
    20	        if (match) {
    21	            const funcBody = match[1];
    22	            console.log(`Current validation logic:`);
    23	            
    24	            // Look for validation patterns
    25	            const errorChecks = funcBody.match(/throw new Error\(['"`].*?['"`]\)/g) || [];
    26	            const dataChecks = funcBody.match(/if \(.*?\)/g) || [];
    27	            
    28	            if (errorChecks.length > 0) {
    29	                console.log(`✅ Has error throwing:`, errorChecks);
    30	            } else {
    31	                console.log(`❌ No error throwing found`);
    32	            }
    33	            
    34	            // Check for data parameter validation
    35	            if (funcBody.includes('!data') || funcBody.includes('!roomId') || funcBody.includes('!uid') || funcBody.includes('!mid')) {
    36	                console.log(`✅ Has some parameter validation`);
    37	            } else {
    38	                console.log(`❌ No obvious parameter validation`);
    39	            }
    40	            
    41	            // Check for error:invalid-data
    42	            if (funcBody.includes('[[error:invalid-data]]')) {
    43	                console.log(`✅ Uses standard error format`);
    44	            } else {
    45	                console.log(`❌ No standard error format found`);
    46	            }
    47	            
    48	            // Check for specific validation patterns
    49	            if (funcName === 'list' && funcBody.includes('!start && !stop && !page')) {
    50	                console.log(`✅ Has list parameter validation`);
    51	            }
    52	            if (funcName === 'listMessages' && funcBody.includes('if (!roomId)')) {
    53	                console.log(`✅ Has roomId validation`);
    54	            }
    55	            if ((funcName === 'getMessage' || funcName === 'getRawMessage') && funcBody.includes('!mid || !roomId')) {
    56	                console.log(`✅ Has mid and roomId validation`);
    57	            }
    58	            if (funcName === 'getPrivateRoomId' && funcBody.includes('if (!uid)')) {
    59	                console.log(`✅ Has uid validation`);
    60	            }
    61	            
    62	        } else {
    63	            console.log(`❌ Function not found in file`);
    64	        }
    65	    });
    66	}
    67	
    68	// Analyze the chat API functions
    69	analyzeFile('/app/src/api/chats.js', ['list', 'listMessages', 'getMessage', 'getRawMessage']);
    70	
    71	// Analyze the users API functions  
    72	analyzeFile('/app/src/api/users.js', ['getPrivateRoomId']);
    73	
    74	console.log(`\n\n✅ Changes implemented! All functions should now have proper validation with '[[error:invalid-data]]' format.`);
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 58] [assistant]
Now let me create a test script to verify that our changes work correctly:

[MSG 59] [user]
Observation: Exited (autosubmitted)
```
</details>

## 4. Contamination Signals

- **ALL AGENTS FAIL** (13 runs, 0 pass) — strong contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → CLEAN
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: Claude Opus 4.1 - paper
**Analyzed**: 2026-04-12 20:30:13

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | timeout |
| Contamination type | None |
| Confidence | 0.95 |
| **Verdict** | **CLEAN** |

**Agent approach**: The agent inspected `src/api/chats.js` and `src/api/users.js`, identified the relevant methods, and added `[[error:invalid-data]]` checks for missing `roomId`, `mid`, pagination data, and `uid`. However, it left destructured argument signatures unchanged, did not add the needed default parameter objects/default values, and never finalized a submitted patch.

**Contamination evidence**: None

**Difficulty evidence**: The task requires noticing a JavaScript-specific pitfall: methods like `async (caller, { mid, roomId }) => {}` throw a native destructuring TypeError when called with `undefined`, so to return `[[error:invalid-data]]` the implementation must use defaults like `({ mid, roomId } = {})`. The agent added inner validation checks but missed this, and also timed out/autosubmitted without a final patch.

**Full reasoning**: This looks clean, not contaminated. The tests are checking behavior directly described in the problem statement: missing or malformed chat/user API inputs should fail fast with `[[error:invalid-data]]`, and valid calls should still return normal results. The gold patch does not introduce hidden helper names, magic strings beyond the explicitly stated error token, or architectural constraints; it simply validates missing input and sets sensible defaults so undefined payloads do not crash before validation. The representative agent clearly understood the intended fix and edited the correct files, but its implementation remained incomplete: it kept signatures like `async (caller, { uid })` and `async (caller, { mid, roomId })`, so calls such as `api.chats.getRawMessage(caller, undefined)` or `api.users.getPrivateRoomId(caller, undefined)` would still throw a destructuring TypeError instead of `[[error:invalid-data]]`. That is an implementation mistake / unfinished patch, not evidence that the tests demanded undiscoverable internals. A stale test title ('should return not allowed error if user is not in room') is just noise; the actual asserted behavior still matches the written spec.
