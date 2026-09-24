# AJI-029 — Zero-Cost Job Provider Evaluation

**Role:** NERO Planner · **Type:** research only · **Depends on:** AJI-028
**Date:** 2026-09-24

No production code, database, frontend or AJI-028 foundation file was changed.
No account was created, no API was called, no key was added, nothing was scraped.

## Decision summary

**No provider is approved.** No candidate passes every check on
primary-source evidence.

- **Himalayas** is the only candidate with no known blocker. Its unresolved
  terms questions (storage, display behind a login, how its general Terms
  apply) mean it stays **UNVERIFIED — DO NOT INTEGRATE** until those are
  answered.
- **USAJOBS** is a narrow secondary candidate (federal jobs only). It needs a
  free API key and OPM's written word on AI processing, because its terms bar
  "derivative works". **UNVERIFIED — DO NOT INTEGRATE.**
- Everything else is **disqualified** or **UNVERIFIED — DO NOT INTEGRATE**.
  See section B.

## How the evidence was gathered, and its limits

This session's network policy blocks every provider host. Tested
2026-09-24: `curl` to himalayas.app, developer.usajobs.gov, themuse.com,
remotive.com, jobicy.com, arbeitnow.com, developer.adzuna.com, jooble.org,
careeronestop.org, boards-api.greenhouse.io and theirstack.com all got
`403 CONNECT` from the egress proxy. The page fetcher returned
`EGRESS_BLOCKED` for himalayas.app.

So every claim below comes from **web search result excerpts** of the linked
pages, not a full read of them. AJI-028 had the same limit. Each claim carries
a label:

- **[official]**: the excerpt came from the provider's own domain.
- **[3rd-party]**: the excerpt came only from a third-party site (Apify
  listings, API directories, blogs). This is weaker evidence.

Excerpts can leave out qualifying clauses. A missing clause is **not** proof
that a restriction doesn't exist. That is why no provider gets approved here.

## NERO facts that decide eligibility (checked in this repo)

| Fact | Where | Why it matters |
|---|---|---|
| Jobs are shown **only after login**. `(app)/layout.tsx` wraps `/jobs` in `AuthGate`, which redirects to `/login`. | `apps/web/app/(app)/layout.tsx`, `apps/web/app/(app)/auth-gate.tsx` | Some providers forbid showing their jobs behind a signup or login. |
| `GET /jobs` itself allows anonymous calls (`get_optional_current_user`). | `apps/api/routers/jobs.py:190` | This is the API, not the product UI. Users reach jobs through the gated UI. |
| NERO does **not** re-publish jobs to Google Jobs or other boards. There is no `JobPosting` JSON-LD and no sitemap in `apps/web`. | grep of `apps/web` | Several providers forbid passing their jobs on to Google Jobs, LinkedIn, Jooble and similar. |
| NERO runs AI on jobs: match, eligibility, intelligence, requirement intelligence, ATS. | `apps/api/routers/jobs.py` | Terms have to allow AI processing. |
| AJI-028 contract: `expires_at` only when the provider states it. U.S. eligibility must be explicit. A worldwide posting is **not** U.S.-eligible. At most 5 pages per run (`MAX_PAGES_PER_RUN`), every 6 h. | `services/job_discovery/README.md` | Decides what adapter output is usable. |

## Comparison table

| Provider | $0? | Account | Business Account | API/Feed | U.S. Jobs | Storage Allowed | AI Processing | Display Allowed | Attribution | Key Restrictions |
|---|---|---|---|---|---|---|---|---|---|---|
| **Himalayas** | Yes | No (no auth) | No | JSON API (browse + search), RSS | Remote only. U.S. only where `locationRestrictions` names the U.S. (empty = worldwide, not U.S.-eligible under AJI-028) | Implied ("apps, databases", "backfill job boards"). **No explicit clause seen** | Implied ("feed AI agents"). **No explicit clause seen** | Yes, in your own app or site. **Behind a login: not addressed in excerpts** | Link to the Himalayas job URL **and** name Himalayas as the source | No submitting jobs to third-party sites (Jooble, Neuvoo, Google Jobs, LinkedIn). 60 req/min. 20 jobs per request. General Terms bar copying or using information "without the consent of Himalayas" |
| **USAJOBS** | Yes | **Yes**: free API key tied to an email and a registration form | No | JSON REST (Search API) | Yes, U.S. **federal** jobs only | Yes, for internal app use (normalize, dedupe) | **Unclear**: "no derivative works"; displayed values must not be altered | Yes, with credit and users sent to USAJOBS to apply | Credit USAJOBS as the source | Use only by the registered requester. No other use without OPM written approval. No redistribution, no competing feed, no derivative works |
| **The Muse** | Yes | Optional (key raises the limit) | No | JSON REST v2 | Yes, mostly U.S. (location list) | **Unclear**. Copies must be destroyed on termination | **Unclear** | **Conflicting** (see B) | Link back (AJI-028) | "Not … copy, distribute, display … any Muse Content … without prior written permission." Revocable license. No expiry field, no employment type |
| **Remotive** | Yes | No | No | JSON API | Remote. Location is free text | Not addressed | Not addressed | **No, behind a signup** | Link to the Remotive URL and name Remotive | Showing jobs "to collect signups/email addresses" breaches its terms. 24 h delay. At most 4 fetches a day. No third-party boards |
| **Jobicy** | Yes (public tier) | No | No | JSON API, RSS | Remote, with a region filter | Implied ("cache responses") | Implied ("summaries") | Yes in own products. **Login gating: unresolved** (AJI-028 found a ban; not re-found now) | Name Jobicy as the source and keep the canonical Jobicy URL | At most one request an hour. No distribution to Jooble, Google Jobs, LinkedIn |
| **Greenhouse / Lever / Ashby** | Yes | No | No | Per-employer JSON boards | Depends on the employer | Per employer | Per employer | Per employer | Per employer | Built for an employer's **own** careers site. Aggregating many employers needs each employer's permission |
| **CareerOneStop / NLx** | Yes | **Yes** | **Yes**: organization request | REST | Yes | Per agreement | Per agreement | Per agreement | Per agreement | Every Jobs API request is approved by the NLx Research Hub Governance Board |
| **Adzuna** | **No** for ongoing commercial use | Yes (app ID and key) | No | REST | Yes | No, "extract … for commercial reuse" is a breach | Unclear | Yes | "Jobs by Adzuna" on every advert | Commercial use limited to a **14-day trial**, then a licence "may be required". 250 calls a day |
| **Jooble** | Limited | **Yes**: request form needs a company website | Effectively yes | REST | Yes (jooble.org key = U.S.) | Unclear | Unclear | Unclear | Unclear | 500 **lifetime** requests per key [3rd-party] |
| **TheirStack** | Only 200 jobs a month | **Yes** | No | REST | Yes | Unread | Unread | Unread | Unread | Paid after 200 API credits a month (1 credit = 1 job). ToS not found |
| Remote OK *(new; not in AJI-028 list)* | Yes | No | No | JSON API | Remote. Location is free text | Not addressed | Not addressed | Yes, with a followed backlink | Direct "follow" link and name Remote OK | 24 h delay. Real-time access costs $10k a month. Logo is trademarked |
| Arbeitnow *(new; not in AJI-028 list)* | Yes | No | No | JSON API | **No**: Germany, EU, UK and remote | Unread | Unread | Unread | Unread | Coverage is outside NERO's U.S. scope |
| LinkedIn / Indeed / Google Jobs | — | — | — | No permitted public job-search API | — | — | — | — | — | Carried over from AJI-028. Not re-researched |

## A. Evidence for each provider

### Himalayas
- Free, no authentication. Returns titles, company, salary, location and
  timezone restrictions, categories, application links **[official]**:
  [himalayas.app/api](https://himalayas.app/api),
  [docs/remote-jobs-api](https://himalayas.app/docs/remote-jobs-api)
- "Anyone can use the interface, but please link back to the URL found on
  Himalayas AND mention Himalayas as the original source. Please do not submit
  Himalayas jobs to third-party websites, including but not limited to Jooble,
  Neuvoo, Google Jobs, or LinkedIn Jobs." The same wording is on the RSS feed
  **[official]**: [himalayas.app/api](https://himalayas.app/api),
  [himalayas.app/rss](https://himalayas.app/rss)
- Uses listed: "backfill other remote job boards, power job search
  experiences, populate internal dashboards, or feed AI agents and automation
  workflows". "Browse API is best for building apps, databases, or dashboards"
  **[official]**: [docs/ai-agents](https://himalayas.app/docs/ai-agents),
  [himalayas.app/api](https://himalayas.app/api)
- General Terms: no scraping. Users may not "copy, use, disclose or distribute
  any information obtained from the Services without the consent of
  Himalayas" **[official]**: [himalayas.app/terms](https://himalayas.app/terms).
  The API page reads like that consent, but the excerpts never say so outright.
- Rate limit 60 req/min (429 when exceeded). `limit` defaults to 20, max 20.
  Cursor pagination (`nextCursor`). `offset` still works but is deprecated
  **[official]**: [docs/remote-jobs-api](https://himalayas.app/docs/remote-jobs-api)
- Endpoints: browse `https://himalayas.app/jobs/api`, and search
  `https://himalayas.app/jobs/api/search` with country, worldwide, employment
  type, seniority, sort and page filters **[official]**:
  [himalayas.app/api](https://himalayas.app/api)
- `expiryDate`, `pubDate`, `locationRestrictions` (empty = worldwide),
  `employmentType` (Full Time, Part Time, Contractor, Temporary, Intern…)
  **[3rd-party]**: [Apify Himalayas listing](https://apify.com/himalayas/remote-jobs),
  [limiop issue](https://github.com/taha-kms/limiop/issues/355).
  AJI-028 also recorded "states an expiry date".

### USAJOBS
- Data is "for the explicit use of the requesting company or individual
  identified on the USAJOBS Program Office API Registration Form. No other use
  … without prior approval, in writing, from OPM USAJOBS" **[official]**:
  [developer.usajobs.gov](https://developer.usajobs.gov/),
  [terms-of-use](https://developer.usajobs.gov/guides/terms-of-use)
- "May not rent, lease, loan, sell, trade or create derivative works of USAJOBS
  API services and data, in whole or in part" **[official]**:
  [terms-of-use](https://developer.usajobs.gov/guides/terms-of-use)
- May store and reformat for internal purposes (normalizing, deduplicating),
  provided displayed values are unaltered, USAJOBS is credited, and users are
  sent to USAJOBS to apply. No competing product or standalone feed
  **[official excerpt]**: [terms-of-use](https://developer.usajobs.gov/guides/terms-of-use).
  This sits awkwardly with the "derivative works" clause. Only a full read can
  settle it.
- Key requested with an email at
  [apirequest](https://developer.usajobs.gov/apirequest/index). Headers `Host`,
  `User-Agent` (registered email), `Authorization-Key`. `ResultsPerPage` up to
  500 **[official + 3rd-party]**:
  [guides/authentication](https://developer.usajobs.gov/guides/authentication),
  [JobsPipe](https://jobspipe.dev/sources/usajobs)

### The Muse
- License to "obtain and distribute Muse Content to format and display it
  through applications". Also "agree not to … copy, distribute, display … any
  Muse Content or Services without prior written permission". Revocable. On
  termination, destroy all copies **[official]**:
  [API v2 terms](https://www.themuse.com/developers/api/v2/terms)
- 500 req/h without a key, 3,600 req/h with a registered key. 403 when
  exceeded **[official]**: [API v2](https://www.themuse.com/developers/api/v2)
- No keyword search, no salary, no employment type. Recorded in AJI-028 and
  the `provider_scorecard` eval adapter docstring. No expiry field found.

### Remotive
- "Displaying Remotive jobs in order to collect signups/email addresses to show
  a listing" breaches its terms. Must link back and name Remotive, or access
  ends. No submitting to Jooble, Neuvoo, Google Jobs, LinkedIn Jobs
  **[official]**: [support.remotive.com](https://support.remotive.com/en/article/list-remote-jobs-public-api-105pww2/),
  [remotive.com/remote-jobs/api](https://remotive.com/remote-jobs/api)
- Jobs delayed 24 h. At most 4 fetches a day. More than 2 requests a minute is
  blocked **[official]**:
  [github.com/remotive-com/remote-jobs-api](https://github.com/remotive-com/remote-jobs-api)

### Jobicy
- Use in your own products without asking. Keep Jobicy as the source and keep
  the canonical URL. Summaries and your own interfaces are allowed. No
  distribution to Jooble, Google Jobs, LinkedIn. At most one request an hour
  **[official]**: [jobicy.com/jobs-rss-feed](https://jobicy.com/jobs-rss-feed),
  [github.com/Jobicy/remote-jobs-api](https://github.com/Jobicy/remote-jobs-api)
- AJI-028 recorded that its terms forbid showing jobs behind a signup or login.
  This session's excerpts neither confirm nor contradict that.

### Greenhouse / Lever / Ashby
- Greenhouse Job Board API is for building "a custom job board or career site"
  **[official]**: [Greenhouse API overview](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview)
- Lever Postings API is for a Lever account's own postings **[official]**:
  [lever/postings-api](https://github.com/lever/postings-api)
- Ashby: "if you host your own careers page, you can use this data to populate
  it" **[official]**: [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api)

### CareerOneStop / NLx
- "All new requests for Jobs APIs will be reviewed, approved and provided by
  the NLx Research Hub Governance Board" **[official]**:
  [registration](https://www.careeronestop.org/Developers/WebAPI/registration.aspx),
  [NLx request](https://nlxresearchhub.org/request-nlx-data)

### Adzuna
- Commercial use is allowed for a 14-day trial. After that it may not be used
  "to deliver any ongoing work … without written consent". Extracting data
  "for commercial reuse" is a breach. "Jobs by Adzuna" must appear. Limits are
  25/min, 250/day, 2,500/month **[official]**:
  [terms_of_service](https://developer.adzuna.com/docs/terms_of_service)

### Jooble
- Key through a request form (name, position, company website, phone). The
  jooble.org key covers U.S. listings **[official]**:
  [jooble.org/api/about](https://jooble.org/api/about),
  [Help Center](https://help.jooble.org/en/support/solutions/articles/60001448238-rest-api-documentation)
- 500 lifetime requests per key **[3rd-party]**:
  [publicapis.io](https://publicapis.io/jooble-api)

### TheirStack
- Free plan: 200 API credits a month, 1 credit per job returned. Paid from
  $49 a month. Account required **[official]**:
  [pricing](https://theirstack.com/en/pricing),
  [docs/pricing/plans](https://theirstack.com/en/docs/pricing/plans).
  ToS not found in excerpts.

### Remote OK (new)
- Link back to the Remote OK URL with a followed link and name Remote OK, or
  access is suspended. API delayed 24 h. Instant access costs $10k a month
  **[official]**: [remoteok.com/legal](https://remoteok.com/legal)

### Arbeitnow (new)
- Germany, EU and UK remote jobs. No U.S. focus **[official + 3rd-party]**:
  [arbeitnow.com/blog/job-board-api](https://www.arbeitnow.com/blog/job-board-api)

## B. Disqualified providers

| Provider | Why it fails |
|---|---|
| **Remotive** | Its terms forbid showing its jobs in exchange for a signup. NERO shows jobs only after login (`AuthGate`). The 24 h delay and 4-fetches-a-day limit also make it a poor fit for freshness. |
| **CareerOneStop / NLx** | Needs organization-level approval from the NLx Governance Board, so not self-serve. |
| **Adzuna** | Not $0 for ongoing commercial use (14-day trial, then a licence). Also forbids commercial reuse of extracted data. |
| **Jooble** | The key needs a company website, has a 500-request lifetime cap [3rd-party], and storage and AI terms are unknown. Himalayas, Remotive and Jobicy all name Jooble as a site their jobs must not reach. |
| **TheirStack** | Needs an account. Free tier is 200 jobs a month, then paid. ToS unread. |
| **Greenhouse / Lever / Ashby** | Not a general source. Each board belongs to one employer, for that employer's own careers site. Usable only with a named employer's permission. That is the existing Greenhouse adapter's stance and needs no new provider ticket. |
| **Arbeitnow** | No U.S. coverage. |
| **LinkedIn / Indeed / Google Jobs** | No permitted public job-search API (carried over from AJI-028). |

These are **UNVERIFIED — DO NOT INTEGRATE**. They aren't disqualified, but
they are unclear:

| Provider | What is unclear |
|---|---|
| **The Muse** | The license grant ("display through applications") conflicts with "not … copy … display … without prior written permission". No expiry date, so NERO could never set `expires_at`. |
| **Jobicy** | AJI-028 found a ban on showing jobs behind a login. This session could not confirm or rule it out. Keep it excluded until a primary-source read settles it. |
| **Remote OK** | Not an AJI-028 candidate. Storage, AI and login terms not seen. U.S. eligibility is free text, so it isn't explicit. |

## C. Viable candidates

Only two survive the hard filters ($0, no business account, U.S. jobs, no
scraping, no auto-apply, no known terms blocker). **Both remain UNVERIFIED —
DO NOT INTEGRATE.**

### 1. Himalayas: primary candidate

| Check | Result |
|---|---|
| $0 / no account / no business account | ✅ [official] |
| Official API, not scraping | ✅ The API and RSS are the provider's own sanctioned route. Scraping the site is forbidden. |
| No auto-apply | ✅ Returns `applicationLink`. NERO only links out. |
| AJI-028 adapter contract | ✅ Cursor pagination fits `fetch_bounded_pages()`. 60 req/min fits `HttpPolicy` throttling. |
| Canonical schema | ✅ title, company, description, employment type, salary, application link |
| Deduplication | ✅ Stable job URL / GUID for the fingerprint |
| Expiration | ✅ `expiryDate` [3rd-party only, needs primary confirmation] |
| U.S. coverage | ⚠️ Remote jobs only. Only postings whose `locationRestrictions` explicitly include the U.S. qualify. Worldwide postings are excluded under AJI-028. Volume unknown until measured. |
| Volume ceiling | ⚠️ 20 per page × 5 pages = at most 100 newest jobs per run, before the U.S. filter. Whether the search endpoint's country filter returns only explicitly U.S.-restricted jobs is unconfirmed. |
| Attribution | ✅ Fits `attribution.py` (`requires_link_back=True`, "Job via Himalayas" linked to the Himalayas URL) |
| Third-party re-submission | ✅ NERO re-publishes nowhere (no JSON-LD or sitemap) |
| **Storage** | ❓ Implied by "databases" and "backfill job boards". No explicit clause. No retention rule seen. |
| **AI processing** | ❓ Implied by "feed AI agents". No explicit clause. |
| **Display behind login** | ❓ Not addressed in any excerpt. Peers (Remotive, maybe Jobicy) forbid it, so this has to be answered, not assumed. |
| **General Terms vs. API page** | ❓ The Terms require Himalayas' consent to "copy, use … information". Whether the API page is that consent needs confirming. |

### 2. USAJOBS: secondary, narrow

| Check | Result |
|---|---|
| $0 / business account | ✅ Free, no business account. ⚠️ Needs a **free API key registered to NERO** (Project Owner decision; not created here). |
| U.S. coverage | ✅ All U.S., but **federal only**, so a niche supplement rather than a main source |
| Contract fit | ✅ Paged JSON, close date (expiry), schedule (full-time/part-time), remote/telework indicator |
| Storage | ✅ Internal storage and normalizing allowed, with credit and redirect to USAJOBS to apply [official excerpt] |
| **AI processing** | ❓ "No derivative works" and "displayed values must not be altered" may cover AI summaries or rewrites. Match scoring on unaltered data may be fine. Needs OPM in writing. |
| **Use scope** | ❓ "Explicit use of the requesting company … no other use without written approval". NERO's use would have to be stated on the registration form. |

## D. Recommended next action (Project Owner)

1. **Do not start AJI-030 yet.** No provider is contractually verified.
2. **Himalayas: close four questions on primary sources.** A human with a
   normal browser should read [himalayas.app/api](https://himalayas.app/api),
   [docs/remote-jobs-api](https://himalayas.app/docs/remote-jobs-api) and
   [himalayas.app/terms](https://himalayas.app/terms) in full. Ideally, also
   get written confirmation from Himalayas that NERO may:
   1. store job records (and for how long, including after `expiryDate`),
   2. show them to **logged-in users only**,
   3. run AI analysis on them (matching, requirement extraction, ATS), and
   4. treat the API page as the "consent" its general Terms require.

   Also confirm from the live docs that `expiryDate` exists, and how the search
   endpoint's country filter treats worldwide postings.
3. **If all four answers are yes**, Himalayas can be approved and AJI-030 can
   build one adapter on the AJI-028 foundation, unchanged: newest explicitly
   U.S.-eligible jobs, no keyword filter, `remote_type="remote"`,
   `requires_link_back=True`. A first `provider_scorecard` run should measure
   real U.S. volume before rollout.
4. **USAJOBS (optional, decide separately).** The Project Owner decides whether
   registering a free API key in NERO's name is acceptable. If so, ask OPM in
   writing whether AI analysis of unaltered announcements counts as a
   "derivative work". Integrate only on a written yes.
5. **Jobicy (optional).** One primary-source read would settle the login
   question. Only if it allows login-gated display should it be re-evaluated.
6. Everything in section B stays excluded.

**Approval decision requested:** none of the providers can be approved today.
The Project Owner is asked to authorize step 2 (verify Himalayas) and to decide
on step 4 (USAJOBS key registration).
