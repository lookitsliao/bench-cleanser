# Case #62 Re-Audit Notes (v2)

**Instance**: `instance_protonmail__webclients-da91f084c0f532d9cc8ca385a701274d598057b8`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"## Title:\n\nNotifications with HTML content display incorrectly and duplicate messages clutter the UI\n\n#### Description:\n\nNotifications generated from API responses may contain simple HTML (e.g., links or formatting). These are currently rendered as plain text, making links unusable and formatting lost. Additionally, repeated identical notifications may appear, leading to noise and poor user experience.\n\n### Steps to Reproduce:\n\n1. Trigger an API error or message that includes HTML con...

**Type**: js | **Repo**: protonmail/webclients
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 4 |
| Gold patch files | 4 |
| Gold patch size | 5632 chars |
| Test patch size | 5562 chars |
| Test patch files | 1 |
| F2P tests | 2 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
packages/components/containers/notifications/manager.test.tsx
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard fd6d7f6479dd2ab0c3318e2680d677b9e61189cd
git clean -fd 
git checkout fd6d7f6479dd2ab0c3318e2680d677b9e61189cd 
git checkout da91f084c0f532d9cc8ca385a701274d598057b8 -- packages/components/containers/notifications/manager.test.tsx
```

## 3. Trajectory Evidence

### Resolution Rate: 1/12 (8%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | PASS | 36 |
| Gemini 2.5 Pro Preview - paper | FAIL | 13 |
| GPT-5 High - paper | FAIL | 20 |
| GPT OSS - paper | FAIL | 41 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 92 |
| Claude 4 Sonnet - 10132025 | FAIL | 55 |
| GPT-5 - 10132025 | FAIL | 43 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 24 |
| GPT-5 Codex -- debug-oct22 | FAIL | 146 |
| GLM-4.5 -- 10222025 | FAIL | 39 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 65 |

### Representative Trajectory: GPT-5 High - paper
- **Resolved**: False
- **Turns**: 19
- **Total tokens**: ~27095
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
/app/LICENSE
/app/plugin-postinstall.js
/app/renovate.json
/app/node_modules
/app/node_modules/eslint-webpack-plugin
/app/node_modules/postcss-discard-overridden
/app/node_modules/unbox-primitive
/app/node_modules/argparse
/app/node_modules/browser-process-hrtime
/app/node_modules/string-length
/app/node_modules/co
/app/node_modules/shallowequal
/app/node_modules/micro-api-client
/app/node_modules/babel-plugin-syntax-class-constructor-call
/app/node_modules/acorn
/app/node_modules/workbox-google-analytics
/app/node_modules/jest-snapshot
/app/node_modules/rfc2047
/app/node_modules/send
/app/node_modules/js-levenshtein
/app/node_modules/spdx-license-ids
/app/node_modules/meow
/app/node_modules/node-source-walk
/app/node_modules/cacheable-lookup
/app/node_modules/buffer-equal-constant-time
/app/node_modules/indexes-of
/app/node_modules/text-hex
/app/node_modules/path-key
/app/node_modules/word-wrap
/app/node_modules/strip-ansi
/app/node_modules/object-copy
/app/node_modules/file-size
/app/node_modules/compute-scroll-into-view
/app/node_modules/dns-equal
/app/node_modules/@babel
/app/node_modules/colorette
/app/node_modules/node-abi
/app/node_modules/p-wait-for
/app/node_modules/autoprefixer
/app/node_modules/lodash.pick
/app/node_modules/glob
/app/node_modules/adjust-sourcemap-loader
/app/node_modules/constants-browserify
/app/node_modules/os-tmpdir
/app/node_modules/validate-npm-package-name
/app/node_modules/min-indent
/app/node_modules/error-ex
/app/node_modules/iserror
/app/node_modules/es-abstract
/app/node_modules/cheerio
/app/node_modules/object.fromentries
/app/node_modules/babel-preset-const-enum
/app/node_modules/ext-name
/app/node_modules/babel-plugin-lodash
/app/node_modules/schema-utils
/app/node_modules/ts-pnp
/app/node_modules/app-root-dir
/app/node_modules/stream-to
/app/node_modules/foreground-child
/app/node_modules/postcss-modules-values
/app/node_modules/@istanbuljs
/app/node_modules/object-inspect
/app/node_modules/get-package-type
/app/node_modules/is-observable
/app/node_modules/prr
/app/node_modules/react-popper-tooltip
/app/node_modules/dir-glob
/app/node_modules/https-proxy-agent
/app/node_modules/pseudomap
/app/node_modules/parse-asn1
/app/node_modules/dotenv
/app/node_modules/babel-plugin-polyfill-corejs2
/app/node_modules/jest-environment-jsdom
/app/node_modules/is-typedarray
/app/node_modules/printj
/app/node_modules/socket.io
/app/node_modules/tsscmp
/app/node_modules/babel-plugin-transform-async-generator-functions
/app/node_modules/estraverse
/app/node_modules/babel-plugin-add-react-displayname
/app/node_modules/property-information
/app/node_modules/fs-readdir-recursive
/app/node_modules/lodash.isboolean
/app/node_modules/leven
/app/node_modules/connect
/app/node_modules/requireindex
/app/node_modules/@base2
/app/node_modules/yauzl
/app/node_modules/postcss-scss
/app/node_modules/@npmcli
/app/node_modules/extend
/app/node_modules/babel-types
/app/node_modules/fecha
/app/node_modules/workbox-core
/app/node_modules/jsx-ast-utils
/app/node_modules/restore-cursor
/app/node_modules/no-case
/app/node_modules/only
/app/node_modules/hast-util-parse-selector
/app/node_modules/workbox-build
/app/node_modules/utila
/app/node_modules/camelcase-css
/app/node_modules/safe-buffer
/app/node_modules/memoizerific
/app/node_modules/chownr
/app/node_modules/plural-forms
/app/node_modules/copy-webpack-plugin
/app/node_modules/babel-helper-function-name
/app/node_modules/is-negative-zero
/app/node_modules/cloneable-readable
/app/node_modules/parse-headers
/app/node_modules/qs
/app/node_modules/safe-json-stringify
/app/node_modules/process-nextick-args
/app/node_modules/listr-silent-renderer
/app/node_modules/crypto-random-string
/app/node_modules/through2-filter
/app/node_modules/obuf
/app/node_modules/typescript
/app/node_modules/type-check
/app/node_modules/node-localstorage
/app/node_modules/file-system-cache
/app/node_modules/babel-plugin-react-docgen
/app/node_modules/roosterjs-editor-core
/app/node_modules/eslint-config-airbnb-base
/app/node_modules/postcss-normalize-repeat-style
/app/node_modules/cacheable-request
/app/node_modules/is-resolvable
/app/node_modules/@octokit
/app/node_modules/babel-plugin-transform-do-expressions
/app/node_modules/fs-monkey
/app/node_modules/dom-walk
/app/node_modules/babel-plugin-named-asset-import
/app/node_modules/babel-helper-regex
/app/node_modules/@jest
/app/node_modules/jsonfile
/app/node_modules/cssesc
/app/node_modules/socks-proxy-agent
/app/node_modules/eslint-plugin-es
/app/node_modules/jest-watcher
/app/node_modules/psl
/app/node_modules/to-fast-properties
/app/node_modules/bindings
/app/node_modules/ci-info
/app/node_modules/is-windows
/app/node_modules/ecc-jsbn
/app/node_modules/process
/app/node_modules/url-parse-lax
/app/node_modules/is-stream
/app/node_modules/@bcoe
/app/node_modules/minizlib
/app/node_modules/jest-util
/app/node_modules/braces
/app/node_modules/ecdsa-sig-formatter
/app/node_modules/create-require
/app/node_modules/lodash.mapvalues
/app/node_modules/parse-bmfont-ascii
/app/node_modules/sprintf-js
/app/node_modules/babel-traverse
/app/node_modules/colors
/app/node_modules/@sindresorhus
/app/node_modules/p-timeout
/app/node_modules/jwt-decode
/app/node_modules/babylon
/app/node_modules/browserify-cipher
/app/node_modules/caniuse-lite
/app/node_modules/minipass-pipeline
/app/node_modules/remark-footnotes
/app/node_modules/is-shared-array-buffer
/app/node_modules/require-inject
/app/node_modules/lodash.memoize
/app/node_modules/fill-range
/app/node_modules/express-logging
/app/node_modules/hi-base32
/app/node_modules/babel-plugin-transform-es2015-destructuring
/app/node_modules/delayed-stream
/app/node_modules/private
/app/node_modules/use-composed-ref
/app/node_modules/find-root
/app/node_modules/escodegen
/app/node_modules/merge-stream
/app/node_modules/pretty-ms
/app/node_modules/lodash.startcase
/app/node_modules/regenerate
/app/node_modules/fastest-levenshtein
/app/node_modules/workbox-strategies
/app/node_modules/deep-is
/app/node_modules/safer-buffer
/app/node_modules/is-boolean-object
/app/node_modules/void-elements
/app/node_modules/lowercase-keys
/app/node_modules/diff-sequences
/app/node_modules/is-color-stop
/app/node_modules/eslint-config-airbnb-typescript
/app/node_modules/array-uniq
/app/node_modules/he
/app/node_modules/to-object-path
/app/node_modules/jest-resolve-dependencies
/app/node_modules/mkdirp
/app/node_modules/jest-runner
/app/node_modules/colors-option
/app/node_modules/pumpify
/app/node_modules/@reduxjs
/app/node_modules/vary
/app/node_modules/serve-favicon
/app/node_modules/builtin-status-codes
/app/node_modules/has-unicode
/app/node_modules/array-includes
/app/node_modules/@nicolo-ribaudo
/app/node_modules/valid-data-url
/app/node_modules/roosterjs-editor-dom
/app/node_modules/p-reduce
/app/node_modules/babel-helper-call-delegate
/app/node_modules/clone-regexp
/app/node_modules/fault
/app/node_modules/webpack-dev-middleware
/app/node_modules/rollup-plugin-node-polyfills
/app/node_modules/@surma
/app/node_modules/querystring-es3
/app/node_modules/lodash.filter
/app/node_modules/remark-mdx
/app/node_modules/postcss-merge-rules
/app/node_modules/detective-amd
/app/node_modules/string-width
/app/node_modules/fs-constants
/app/node_modules/tweetnacl
/app/node_modules/decode-uri-component
/app/node_modules/unique-filename
/app/node_modules/cssnano-utils
/app/node_modules/p-retry
/app/node_modules/jest-junit
/app/node_modules/@cspotcode
/app/node_modules/postcss-merge-longhand
/app/node_modules/duplexer3
/app/node_modules/gitconfiglocal
/app/node_modules/react-helmet-async
/app/node_modules/ignore
/app/node_modules/pmcrypto
/app/node_modules/handlebars
/app/node_modules/readdir-glob
/app/node_modules/is-wsl
/app/node_modules/@xtuc
/app/node_modules/mdast-util-to-string
/app/node_modules/lazy-universal-dotenv
/app/node_modules/write
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
== ANIMATIONS.NOTIFICATION_OUT && isClosing) {
    34	            onExit();
    35	        }
    36	    };
    37	
    38	    return (
    39	        <div
    40	            aria-atomic="true"
    41	            role="alert"
    42	            className={classnames([
    43	                'p1',
    44	                'mb0-5',
    45	                'text-break',
    46	                CLASSES.NOTIFICATION,
    47	                CLASSES.NOTIFICATION_IN,
    48	                TYPES_CLASS[type] || TYPES_CLASS.success,
    49	                isClosing && CLASSES.NOTIFICATION_OUT,
    50	            ])}
    51	            onClick={onClick}
    52	            onAnimationEnd={handleAnimationEnd}
    53	        >
    54	            {children}
    55	        </div>
    56	    );
    57	};
    58	
    59	export default Notification;
    60	







[MSG 9] [user]
Observation: 

Here's the result of running `cat -n` on /app/packages/components/containers/notifications/interfaces.ts:
     1	import { ReactNode } from 'react';
     2	
     3	export type NotificationType = 'error' | 'warning' | 'info' | 'success';
     4	
     5	export interface NotificationOptions {
     6	    id: number;
     7	    key: any;
     8	    text: ReactNode;
     9	    type: NotificationType;
    10	    isClosing: boolean;
    11	    disableAutoClose?: boolean;
    12	}
    13	
    14	export interface CreateNotificationOptions extends Omit<NotificationOptions, 'id' | 'type' | 'isClosing' | 'key'> {
    15	    id?: number;
    16	    type?: NotificationType;
    17	    isClosing?: boolean;
    18	    expiration?: number;
    19	}
    20	







[MSG 10] [user]
Observation: The command 'bash -lc "grep -RIn "dangerouslySetInnerHTML\|DOMPurify\|sanitize\|external links\|target=\"_blank\"\|noopener noreferrer" /app/packages/components | sed -n '1,200p'"}' was cancelled because it took more than 450 seconds. Please try a different command that completes more quickly.

[MSG 11] [user]
Observation: The command 'bash -lc "grep -RIn "dangerouslySetInnerHTML\|DOMPurify\|sanitize" /app/packages/components | head -n 200"}' was cancelled because it took more than 450 seconds. Please try a different command that completes more quickly.

[MSG 12] [user]
Observation: 

Here's the result of running `cat -n` on /app/package.json:
     1	{
     2	    "name": "root",
     3	    "private": true,
     4	    "license": "GPL-3.0",
     5	    "workspaces": [
     6	        "applications/*",
     7	        "packages/*",
     8	        "tests",
     9	        "utilities/*"
    10	    ],
    11	    "scripts": {
    12	        "config-app": "(packages/config/install 2>/dev/null) || true",
    13	        "postinstall": "is-ci || (husky install; yarn run config-app)",
    14	        "start-all": "cd utilities/local-sso && bash ./run.sh",
    15	        "version": "yarn workspace scripts run version:applications"
    16	    },
    17	    "resolutions": {
    18	        "@types/jest": "^27.4.0",
    19	        "@types/react": "^17.0.39",
    20	        "@types/react-dom": "^17.0.11",
    21	        "safe-buffer": "^5.2.1"
    22	    },
    23	    "dependencies": {
    24	        "@proton/eslint-config-proton": "workspace:packages/eslint-config-proton",
    25	        "@proton/stylelint-config-proton": "workspace:packages/stylelint-config-proton",
    26	        "is-ci": "^3.0.1",
    27	        "typescript": "^4.5.5"
    28	    },
    29	    "devDependencies": {
    30	        "husky": "^7.0.4",
    31	        "lint-staged": "^12.3.4",
    32	        "prettier": "^2.5.1",
    33	        "sort-package-json": "^1.54.0"
    34	    },
    35	    "engines": {
    36	        "node": ">= v16.14.0"
    37	    },
    38	    "packageManager": "yarn@3.1.1"
    39	}
    40	







[MSG 13] [user]
Observation: 

Here's the result of running `cat -n` on /app/packages/components/containers/notifications/notificationsContext.ts:
     1	import { createContext } from 'react';
     2	import { NotificationsManager } from './manager';
     3	
     4	export type NotificationsContextValue = NotificationsManager;
     5	
     6	export default createContext<NotificationsManager>(null as unknown as NotificationsManager);
     7	







[MSG 14] [user]
Observation: 

Here's the result of running `cat -n` on /app/packages/components/hooks/useNotifications.tsx:
     1	import { useContext } from 'react';
     2	import NotificationsContext from '../containers/notifications/notificationsContext';
     3	
     4	const useNotifications = () => {
     5	    const manager = useContext(NotificationsContext);
     6	
     7	    if (!manager) {
     8	        throw new Error('Trying to use uninitialized NotificationsContext');
     9	    }
    10	
    11	    return manager;
    12	};
    13	
    14	export default useNotifications;
    15	







[MSG 15] [user]
Observation: 

Here's the result of running `cat -n` on /app/packages/components/containers/notifications/Children.tsx:
     1	import React, { useContext } from 'react';
     2	import NotificationsContext from './notificationsContext';
     3	import NotificationsChildrenContext from './childrenContext';
     4	import NotificationsContainer from './Container';
     5	
     6	const NotificationsChildren = () => {
     7	    const manager = useContext(NotificationsContext);
     8	    const children = useContext(NotificationsChildrenContext);
     9	
    10	    return (
    11	        <NotificationsContainer
    12	            notifications={children}
    13	            removeNotification={manager.removeNotification}
    14	            hideNotification={manager.hideNotification}
    15	        />
    16	    );
    17	};
    18	
    19	export default NotificationsChildren;
    20	







[MSG 16] [user]
Observation: 

Here's the result of running `cat -n` on /app/packages/components/containers/notifications/index.ts:
     1	export { default as NotificationsContainer } from './Container';
     2	export { default as NotificationsChildren } from './Children';
     3	export { default as NotificationsProvider } from './Provider';
     4	export { default as NotificationsContext } from './notificationsContext';
     5	export { default as NotificationsHijack } from './NotificationsHijack';
     6	export * from './notificationsContext';
     7	export * from './interfaces';
     8	







[MSG 17] [user]
Observation: 

Here's the result of running `cat -n` on /app/packages/components/containers/notifications/NotificationsHijack.tsx:
     1	import { FC } from 'react';
     2	import { CreateNotificationOptions, NotificationsContext, NotificationsContextValue } from '@proton/components';
     3	import { noop } from '@proton/shared/lib/helpers/function';
     4	
     5	interface NotificationsHijackProps {
     6	    onCreate: (options: CreateNotificationOptions) => void;
     7	}
     8	
     9	const NotificationsHijack: FC<NotificationsHijackProps> = ({ children, onCreate }) => {
    10	    const hijackedCreateNotification = (options: CreateNotificationOptions) => {
    11	        onCreate(options);
    12	
    13	        /* createNotification has to return a number */
    14	        return 42;
    15	    };
    16	
    17	    const context: NotificationsContextValue = {
    18	        createNotification: hijackedCreateNotification,
    19	        removeNotification: noop,
    20	        hideNotification: noop,
    21	        clearNotifications: noop,
    22	    };
    23	
    24	    return <NotificationsContext.Provider value={context}>{children}</NotificationsContext.Provider>;
    25	};
    26	
    27	export default NotificationsHijack;
    28	







[MSG 18] [user]
Observation: 

Here's the result of running `cat -n` on /app/packages/components/components/notifications/LinkConfirmationModal.tsx:
     1	import { useState } from 'react';
     2	import { c } from 'ttag';
     3	import { isEdge, isIE11, openNewTab } from '@proton/shared/lib/helpers/browser';
     4	import { updateConfirmLink } from '@proton/shared/lib/api/mailSettings';
     5	import { rtlSanitize } from '@proton/shared/lib/helpers/string';
     6	import { useApi, useEventManager } from '../../hooks';
     7	import { ConfirmModal } from '../modal';
     8	import { Button } from '../button';
     9	import { Alert } from '../alert';
    10	import { Href } from '../link';
    11	import { Checkbox } from '../input';
    12	import { Label } from '../label';
    13	
    14	interface Props {
    15	    onClose: () => void;
    16	    link?: string;
    17	    isOutside?: boolean;
    18	}
    19	
    20	const LinkConfirmationModal = ({ onClose, link = '', isOutside = false, ...rest }: Props) => {
    21	    const api = useApi();
    22	    const { call } = useEventManager();
    23	    const [dontAskAgain, setDontAskAgain] = useState(false);
    24	
    25	    // https://jira.protontech.ch/browse/SEC-574
    26	    const linkToShow = rtlSanitize(link);
    27	
    28	    // Both are not able to open the link
    29	    const punyCodeLink = /:\/\/xn--/.test(link);
    30	
    31	    const punyCodeLinkText =
    32	        isEdge() || isIE11()
    33	            ? c('Info')
    34	                  .t`This link may be a homograph attack and cannot be opened by Internet Explorer and Edge browsers. If you are certain the link is legitimate, please use a different browser to open it.`
    35	            : c('Info')
    36	                  .t`This link may be a homograph attack. Please verify this is the link you wish to visit, or don't open it.`;
    37	
    38	    const handleConfirm = async () => {
    39	        openNewTab(link);
    40	
    41	        if (dontAskAgain && !isOutside) {
    42	            await api(updateConfirmLink(0));
    43	            await call();
    44	        }
    45	    };
    46	
    47	    // Not really ellegant but the least bad solution I found to please TS
    48	    const additionalModalProps = { small: false };
    49	
    50	    return (
    51	        <ConfirmModal
    52	            onConfirm={handleConfirm}
    53	            onClose={onClose}
    54	            title={c('Title').t`Link confirmation`}
    55	            confirm={
    56	                // translator: this string is only for blind people, it will be vocalized: confirm opening of link https://link.com
    57	                <Button
    58	                    color="norm"
    59	                    type="submit"
    60	                    autoFocus
    61	                    aria-label={c('Action').t`Confirm opening of link ${linkToShow}`}
    62	                >
    63	                    {c('Action').t`Confirm`}
    64	                </Button>
    65	            }
    66	            {...rest}
    67	            {...additionalModalProps}
    68	        >
    69	            <Alert className="mb1 text-break" type="warning">
    70	                {`${c('Info').t`You are about to open another browser tab and visit:`} `}
    71	                <span className="text-bold">{linkToShow}</span>
    72	            </Alert>
    73	
    74	            {punyCodeLink && (
    75	                <Alert className="mb1" type="warning">
    76	                    {`${punyCodeLinkText} `}
    77	                    <Href
    78	                        url="https://protonmail.com/support/knowledge-base/homograph-attacks/"
    79	                        title="What are homograph attacks?"
    80	                    >
    81	                        {c('Info').t`Learn more`}
    82	                    </Href>
    83	                </Alert>
    84	            )}
    85	
    86	            {!isOutside && (
    87	                <Label className="flex">
    88	                    <Checkbox checked={dontAskAgain} onChange={() => setDontAskAgain(!dontAskAgain)} />
    89	                    {c('Label').t`Do not ask again`}
    90	                </Label>
    91	            )}
    92	        </ConfirmModal>
    93	    );
    94	};
    95	
    96	export default LinkConfirmationModal;
    97	






```
</details>

## 4. Contamination Signals

- **LOW RESOLUTION** (1/12 = 8%) — moderate contamination signal
- **TEST PRE-STAGING DETECTED** — tests modified via before_repo_set_cmd, may not appear in test_patch

## 5. Verdict

**Status**: LLM_ANALYZED → LIKELY_SEVERE
**Preliminary Assessment**: [To be determined after human review of trajectory + problem statement + test alignment]


## LLM Trajectory Analysis

**Model**: GPT-5 High - paper
**Analyzed**: 2026-04-12 19:55:27

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | contamination |
| Contamination type | test_coupling |
| Confidence | 0.9 |
| **Verdict** | **LIKELY_SEVERE** |

**Agent approach**: The agent traced the notification stack through the manager, provider, container, interfaces, and existing link-handling code to figure out where HTML rendering and deduplication should live. It also inspected related components like LinkConfirmationModal, suggesting it understood the task as a notification rendering/dedup problem, but it never submitted a patch.

**Contamination evidence**: The F2P tests assert on manager internals rather than externally stated behavior. In `should allow to create notifications with raw html text and deduplicate it`, the test requires the stored `text` field to be exactly a `<div dangerouslySetInnerHTML={...} />` React element with rewritten `<a>` attributes (`rel="noopener noreferrer"` and `target="_blank"`) and requires the notification `key` to equal the original raw HTML string. The problem statement only says HTML should be displayed safely and links should open securely/predictably; it does not require this exact wrapper element, use of `dangerouslySetInnerHTML`, or this keying scheme. In `should deduplicate react elements using the provided key`, the test requires a new `key` option on `createNotification` and deduplication of React-element notifications by that key, but the problem statement discusses API-response HTML strings and duplicate notifications, not React elements or a `key` API. A correct implementation using a different safe HTML rendering strategy (e.g. a parser/component-level rendering, existing link components, different dedupe token name, or only deduping string API messages) would fail these tests.

**Difficulty evidence**: None

**Full reasoning**: This task shows strong contamination signals. The agent appeared to understand the bug area and inspected exactly the right files, but the decisive issue is in the tests themselves: they verify specific implementation choices not recoverable from the problem statement. The statement asks for safe HTML rendering in notifications, secure/predictable link opening, and suppression of duplicate non-success notifications. Those are behavioral requirements. The F2P tests instead lock in the gold patch's internal representation: raw HTML must be transformed inside the manager into a React `<div>` with `dangerouslySetInnerHTML`, links must be rewritten with specific attributes, and deduplication for non-string React content must happen via a newly exposed `key` field on `createNotification`. None of those details are mandated by the spec, and there are plausible alternative correct solutions in this repo, especially given the existing link-handling infrastructure. The extra gold-patch changes outside the manager are just overpatch noise, but the tested manager behavior is overconstrained enough that an agent could solve the stated problem and still fail.
