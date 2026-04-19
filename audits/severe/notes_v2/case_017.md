# Case #17 Re-Audit Notes (v2)

**Instance**: `instance_protonmail__webclients-369fd37de29c14c690cb3b1c09a949189734026f`
**Date**: 2026-04-12
**Data Sources**: HuggingFace SWE-bench Pro (raw) + Docent trajectories (raw)

## 1. Problem Statement (from HuggingFace)

"### Title: Users cannot add or manage public holiday calendars in Calendar Settings\n\n### Description\n\nThe Calendar Settings interface does not support browsing, selecting, or initializing calendars that display public holidays based on a user’s country or language. This limitation affects usability and forces users to manually input holidays, which should be offered automatically or through a simple selection interface.\n\nExisting components that manage calendar rendering and setup, such a...

**Type**: js | **Repo**: protonmail/webclients
**Requirements provided**: Yes
**Interface provided**: Yes

## 2. Raw Metrics

| Metric | Value |
|--------|-------|
| Gold patch hunks | 33 |
| Gold patch files | 33 |
| Gold patch size | 103181 chars |
| Test patch size | 36767 chars |
| Test patch files | 4 |
| F2P tests | 12 |
| Has test pre-staging | True |
| before_repo_set_cmd | Yes |

### Pre-staged test files
```
packages/components/components/country/CountrySelect.helpers.test.ts
packages/components/containers/calendar/holidaysCalendarModal/tests/HolidaysCalendarModal.test.tsx
packages/components/containers/calendar/settings/CalendarsSettingsSection.test.tsx
packages/shared/test/calendar/holidaysCalendar/holidaysCalendar.spec.ts
```
**WARNING**: Tests may be modified without appearing in test_patch.

### before_repo_set_cmd
```
git reset --hard 42082399f3c51b8e9fb92e54312aafda1838ec4d
git clean -fd 
git checkout 42082399f3c51b8e9fb92e54312aafda1838ec4d 
git checkout 369fd37de29c14c690cb3b1c09a949189734026f -- packages/components/components/country/CountrySelect.helpers.test.ts packages/components/containers/calendar/holidaysCalendarModal/tests/HolidaysCalendarModal.test.tsx packages/components/containers/calendar/settings/CalendarsSettingsSection.test.tsx packages/shared/test/calendar/holidaysCalendar/holidaysCalendar.
```

## 3. Trajectory Evidence

### Resolution Rate: 0/12 (0%)

| Model | Resolved | Turns |
|-------|----------|-------|
| Claude Opus 4.1 - paper | FAIL | 29 |
| Gemini 2.5 Pro Preview - paper | FAIL | 12 |
| GPT-5 High - paper | FAIL | 42 |
| GPT OSS - paper | FAIL | 35 |
| Kimi - paper | FAIL | 51 |
| Claude 4.5 Sonnet - 10132025 | FAIL | 81 |
| Claude 4 Sonnet - 10132025 | FAIL | 124 |
| GPT-5 - 10132025 | FAIL | 38 |
| Gemini 2.5 Pro Preview -- debug-oct22 | FAIL | 64 |
| GPT-5 Codex -- debug-oct22 | FAIL | 60 |
| GLM-4.5 -- 10222025 | FAIL | 147 |
| Claude 4.5 Haiku -- 10222025 | FAIL | 90 |

### Representative Trajectory: Claude Opus 4.1 - paper
- **Resolved**: False
- **Turns**: 52
- **Total tokens**: ~48501
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
/app/package.json
/app/node_modules
/app/node_modules/unix-dgram
/app/node_modules/p-defer
/app/node_modules/@mapbox
/app/node_modules/glob-parent
/app/node_modules/serve-index
/app/node_modules/mdast-util-to-string
/app/node_modules/sort-keys
/app/node_modules/cache-base
/app/node_modules/decompress-response
/app/node_modules/ecdsa-sig-formatter
/app/node_modules/update-notifier
/app/node_modules/lodash.flatten
/app/node_modules/unist-util-visit-parents
/app/node_modules/cookie
/app/node_modules/detective-stylus
/app/node_modules/repeat-string
/app/node_modules/core-js-pure
/app/node_modules/is-weakset
/app/node_modules/node-dir
/app/node_modules/camelcase
/app/node_modules/iconv-lite
/app/node_modules/browserify-sign
/app/node_modules/xmlbuilder
/app/node_modules/detect-node
/app/node_modules/is-callable
/app/node_modules/strict-event-emitter
/app/node_modules/css-declaration-sorter
/app/node_modules/@esbuild
/app/node_modules/ajv
/app/node_modules/character-entities-legacy
/app/node_modules/loud-rejection
/app/node_modules/qs
/app/node_modules/engine.io
/app/node_modules/p-cancelable
/app/node_modules/proxy-from-env
/app/node_modules/proton-preview-sandbox
/app/node_modules/seek-bzip
/app/node_modules/is-decimal
/app/node_modules/source-map-js
/app/node_modules/wbuf
/app/node_modules/he
/app/node_modules/to-arraybuffer
/app/node_modules/strip-outer
/app/node_modules/jest-mock
/app/node_modules/babel-helpers
/app/node_modules/babel-loader
/app/node_modules/type-fest
/app/node_modules/netlify-onegraph-internal
/app/node_modules/browserify-aes
/app/node_modules/sourcemap-codec
/app/node_modules/html-escaper
/app/node_modules/esutils
/app/node_modules/detab
/app/node_modules/prelude-ls
/app/node_modules/expect
/app/node_modules/@webpack-cli
/app/node_modules/is-weakref
/app/node_modules/parent-module
/app/node_modules/fetch-retry
/app/node_modules/stream-shift
/app/node_modules/p-wait-for
/app/node_modules/ical.js
/app/node_modules/url-parse
/app/node_modules/fastify-plugin
/app/node_modules/cp-file
/app/node_modules/parse-ms
/app/node_modules/babel-plugin-syntax-export-extensions
/app/node_modules/unherit
/app/node_modules/babel-plugin-polyfill-corejs2
/app/node_modules/get-symbol-from-current-process-h
/app/node_modules/pbkdf2
/app/node_modules/babel-plugin-transform-es2015-literals
/app/node_modules/@jridgewell
/app/node_modules/vfile
/app/node_modules/figures
/app/node_modules/kleur
/app/node_modules/http-deceiver
/app/node_modules/date-time
/app/node_modules/postcss-flexbugs-fixes
/app/node_modules/iterate-iterator
/app/node_modules/p-limit
/app/node_modules/domutils
/app/node_modules/es-module-lexer
/app/node_modules/svgo
/app/node_modules/@fastify
/app/node_modules/relateurl
/app/node_modules/which-boxed-primitive
/app/node_modules/asynckit
/app/node_modules/depd
/app/node_modules/set-blocking
/app/node_modules/spdx-exceptions
/app/node_modules/eslint-plugin-custom-rules
/app/node_modules/redent
/app/node_modules/@szmarczak
/app/node_modules/@surma
/app/node_modules/on-headers
/app/node_modules/array-timsort
/app/node_modules/serialize-javascript
/app/node_modules/regenerator-runtime
/app/node_modules/istanbul-lib-report
/app/node_modules/watchpack-chokidar2
/app/node_modules/move-file
/app/node_modules/p-locate
/app/node_modules/get-package-type
/app/node_modules/fork-ts-checker-webpack-plugin
/app/node_modules/lodash.bind
/app/node_modules/fast-json-parse
/app/node_modules/@netlify
/app/node_modules/@xmldom
/app/node_modules/vue-sfc-parser
/app/node_modules/enabled
/app/node_modules/resize-observer
/app/node_modules/esprima
/app/node_modules/parseurl
/app/node_modules/acorn-walk
/app/node_modules/json-parse-even-better-errors
/app/node_modules/is-regexp
/app/node_modules/async-sema
/app/node_modules/eslint-webpack-plugin
/app/node_modules/base64-arraybuffer
/app/node_modules/buffer-alloc-unsafe
/app/node_modules/valid-data-url
/app/node_modules/proxy-addr
/app/node_modules/@openpgp
/app/node_modules/babel-plugin-transform-es2015-shorthand-properties
/app/node_modules/cssnano-preset-default
/app/node_modules/resolve-cwd
/app/node_modules/babel-plugin-syntax-do-expressions
/app/node_modules/trim-newlines
/app/node_modules/get-value
/app/node_modules/globjoin
/app/node_modules/@pkgjs
/app/node_modules/workerpool
/app/node_modules/browserify-des
/app/node_modules/resolve.exports
/app/node_modules/cli-truncate
/app/node_modules/for-each
/app/node_modules/log-update
/app/node_modules/author-regex
/app/node_modules/fastq
/app/node_modules/console-control-strings
/app/node_modules/type-is
/app/node_modules/hash.js
/app/node_modules/@dabh
/app/node_modules/proton-account
/app/node_modules/os-name
/app/node_modules/lower-case
/app/node_modules/sort-package-json
/app/node_modules/@eslint-community
/app/node_modules/available-typed-arrays
/app/node_modules/react-element-to-jsx-string
/app/node_modules/yallist
/app/node_modules/socket.io
/app/node_modules/prr
/app/node_modules/@testing-library
/app/node_modules/enhanced-resolve
/app/node_modules/domino
/app/node_modules/string.prototype.trimstart
/app/node_modules/negotiator
/app/node_modules/eventemitter3
/app/node_modules/is-fullwidth-code-point
/app/node_modules/ylru
/app/node_modules/babel-plugin-transform-es2015-destructuring
/app/node_modules/inline-style-parser
/app/node_modules/babel-helper-define-map
/app/node_modules/ast-module-types
/app/node_modules/path-browserify
/app/node_modules/thunky
/app/node_modules/neo-async
/app/node_modules/koa-compose
/app/node_modules/espree
/app/node_modules/strip-eof
/app/node_modules/color-convert
/app/node_modules/tomlify-j0.4
/app/node_modules/safe-json-stringify
/app/node_modules/form-data
/app/node_modules/pino
/app/node_modules/handle-thing
/app/node_modules/babel-plugin-ttag
/app/node_modules/inherits
/app/node_modules/unist-util-generated
/app/node_modules/slice-ansi
/app/node_modules/@tsconfig
/app/node_modules/jest-config
/app/node_modules/react-is
/app/node_modules/mkdirp-classic
/app/node_modules/svelte
/app/node_modules/proton-verify
/app/node_modules/fragment-cache
/app/node_modules/is-path-inside
/app/node_modules/sprintf-js
/app/node_modules/@types
/app/node_modules/comment-json
/app/node_modules/encodeurl
/app/node_modules/co
/app/node_modules/html-void-elements
/app/node_modules/on-exit-leak-free
/app/node_modules/htmlparser2
/app/node_modules/@vercel
/app/node_modules/babel-helper-get-function-arity
/app/node_modules/react-error-boundary
/app/node_modules/@typescript-eslint
/app/node_modules/luxon
/app/node_modules/is-bigint
/app/node_modules/lodash.merge
/app/node_modules/typedarray-to-buffer
/app/node_modules/stream-browserify
/app/node_modules/strict-uri-encode
/app/node_modules/to-regex-range
/app/node_modules/lowercase-keys
/app/node_modules/backoff
/app/node_modules/micro-api-client
/app/node_modules/path-exists
/app/node_modules/rollup
/app/node_modules/log-symbols
/app/node_modules/hmac-drbg
/app/node_modules/currently-unhandled
/app/node_modules/jsx-ast-utils
/app/node_modules/ejs
/app/node_modules/fast-json-stable-stringify
/app/node_modules/fs-monkey
/app/node_modules/better-opn
/app/node_modules/vfile-location
/app/node_modules/is-ci
/app/node_modules/is-yarn-global
/app/node_modules/spdy-transport
/app/node_modules/browser-stdout
/app/node_modules/is-promise
/app/node_modules/fraction.js
/app/node_modules/snapdragon-util
/app/node_modules/path-key
/app/node_modules/from2
/app/node_modules/argparse
/app/node_modules/domhandler
/app/node_modules/dom-helpers
/app/node_modules/webpack-dev-server
/app/node_modules/husky
/app/node_modules/mimic-response
/app/node_modules/latest-version
/app/node_modules/minimalistic-crypto-utils
/app/node_modules/emoji-mart
/app/node_modules/pathval
/app/node_modules/babel-plugin-syntax-async-functions
/app/node_modules/infer-owner
/app/node_modules/type-detect
/app/node_modules/jes
```
</details>

### Trajectory Tail (submission + results)
<details>
<summary>Click to expand (last ~3K tokens)</summary>

```
don't need to fill this state on holiday calendar edition since this field will not be displayed
   160	
   161	    const canShowHint = defaultCalendar && defaultCalendar === selectedCalendar && !hasAlreadyJoinedDefaultCalendar;
   162	
   163	    // We want to display one option per country, so we need to filter them
   164	    const filteredCalendars: HolidaysDirectoryCalendar[] = useMemo(() => {
   165	        return uniqueBy(directory, ({ CountryCode }) => CountryCode).sort((a, b) => a.Country.localeCompare(b.Country));
   166	    }, [holidaysCalendars]);
   167	
   168	    // We might have several Calendars for a specific country, with different languages
   169	    const languageOptions: HolidaysDirectoryCalendar[] = useMemo(() => {
   170	        return getHolidaysCalendarsFromCountryCode(directory, selectedCalendar?.CountryCode || '');
   171	    }, [selectedCalendar]);
   172	
   173	    const handleSubmit = async () => {
   174	        try {
   175	            if (!onFormSubmit() || hasAlreadyJoinedSelectedCalendar) {
   176	                return;
   177	            }
   178	
   179	            if (selectedCalendar) {
   180	                /**
   181	                 * Based on the inputHolidaysCalendar, we have several cases to cover:
   182	                 * 1 - The user is updating colors or notifications of his holiday calendar
   183	                 *      => We perform a classic calendar update
   184	                 * 2 - The user is updating the country or the language of his holiday calendar
   185	                 *      => We need to leave the old holiday calendar and then join a new one
   186	                 * 3 - The user is joining a holiday calendar
   187	                 *      => We just want to join a holiday calendar
   188	                 */
   189	                if (inputHolidaysCalendar && inputCalendar) {
   190	                    // 1 - Classic update
   191	                    if (selectedCalendar === inputCalendar) {
   192	                        const calendarPayload: CalendarCreateData = {
   193	                            Name: inputHolidaysCalendar.Name,
   194	                            Description: inputHolidaysCalendar.Description,
   195	                            Color: color,
   196	                            Display: inputHolidaysCalendar.Display,
   197	                        };
   198	                        const calendarSettingsPayload: Required<
   199	                            Pick<
   200	                                CalendarSettings,
   201	                                'DefaultEventDuration' | 'DefaultPartDayNotifications' | 'DefaultFullDayNotifications'
   202	                            >
   203	                        > = {
   204	                            DefaultEventDuration: 30, // TODO check
   205	                            DefaultFullDayNotifications: modelToNotifications(dedupeNotifications(notifications)),
   206	                            DefaultPartDayNotifications: [],
   207	                        };
   208	                        await updateCalendar(
   209	                            inputHolidaysCalendar,
   210	                            calendarPayload,
   211	                            calendarSettingsPayload,
   212	                            readCalendarBootstrap,
   213	                            getAddresses,
   214	                            api
   215	                        );
   216	                    } else {
   217	                        // 2 - Leave old holiday calendar and join a new one
   218	                        await api(removeMember(inputHolidaysCalendar.ID, inputHolidaysCalendar.Members[0].ID));
   219	
   220	                        const { calendarID, addressID, payload } = await getJoinHolidaysCalendarData({
   221	                            holidaysCalendar: selectedCalendar,
   222	                            addresses,
   223	                            getAddressKeys,
   224	                            color,
   225	                            notifications,
   226	                        });
   227	                        await api(joinHolidaysCalendar(calendarID, addressID, payload));
   228	                    }
   229	                } else {
   230	                    // 3 - Joining a holiday calendar
   231	                    const { calendarID, addressID, payload } = await getJoinHolidaysCalendarData({
   232	                        holidaysCalendar: selectedCalendar,
   233	                        addresses,
   234	                        getAddressKeys,
   235	                        color,
   236	                        notifications,
   237	                    });
   238	                    await api(joinHolidaysCalendar(calendarID, addressID, payload));
   239	
   240	                    createNotification({
   241	                        type: 'success',
   242	                        text: c('Notification in holidays calendar modal').t`Calendar added`,
   243	                    });
   244	                }
   245	
   246	                await call();
   247	
   248	                rest.onClose?.();
   249	            }
   250	        } catch (error) {
   251	            console.log(error);
   252	            noop();
   253	        }
   254	    };
   255	
   256	    const handleSelectCountry = (value: string) => {
   257	        /*
   258	         * Get the default calendar selected
   259	         * If only one calendar in the country is found, return that one
   260	         * Else try to get the default one based on the user language
   261	         */
   262	        const newSelected = findHolidaysCalendarByCountryCodeAndLanguageCode(directory, value, languageCode);
   263	        if (newSelected) {
   264	            setSelectedCalendar(newSelected);
   265	        }
   266	    };
   267	
   268	    const handleSelectLanguage = ({ value }: { value: any }) => {
   269	        const calendarsFromCountry = languageOptions.find((calendar) => calendar.Language === value);
   270	        setSelectedCalendar(calendarsFromCountry);
   271	    };
   272	
   273	    const handleGetInputCalendarBootstrap = async (inputCalendar: VisualCalendar) => {
   274	        setInputCalendarLoading(true);
   275	        const { CalendarSettings } = await getCalendarBootstrap(inputCalendar.ID);
   276	        const notifications = notificationsToModel(CalendarSettings.DefaultFullDayNotifications, true);
   277	        setNotifications(notifications);
   278	        setInputCalendarLoading(false);
   279	    };
   280	
   281	    const getErrorText = () => {
   282	        if (hasAlreadyJoinedSelectedCalendar) {
   283	            // TODO Check this error string with product
   284	            return c('Error').t`You already subscribed to this holidays calendar`;
   285	        }
   286	
   287	        return c('Error').t`To add a holiday calendar you must select a country`;
   288	    };
   289	
   290	    useEffect(() => {
   291	        if (inputHolidaysCalendar) {
   292	            void handleGetInputCalendarBootstrap(inputHolidaysCalendar);
   293	        }
   294	    }, []);
   295	
   296	    return (
   297	        <Modal as={Form} fullscreenOnMobile onSubmit={() => withLoading(handleSubmit())} size="large" {...rest}>
   298	            {inputCalendarLoading ? (
   299	                <Loader />
   300	            ) : (
   301	                <>
   302	                    <ModalHeader
   303	                        title={isEdit ? c('Modal title').t`Edit calendar` : c('Modal title').t`Add public holidays`}
   304	                        subline={
   305	                            isEdit ? undefined : c('Modal title').t`Get a country's official public holidays calendar.`
   306	                        }
   307	                    />
   308	                    <ModalContent className="holidays-calendar-modal-content">
   309	                        <CountrySelect
   310	                            options={filteredCalendars.map((calendar) => ({
   311	                                countryName: calendar.Country,
   312	                                countryCode: calendar.CountryCode,
   313	                            }))}
   314	                            preSelectedOption={
   315	                                canPreselect
   316	                                    ? {
   317	                                          countryName: defaultCalendar.Country,
   318	                                          countryCode: defaultCalendar.CountryCode,
   319	                                      }
   320	                                    : undefined
   321	                            }
   322	                            value={
   323	                                selectedCalendar
   324	                                    ? {
   325	                                          countryName: selectedCalendar.Country,
   326	                                          countryCode: selectedCalendar.CountryCode,
   327	                                      }
   328	                                    : undefined
   329	                            }
   330	                            preSelectedOptionDivider={c('holiday calendar').t`Based on your time zone`}
   331	                            onSelectCountry={handleSelectCountry}
   332	                            validator={validator}
   333	                            error={hasAlreadyJoinedSelectedCalendar}
   334	                            errorText={getErrorText()}
   335	                            hint={canShowHint ? c('holiday calendar').t`Based on your time zone` : undefined}
   336	                        />
   337	
   338	                        {selectedCalendar && languageOptions.length > 1 && (
   339	                            <InputFieldTwo
   340	                                id="languageSelect"
   341	                                as={SelectTwo}
   342	                                label={c('Label').t`Language`}
   343	                                value={selectedCalendar.Language}
   344	                                onChange={handleSelectLanguage}
   345	                                aria-describedby="label-languageSelect"
   346	                                data-testid="holidays-calendar-modal:language-select"
   347	                            >
   348	                                {languageOptions.map((option) => (
   349	                                    <Option key={option.Language} value={option.Language} title={option.Language} />
   350	                                ))}
   351	                            </InputFieldTwo>
   352	                        )}
   353	
   354	                        <InputFieldTwo
   355	                            id="colorSelect"
   356	                            as={ColorPicker}
   357	                            label={c('Label').t`Color`}
   358	                            color={color}
   359	                            onChange={(color: string) => setColor(color)}
   360	                            data-testid="holidays-calendar-modal:color-select"
   361	                        />
   362	
   363	                        {showNotification && (
   364	                            <InputFieldTwo
   365	                                id="default-full-day-notification"
   366	                                as={Notifications}
   367	                                label={c('Label').t`Notifications`}<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>







[MSG 49] [assistant]
Perfect! Now let me check the HolidaysCalendarModal to understand how it works:

[MSG 50] [user]
Observation: 







[MSG 51] [assistant]
Now I have a comprehensive understanding. Let me check to see if there are any helpers for setup calendars:
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
**Analyzed**: 2026-04-12 19:01:34

| Field | Value |
|-------|-------|
| Agent understood problem | True |
| Agent addressed spec | False |
| Failure reason | contamination |
| Contamination type | test_coupling |
| Confidence | 0.94 |
| **Verdict** | **CONFIRMED_SEVERE** |

**Agent approach**: The agent correctly homed in on the calendar setup, sidebar, settings, and holidays-related hooks/helpers, reading the key files that would need changes for adding and suggesting public holiday calendars. It never produced a patch, but its exploration shows it understood the intended feature area.

**Contamination evidence**: The clearest contamination is in the staged F2P CountrySelect helper tests: they require a specific helper API rename (`getAllDropdownOptions` instead of `getCountryDropdownOptions`) and a hidden internal sentinel encoding for preselected countries (`countryCode: 'fr-preselected'`). None of that is stated or reasonably inferable from the problem statement, which only describes adding/browsing/suggesting holiday calendars. A different but fully correct implementation of the country preselection UX would still fail these tests. The holidays modal tests also assert undisclosed details such as exact copy changes ('You already added this holidays calendar') and a particular language fallback behavior, which go beyond the public spec.

**Difficulty evidence**: None

**Full reasoning**: This task looks contaminated rather than merely difficult. The public problem statement asks for holiday calendars to be browseable/addable in Calendar Settings, suggested during setup based on country/language, and correctly handled in relevant calendar components. Those are broad behavioral requirements. But the F2P suite is coupled to very specific implementation details from the gold patch: it imports and expects a renamed helper function in `CountrySelect.helpers`, checks for an exact internal representation of preselected options using a magic `-preselected` suffix, and verifies precise copy and selection behavior in `HolidaysCalendarModal` that are not specified in the prompt. That means an agent could implement the feature correctly at the product level—showing a suggested holiday calendar, allowing add/manage flows, and rendering holidays calendars properly—yet still fail because it did not reproduce the gold patch’s helper API shape and internal option encoding. The agent’s trajectory does not show misunderstanding; it investigated the right areas. Its lack of a patch is consistent with the task being both large and underspecified, but the decisive evidence comes from the tests themselves, which are not specification-faithful.
