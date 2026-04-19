# Case #80 Re-Audit Notes (v2)

**Instance**: `instance_NodeBB__NodeBB-f2082d7de85eb62a70819f4f3396dd85626a0c0a-vd59a5728dfc977f44533186ace531248c2917516`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"## Title:\n\nMigrate Socket Methods to Write API\n\n### Description:\n\nThe current implementation relies on two socket methods, `posts.getRawPost` and `posts.getPostSummaryByPid`, to serve raw and summarized post data. These socket-based endpoints are tightly coupled to the real-time layer and are increasingly incompatible with REST-oriented client use cases, external integrations, and modern architectural patterns.\n\nTo improve API clarity and decouple data access from sockets, we propose re...

**Type**: js | **Repo**: NodeBB/NodeBB
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 6 |
| Gold patch files | 6 |
| Gold patch size | 9716 chars |
| Test patch size | 2348 chars |
| Test patch files | 1 |
| F2P tests | 5 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
test/posts.js
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard f0d989e4ba5b0dccff6e56022fc6d378d05ab404
git clean -fd 
git checkout f0d989e4ba5b0dccff6e56022fc6d378d05ab404 
git checkout f2082d7de85eb62a70819f4f3396dd85626a0c0a -- test/posts.js
```

## 3. Trajectory Evidence

### Resolution Rate: 0/13 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 39 |
| Claude Sonnet 4 - paper | FAIL | 15 |
| Gemini 2.5 Pro Preview - paper | FAIL | 50 |
| GPT-4o - paper | FAIL | 30 |
| GPT-5 High - paper | FAIL | 28 |
| GPT OSS - paper | FAIL | 38 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 104 |
| GPT-5 - 10132025 | FAIL | 145 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 38 |
| GPT-5 Codex -- debug-oct22 | FAIL | 2 |
| GLM-4.5 -- 10222025 | FAIL | 68 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 91 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 64
- **Total tokens**: ~30502
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
/app/test
/app/test/settings.js
/app/test/database
/app/test/password.js
/app/test/plugins-installed.js
/app/test/socket.io.js
/app/test/build.js
/app/test/controllers.js
/app/test/search.js
/app/test/i18n.js
/app/test/categories.js
/app/test/authentication.js
/app/test/flags.js
/app/test/upgrade.js
/app/test/search-admin.js
/app/test/meta.js
/app/test/topics.js
/app/test/feeds.js
/app/test/plugins.js
/app/test/middleware.js
/app/test/posts.js
/app/test/helpers
/app/test/locale-detect.js
/app/test/defer-logger.js
/app/test/database.js
/app/test/image.js
/app/test/user.js
/app/test/topics
/app/test/groups.js
/app/test/coverPhoto.js
/app/test/notifications.js
/app/test/uploads.js
/app/test/pagination.js
/app/test/file.js
/app/test/api.js
/app/test/files
/app/test/user
/app/test/template-helpers.js
/app/test/utils.js
/app/test/emailer.js
/app/test/batch.js
/app/test/mocks
/app/test/pubsub.js
/app/test/posts
/app/test/messaging.js
/app/test/rewards.js
/app/test/controllers-admin.js
/app/test/translator.js
/app/test/package-install.js
/app/test/blacklist.js
/app/README.md
/app/webpack.prod.js
/app/CHANGELOG.md
/app/build
/app/build/export
/app/build/public
/app/build/cache-buster
/app/build/active_plugins.json
/app/package.json
/app/LICENSE
/app/logs
/app/logs/webinstall.log
/app/webpack.dev.js
/app/Gruntfile.js
/app/docker-compose.yml
/app/src
/app/src/password.js
/app/src/webserver.js
/app/src/plugins
/app/src/helpers.js
/app/src/api
/app/src/cache
/app/src/admin
/app/src/cacheCreate.js
/app/src/user
/app/src/database
/app/src/upgrade.js
/app/src/socket.io
/app/src/social.js
/app/src/upgrades
/app/src/views
/app/src/prestart.js
/app/src/routes
/app/src/image.js
/app/src/navigation
/app/src/file.js
/app/src/posts
/app/src/coverPhoto.js
/app/src/cache.js
/app/src/install.js
/app/src/privileges
/app/src/slugify.js
/app/src/controllers
/app/src/groups
/app/src/search.js
/app/src/flags.js
/app/src/settings.js
/app/src/messaging
/app/src/notifications.js
/app/src/constants.js
/app/src/languages.js
/app/src/meta
/app/src/rewards
/app/src/pagination.js
/app/src/analytics.js
/app/src/emailer.js
/app/src/logger.js
/app/src/translator.js
/app/src/batch.js
/app/src/middleware
/app/src/categories
/app/src/events.js
/app/src/sitemap.js
/app/src/topics
/app/src/start.js
/app/src/pubsub.js
/app/src/utils.js
/app/src/promisify.js
/app/src/cli
/app/src/als.js
/app/src/widgets
/app/config.json
/app/webpack.common.js
/app/node_modules
/app/node_modules/emitter
/app/node_modules/inherits
/app/node_modules/neo-async
/app/node_modules/ajv-draft-04
/app/node_modules/parse-passwd
/app/node_modules/liftup
/app/node_modules/json5
/app/node_modules/shallow-clone
/app/node_modules/ignore
/app/node_modules/combined-stream
/app/node_modules/express
/app/node_modules/sass
/app/node_modules/node-preload
/app/node_modules/lodash.flattendeep
/app/node_modules/typed-array-length
/app/node_modules/connect-pg-simple
/app/node_modules/buffer-from
/app/node_modules/commander
/app/node_modules/@jridgewell
/app/node_modules/clone
/app/node_modules/esutils
/app/node_modules/is-core-module
/app/node_modules/cosmiconfig-typescript-loader
/app/node_modules/es-object-atoms
/app/node_modules/@webassemblyjs
/app/node_modules/fizzy-ui-utils
/app/node_modules/querystringify
/app/node_modules/picocolors
/app/node_modules/caseless
/app/node_modules/fromentries
/app/node_modules/object.assign
/app/node_modules/logform
/app/node_modules/cbor
/app/node_modules/has
/app/node_modules/lodash.upperfirst
/app/node_modules/strip-ansi
/app/node_modules/multer
/app/node_modules/delegate
/app/node_modules/request
/app/node_modules/json-text-sequence
/app/node_modules/pump
/app/node_modules/stream-parser
/app/node_modules/long
/app/node_modules/process-nextick-args
/app/node_modules/js-tokens
/app/node_modules/pg
/app/node_modules/fraction.js
/app/node_modules/random-bytes
/app/node_modules/to-regex-range
/app/node_modules/safe-array-concat
/app/node_modules/@dabh
/app/node_modules/sass-embedded-linux-x64
/app/node_modules/compressible
/app/node_modules/grunt
/app/node_modules/picomatch
/app/node_modules/ecc-jsbn
/app/node_modules/socket.io-parser
/app/node_modules/safe-stable-stringify
/app/node_modules/make-dir
/app/node_modules/tough-cookie
/app/node_modules/object.values
/app/node_modules/normalize-range
/app/node_modules/is-binary-path
/app/node_modules/math-intrinsics
/app/node_modules/memory-pager
/app/node_modules/call-me-maybe
/app/node_modules/fecha
/app/node_modules/is-weakref
/app/node_modules/map-cache
/app/node_modules/string.prototype.trimstart
/app/node_modules/@isaacs
/app/node_modules/is-async-function
/app/node_modules/is-data-view
/app/node_modules/grunt-known-options
/app/node_modules/normalize-package-data
/app/node_modules/whatwg-url
/app/node_modules/sshpk
/app/node_modules/typed-array-buffer
/app/node_modules/standard-as-callback
/app/node_modules/logrotate-stream
/app/node_modules/timeago
/app/node_modules/caching-transform
/app/node_modules/path-type
/app/node_modules/clone-deep
/app/node_modules/spawn-wrap
/app/node_modules/minimalistic-assert
/app/node_modules/underscore
/app/node_modules/functions-have-names
/app/node_modules/@jsdevtools
/app/node_modules/is-symbol
/app/node_modules/xmlhttprequest-ssl
/app/node_modules/node-addon-api
/app/node_modules/es6-promise
/app/node_modules/define-properties
/app/node_modules/slice-ansi
/app/node_modules/proxy-addr
/app/node_modules/safe-regex-test
/app/node_modules/available-typed-arrays
/app/node_modules/yn
/app/node_modules/JSONStream
/app/node_modules/es-define-property
/app/node_modules/csrf-sync
/app/node_modules/asn1
/app/node_modules/@ioredis
/app/node_modules/requires-port
/app/node_modules/async
/app/node_modules/is-negative-zero
/app/node_modules/dot-prop
/app/node_modules/es-to-primitive
/app/node_modules/emoji-datasource-google
/app/node_modules/figures
/app/node_modules/delayed-stream
/app/node_modules/array-flatten
/app/node_modules/jwa
/app/node_modules/os-homedir
/app/node_modules/good-listener
/app/node_modules/busboy
/app/node_modules/utf8
/app/node_modules/is-what
/app/node_modules/glob
/app/node_modules/htmlparser2
/app/node_modules/is-typedarray
/app/node_modules/fetch-blob
/app/node_modules/html-escaper
/app/node_modules/saslprep
/app/node_modules/spdx-correct
/app/node_modules/getobject
/app/node_modules/ms
/app/node_modules/hmac-drbg
/app/node_modules/require-from-string
/app/node_modules/compress-commons
/app/node_modules/is-regex
/app/node_modules/fs-extra
/app/node_modules/data-urls
/app/node_modules/zxcvbn
/app/node_modules/deepmerge
/app/node_modules/http-errors
/app/node_modules/require-directory
/app/node_modules/cookie-signature
/app/node_modules/@commitlint
/app/node_modules/@tsconfig
/app/node_modules/grunt-cli
/app/node_modules/bl
/app/node_modules/dijkstrajs
/app/node_modules/destroy
/app/node_modules/fined
/app/node_modules/typed-array-byte-offset
/app/node_modules/express-session
/app/node_modules/mousetrap
/app/node_modules/is-number-object
/app/node_modules/needle
/app/node_modules/rimraf
/app/node_modules/get-size
/app/node_modules/string-template
/app/node_modules/qrcode
/app/node_modules/setprototypeof
/app/node_modules/tsconfig-paths
/app/node_modules/is-number
/app/node_modules/rrweb-cssom
/app/node_modules/data-view-buffer
/app/node_modules/commondir
/app/node_modules/global-modules
/app/node_modules/jwk-to-pem
/app/node_modules/imagesloaded
/app/node_modules/ansi-styles
/app/node_modules/read-pkg-up
/app/node_modules/is-windows
/app/node_modules/moment
/app/node_modules/astral-regex
/app/node_modules/import-fresh
/app/node_modules/path-exists
/app/node_modules/chartjs-color-string
/app/node_modules/negotiator
/app/node_modules/log-update
/app/node_modules/tiny-lr
/app/node_modules/eslint-import-resolver-node
/app/node_modules/husky
/app/node_modules/debug
/app/node_modules/data-vi
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
canViewDeleted = isAdmin || (postPrivileges && postPrivileges[0] && postPrivileges[0]['posts:view_deleted']);
   371	                if (!(isAuthor || canViewDeleted)) {
   372	                        throw new Error('[[error:no-post]]');
   373	                }
   374	        }
   375	
   376	        postData.pid = data.pid;
   377	        const result = await plugins.hooks.fire('filter:post.getRawPost', { uid: caller.uid, postData: postData });
   378	        return result.postData.content;
   379	};
   380	
   381	postsAPI.getSummary = async function (caller, data) {
   382	        if (!data || !data.pid) {
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 44] [assistant]
I need to look more at the structure to understand how to check for deleted posts. Let me fix the implementation:

[MSG 45] [user]
Observation: 





































The file /app/src/controllers/write/posts.js has been edited. Here's the result of running `cat -n` on a snippet of /app/src/controllers/write/posts.js:
    89	
    90	Posts.restoreDiff = async (req, res) => {
    91	        helpers.formatApiResponse(200, res, await api.posts.restoreDiff(req, { ...req.params }));
    92	};
    93	
    94	Posts.deleteDiff = async (req, res) => {
    95	        await api.posts.deleteDiff(req, { ...req.params });
    96	
    97	        helpers.formatApiResponse(200, res, await api.posts.getDiffs(req, { ...req.params }));
    98	};
    99	
   100	Posts.getRaw = async (req, res) => {
   101	        const content = await api.posts.getRaw(req, { pid: req.params.pid });
   102	        helpers.formatApiResponse(200, res, { content });
   103	};
   104	
   105	Posts.getSummary = async (req, res) => {
   106	        const summary = await api.posts.getSummary(req, { pid: req.params.pid });
   107	        helpers.formatApiResponse(200, res, summary);
   108	};
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 46] [assistant]
Now I need to add the controller methods to handle these new endpoints:

[MSG 47] [user]
Observation: 



























The file /app/src/routes/write/posts.js has been edited. Here's the result of running `cat -n` on a snippet of /app/src/routes/write/posts.js:
    24	        setupApiRoute(router, 'delete', '/:pid/vote', [...middlewares, middleware.assert.post], controllers.write.posts.unvote);
    25	
    26	        setupApiRoute(router, 'put', '/:pid/bookmark', [...middlewares, middleware.assert.post], controllers.write.posts.bookmark);
    27	        setupApiRoute(router, 'delete', '/:pid/bookmark', [...middlewares, middleware.assert.post], controllers.write.posts.unbookmark);
    28	
    29	        setupApiRoute(router, 'get', '/:pid/diffs', [middleware.assert.post], controllers.write.posts.getDiffs);
    30	        setupApiRoute(router, 'get', '/:pid/diffs/:since', [middleware.assert.post], controllers.write.posts.loadDiff);
    31	        setupApiRoute(router, 'put', '/:pid/diffs/:since', [...middlewares, middleware.assert.post], controllers.write.posts.restoreDiff);
    32	        setupApiRoute(router, 'delete', '/:pid/diffs/:timestamp', [...middlewares, middleware.assert.post], controllers.write.posts.deleteDiff);
    33	
    34	        setupApiRoute(router, 'get', '/:pid/raw', [middleware.assert.post], controllers.write.posts.getRaw);
    35	        setupApiRoute(router, 'get', '/:pid/summary', [middleware.assert.post], controllers.write.posts.getSummary);
    36	
    37	        return router;
    38	};
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 48] [assistant]
Now I need to add the routes for these endpoints. Let me add them to the routes file:

[MSG 49] [user]
Observation: 



























The file /app/src/socket.io/posts.js has been edited. Here's the result of running `cat -n` on a snippet of /app/src/socket.io/posts.js:
    16	const SocketPosts = module.exports;
    17	
    18	require('./posts/votes')(SocketPosts);
    19	require('./posts/tools')(SocketPosts);
    20	
    21	
    22	
    23	SocketPosts.getPostSummaryByIndex = async function (socket, data) {
    24	        if (data.index < 0) {
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 50] [assistant]
Now I need to remove the obsolete socket methods. Let me remove the `getRawPost` method:

[MSG 51] [user]
Observation: 

public/src/client/topic/postTools.js:			socket.emit('posts.getRawPost', toPid, function (err, post) {






[MSG 52] [assistant]
Now let me check if there are any references to `posts.getRawPost` socket method that need to be updated:

[MSG 53] [user]
Observation: 

Here's the result of running `cat -n` on /app/public/src/client/topic/postTools.js:
     1	'use strict';
     2	
     3	
     4	define('forum/topic/postTools', [
     5	        'share',
     6	        'navigator',
     7	        'components',
     8	        'translator',
     9	        'forum/topic/votes',
    10	        'api',
    11	        'bootbox',
    12	        'alerts',
    13	        'hooks',
    14	], function (share, navigator, components, translator, votes, api, bootbox, alerts, hooks) {
    15	        const PostTools = {};
    16	
    17	        let staleReplyAnyway = false;
    18	
    19	        PostTools.init = function (tid) {
    20	                staleReplyAnyway = false;
    21	
    22	                renderMenu();
    23	
    24	                addPostHandlers(tid);
    25	
    26	                share.addShareHandlers(ajaxify.data.titleRaw);
    27	
    28	                votes.addVoteHandler();
    29	
    30	                PostTools.updatePostCount(ajaxify.data.postcount);
    31	        };
    32	
    33	        function renderMenu() {
    34	                const container = document.querySelector('[component="topic"]');
    35	                if (!container) {
    36	                        return;
    37	                }
    38	                $('[component="topic"]').on('show.bs.dropdown', '.moderator-tools', function () {
    39	                        const $this = $(this);
    40	                        const dropdownMenu = $this.find('.dropdown-menu');
    41	                        if (dropdownMenu.attr('data-loaded')) {
    42	                                return;
    43	                        }
    44	                        const postEl = $this.parents('[data-pid]');
    45	                        const pid = postEl.attr('data-pid');
    46	                        const index = parseInt(postEl.attr('data-index'), 10);
    47	
    48	                        socket.emit('posts.loadPostTools', { pid: pid }, async (err, data) => {
    49	                                if (err) {
    50	                                        return alerts.error(err);







[MSG 54] [assistant]
I need to update the client-side code to use the new REST endpoint. Let me examine and update that file:

[MSG 55] [user]
Observation: 

			}

			if (selectedNode.text && toPid && toPid === selectedNode.pid) {
				return quote(selectedNode.text);
			}
			socket.emit('posts.getRawPost', toPid, function (err, post) {
				if (err) {
					return alerts.error(err);
				}

				quote(post);
			});
		});
	}

	async function getSelectedNode() {






[MSG 56] [assistant]
Let me search for the specific usage of getRawPost:

[MSG 57] [user]
Observation: 

















The file /app/public/src/client/topic/postTools.js has been edited. Here's the result of running `cat -n` on a snippet of /app/public/src/client/topic/postTools.js:
   311	                        }
   312	
   313	                        if (selectedNode.text && toPid && toPid === selectedNode.pid) {
   314	                                return quote(selectedNode.text);
   315	                        }
   316	                        api.get(`/posts/${toPid}/raw`, {}).then(({ content }) => {
   317	                                quote(content);
   318	                        }).catch(alerts.error);
   319	                });
   320	        }
   321	
Review the changes and make sure they are as expected. Edit the file again if necessary.






[MSG 58] [assistant]
Now let me update this to use the new REST API:

[MSG 59] [user]
Observation: 

src/api/posts.js:        const postObj = await posts.getPostSummaryByPids([editResult.post.pid], caller.uid, {});
src/api/posts.js:        const postsData = await posts.getPostSummaryByPids([pid], caller.uid, { stripTags: false });
src/api/topics.js:	const postObj = await posts.getPostSummaryByPids([postData.pid], caller.uid, {});
src/socket.io/posts.js:        const postsData = await posts.getPostSummaryByPids([pid], socket.uid, { stripTags: false });
src/socket.io/posts.js:        const postsData = await posts.getPostSummaryByPids([pid], socket.uid, { stripTags: false });
src/controllers/topics.js:	const postData = await posts.getPostSummaryByPids([pid], req.uid, { stripTags: false });
src/controllers/accounts/posts.js:			const postObjs = await posts.getPostSummaryByPids(pids, req.uid, { stripTags: false });
src/controllers/accounts/posts.js:			const postObjs = await posts.getPostSummaryByPids(pids, req.uid, { stripTags: false });
src/controllers/accounts/profile.js:			const p = await posts.getPostSummaryByPids(pids, callerUid, { stripTags: false });
src/groups/posts.js:		const postData = await posts.getPostSummaryByPids(pids, uid, { stripTags: false });
src/search.js:	returnData.posts = await posts.getPostSummaryByPids(metadata.pids, data.uid, {});
src/categories/recentreplies.js:		return await posts.getPostSummaryByPids(pids, uid, { stripTags: true });
public/src/client/topic.js:				const postData = postCache[pid] || await socket.emit('posts.getPostSummaryByPid', { pid: pid });






[MSG 60] [assistant]
Now let me check for any references to `posts.getPostSummaryByPid`:

[MSG 61] [user]
Observation: 

Here's the result of running `cat -n` on /app/public/src/client/topic.js:
     1	'use strict';
     2	
     3	
     4	define('forum/topic', [
     5	        'forum/infinitescroll',
     6	        'forum/topic/threadTools',
     7	        'forum/topic/postTools',
     8	        'forum/topic/events',
     9	        'forum/topic/posts',
    10	        'navigator',
    11	        'sort',
    12	        'quickreply',
    13	        'components',
    14	        'storage',
    15	        'hooks',
    16	        'api',
    17	        'alerts',
    18	        'bootbox',
    19	        'clipboard',
    20	], function (
    21	        infinitescroll, threadTools, postTools,
    22	        events, posts, navigator, sort, quickreply,
    23	        components, storage, hooks, api, alerts,
    24	        bootbox, clipboard
    25	) {
    26	        const Topic = {};
    27	        let tid = 0;
    28	        let currentUrl = '';
    29	
    30	        $(window).on('action:ajaxify.start', function (ev, data) {
    31	                events.removeListeners();
    32	
    33	                if (!String(data.url).startsWith('topic/')) {
    34	                        navigator.disable();
    35	                        components.get('navbar/title').find('span').text('').hide();
    36	                        alerts.remove('bookmark');
    37	                }
    38	        });
    39	
    40	        Topic.init = async function () {
    41	                const tidChanged = !tid || parseInt(tid, 10) !== parseInt(ajaxify.data.tid, 10);
    42	                tid = ajaxify.data.tid;
    43	                currentUrl = ajaxify.currentPage;
    44	                hooks.fire('action:topic.loading');
    45	
    46	                app.enterRoom('topic_' + tid);
    47	
    48	                if (tidChanged) {
    49	                        posts.signaturesShown = {};
    50	                }







[MSG 62] [assistant]
I found the client-side usage. Let me update that:

[MSG 63] [user]
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
**Analyzed**: 2026-04-12 20:36:36

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | contamination |
| Contamination type | test_coupling |
| Confidence | 0.9 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent traced the existing socket, API, controller, and write-route layers, then started implementing `api.posts.getRaw`/`getSummary`, added write-controller handlers and routes, removed `SocketPosts.getRawPost`, and updated a client call from `socket.emit` to `api.get`.

**Contamination evidence**: The problem statement asks for new HTTP Write API endpoints (`GET /api/v3/posts/:pid/raw` and `/summary`) and migration away from socket methods, but the F2P tests do not exercise HTTP routes at all. Instead, they directly import and assert on specific internal helper methods `apiPosts.getRaw` and `apiPosts.getSummary`, including their exact null-return semantics. A solution that correctly implements the documented REST endpoints inside controllers/routes without adding those exact internal API methods would still fail. The tests also assert an extra behavior not stated in the issue: privileged users (e.g. global moderators) can read raw content of deleted posts, even though the legacy socket implementation shown in the repo threw `[[error:no-post]]` for deleted posts unconditionally.

**Difficulty evidence**: None

**Full reasoning**: This looks contaminated rather than merely hard. The agent clearly understood the requested migration: it inspected the socket methods, the write API structure, controllers, and routes, and began implementing the new read paths in the expected layers. However, the tests are coupled to an internal architecture choice that is not part of the stated contract: they call `api.posts.getRaw/getSummary` directly instead of verifying the advertised HTTP endpoints. That means an implementation could satisfy the public spec yet fail the benchmark. On top of that, the tests require a deleted-post privilege rule (global moderators can read deleted raw content) that is not described in the problem statement and even differs from the legacy `SocketPosts.getRawPost` behavior in the base repo. The agent did make some mistakes and timed out, but the benchmark itself contains strong hidden-requirement/test-coupling signals that plausibly explain the 0% solve rate.
