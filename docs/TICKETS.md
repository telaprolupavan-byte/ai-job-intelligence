# NERO Ticket Register

The authoritative list of ticket IDs used in this repository, reconstructed
from Git history (AJI-026). Historical IDs are recorded exactly as they were
used. Nothing here renumbers or renames a past ticket.

## Numbering rules (from AJI-026 onward)

1. **Claim before build.** Add a row here, marked `Claimed`, before creating
   the branch. The next ID is the highest one in this file plus one.
2. **Never reuse an ID.** An ID counts as used once it appears anywhere:
   a merged PR, an unmerged branch, or a commit message. This includes
   AJI-003 (never used, still skipped) and AJI-021 (see "Collisions").
3. **Put the ID in the branch name, the commit subject and the PR title.**
4. **Letter suffixes (`A`, `B`, `C`) are only for planned parts of one parent
   ticket.** Do not use decimal suffixes such as `.1` for new work. A fix to
   an already-merged ticket gets a new ID.
5. **No placeholder IDs.** `AUTH-XXX` below is historical and stays as-is.

## Register

"Merged" means the work is on `main`. It is a Git fact, not a statement
that the capability is product-complete. See `docs/ARCHITECTURE.md` for each
ticket's documented scope and open items.

| ID | Purpose | PR(s) → merge commit | Merged |
|---|---|---|---|
| AJI-001 | Authentication | no PR; direct merge `34e6cfc` | 2026-09-15 |
| AJI-002 | User dashboard (first version) | #1 → `402643c` | 2026-09-15 |
| AJI-003 | **Never used.** No commit, branch or doc references it. | — | — |
| AJI-004 | Resume validation. Its branch also added the app shell and deterministic resume analysis. | #2 → `34f05ae` | 2026-09-15 |
| AJI-005 | AI resume check | #3 → `b5c17fc`, #4 → `bc5b5ec`, #5 → `2a72ed2` | 2026-09-16 |
| AJI-006 | Job discovery engine | #6 → `108405a` | 2026-09-16 |
| AJI-007 | Job Match scoring | #7 → `16250cb` | 2026-09-16 |
| AJI-008 | Jobs intelligence UI | #8 → `9647954` | 2026-09-16 |
| AJI-009 | Architecture foundation: legacy models removed, canonical skills | #11 → `66fb13b` | 2026-09-17 |
| AJI-010 | Resume Intelligence. The commit carries no ID; the ID comes from `docs/ARCHITECTURE.md`. | #12 → `25c734d` | 2026-09-17 |
| AJI-011 | Hard Eligibility engine, then persistence and Jobs UI | #13 → `f38c68d`, #16 → `213f383` | 2026-09-17 |
| AJI-012 | Job Intelligence | #14 → `96c91a5` | 2026-09-17 |
| AJI-013 | ATS Alignment evidence engine | #17 → `21ddc2b` | 2026-09-17 |
| AJI-014 | Job Match reads Job Intelligence | #18 → `95cd0eb` | 2026-09-17 |
| AJI-015 | Gap Analysis: backend, then Jobs-page UI | #19 → `88bcee6`, #59 → `71f730b` | 2026-09-17, 2026-09-21 |
| AJI-016 | Application Tracking. The first commit carries no ID. | #25 → `39dcec5`, #27 → `fc8ea67` | 2026-09-18 |
| AJI-017 | Discovery run observability | #28 → `7944776` | 2026-09-18 |
| AJI-017.1 | Automatic discovery scheduler | #30 → `915f63e` | 2026-09-18 |
| AJI-018 | Provider Scorecard workflow and evaluation adapters | #29 → `2a673c3` | 2026-09-18 |
| AJI-018C | Offline ingestion for the provider comparison table. No AJI-018A/018B exist. | #29 → `2a673c3` | 2026-09-18 |
| AJI-019 | Resume-version selection for Match, ATS and Gap Analysis | #31 → `e3aed95` | 2026-09-18 |
| AJI-020 | ATS real scoring engine (four weighted components) | #33 → `7df40ac` | 2026-09-18 |
| AJI-020A | Requirement Intelligence model | #32 → `6a6e8ea` | 2026-09-18 |
| AJI-020B | Requirement Intelligence persistence and API | #32 → `6a6e8ea` | 2026-09-18 |
| AJI-020C | ATS Alignment reads Requirement Intelligence | #32 → `6a6e8ea` | 2026-09-18 |
| AJI-021 | Resume Improvement approval and recheck (+ #62, migration-head fix) | #61 → `dec12d9`, #62 → `9c1d595` | 2026-09-22 |
| AJI-022 | User job submission | #63 → `5bfbaf5` | 2026-09-22 |
| AJI-023 | Job Intelligence → Application Decision Workflow | #64 → `3c1bd6c` | 2026-09-23 |
| AJI-024 | Job Discovery product pipeline | #65 → `5ce6df0` | 2026-09-23 |
| AJI-025 | Job priority ordering | #66 → `bcd05af` | 2026-09-23 |
| AJI-023 (Job Search) | Job Search / Discovery foundation. **Duplicate ID**, see "Collisions". | #67 → `0a60744` | 2026-09-24 |
| AJI-026 | Production baseline: CI, Compose fix, AI timeouts, doc reconciliation, this register | Claimed | — |
| AJI-027 | General Resume Intelligence: job-independent General Resume Score, resume-level improvements, approve/reject, `Refined N` versions, recheck, readiness | Claimed | — |
| AJI-028 | Zero-Cost Job Discovery Foundation (foundation only): shared HTTP retry/backoff/throttle client, bounded pagination, `jobs.expires_at` + `active_jobs_filter()`, generic source attribution, adapter contract. No real provider enabled. Branch `claude/aji-028-zero-cost-discovery-foundation`. | Claimed | — |
| AJI-030 | Job Intelligence Development Dataset & End-to-End Pipeline: synthetic, clearly-labelled U.S. development dataset fed through the existing AJI-024/028 adapter pipeline (`JOB_DISCOVERY_PROVIDER=development_dataset`, test-mode only); one `NON_PRODUCTION_SOURCES` isolation set; end-to-end tests through search, details, Job Intelligence, Job Match and Application Tracking. No real provider. Branch `pavant/sweet-tesla-er8io8`. | Claimed | — |

### Work outside the AJI series

| ID | Purpose | PR(s) → merge commit |
|---|---|---|
| AUTH-XXX | Password recovery and reset. The placeholder number was never assigned. | #21 → `434f536` |
| UI-DASH-001 | Verified desktop Dashboard (Figma 33:3) | #24 → `22688ce` |
| — | Desktop Dashboard from Figma 33:3 (first pass, no ID in its commit) | #23 → `dc5dc62` |
| NERO-MOTION-001 | Landing-page motion easing | #53 → `912b0fa` |
| — | Figma design-system sync, phases 2–4 | #20 → `98c9091`, #22 → `2f61321` |
| — | Multi-resume, version-aware resume storage | #9 → `55b4d19`, #10 → `39edd2e` |
| — | Frontend UX modernization | #15 → `e39b878` |
| — | AI provider failure-coverage tests | #26 → `80a232b` |
| — | AI crash/timeout fixes (Resume Intelligence) | #34 → `3078e22`, #35 → `7482b05` |
| — | Branding and landing page | #36–#58 (excluding #53) |
| — | Stabilization pass (7 defects) | #60 → `75b762c` |
| — | Docker build context fix | #68 → `cedfaa8` |

## Collisions

1. **AJI-023: two different tickets, both merged.** The ID was first used by
   the Job Intelligence → Application Decision Workflow (#64). It was used
   again by Job Search / Discovery (#67). The repository tells them apart as
   "AJI-023" and "AJI-023 (Job Search)", as `docs/ARCHITECTURE.md` already
   does. **Product Owner confirmation of this numbering is pending.**
2. **AJI-021: one merged, one unmerged.** The merged AJI-021 is Resume
   Improvement (#61). The unmerged branch `claude/trusting-pascal-bs9sar`
   (commit `a45020d`, 2026-09-19) uses the same ID for a TheirStack job
   provider. No PR was ever opened for that branch.

## Unmerged branches

Recorded as found. Whether each branch is adopted, deleted or kept is a
Product Owner decision; nothing has been deleted.

| Branch | Content | Status |
|---|---|---|
| `claude/trusting-pascal-bs9sar` | TheirStack as a second discovery provider, labelled "AJI-021" | **Not merged.** No PR. Built before AJI-024's pipeline changes. Real provider selection is an open Product Owner decision. |
| `claude/nero-page-4-visual-f7l6k0` | 2 landing-page Page 4 layout commits (`ffc90fa`, `0132f04`) | **Not merged.** |
