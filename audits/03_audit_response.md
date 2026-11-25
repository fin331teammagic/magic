# Response to the Checkpoint 2 instructor audit

Team Magic · written 2026-11-24 · audit: `audits/02_instructor_audit.md`
(issue #13)

**Late, and why.** Issue #13 asked for this file by Saturday, November 21.
The fixes themselves were made on time. A2 and A3 were added on 2026-11-19,
A4 and A5 by the Checkpoint 3 response. But we never wrote the response in
this file. We answered the CP2 findings that were still open inside
`audits/05_audit_response.md` instead. This file collects the evidence in
one place. Every commit named here is on `main`.

## Summary

| Finding | Response | Where |
|---|---|---|
| A1 · `main` doesn't contain all of your work | **Fixed.** Every CP2 branch the audit lists is on `main` | see below; CP3 B4 in `05_audit_response.md` |
| A2 · No `specs_tried.md` | **Fixed** | `e775058` (2026-11-19); frozen by Amendment 1 (2026-11-22) |
| A3 · One cohort, overlapping windows | **Fixed.** Inference is pre-specified and was applied in runs 12–19 | `specs_tried.md` §5, "Inference for correlated holdout errors (A3)" |
| A4 · Live pulls drift; versions not pinned | Pins **fixed**. Drift is **disclosed** and contained | `ba726b7`, `971e1a3`; `05_audit_response.md` |
| A5 · Forward-window off-by-one | **Fixed** | `5320e8d`; `05_audit_response.md` |

## A1 · `main` contains the work

Checked on 2026-11-24. The work in each PR the audit lists is on `main`:

| Audit item | Branch | On `main`? |
|---|---|---|
| #5, Abby's transcript export | `abby-pead-v0` | Yes |
| #9, Michelle's dataset | `michelle-final-dataset` | Yes |
| #10, Gus's Q2 2026 events and CAR[0,1] | `gus-event-study-data` | Yes |
| #8, Cammy's `ANALYSIS_PLAN.md` | `cammymarks-analysis-plan` | Yes (see below) |
| #11, team integration | `checkpoint-2/team-integration` | Yes, PR #11 (`648ae65`) |

- **The one exception:** commit `c7e3f7c` on `cammymarks-analysis-plan`
  (2026-11-23) is not on `main`. It is an earlier draft of the Run 3
  section of `ANALYSIS_PLAN.md`. `main` has a later, more accurate version
  of that same section, so nothing is missing.
- **How we keep it that way:** since Checkpoint 3, all work reaches `main`
  through pull requests. Recent examples are #28 and #29.

## A2 · `specs_tried.md`

- **Added:** in `e775058` (2026-11-19).
- **Frozen:** §1–7 were frozen by Amendment 1 (2026-11-22), before any
  real-data fit.
- **Run log:** §8 records every fit, scoring run and evaluation, in order,
  including the exploratory ones (runs 16 and 20).
- **Later changes:** each one is a dated amendment (Amendments 1–6).

## A3 · Inference for one cohort with a chronological split

`specs_tried.md` §5 pre-specifies two checks for each holdout comparison:
- a week-block bootstrap of ΔMSE (calendar weeks of day 0, 2,000 draws,
  seed 331);
- a shuffled-score placebo (1,000 draws).

It also discloses the window overlap. CAR[0,1] windows are two sessions
long, so training and holdout outcomes barely overlap. The 20-session
secondary outcome overlaps heavily, and we say so next to its table.

Both checks were applied in runs 12–19. Because the transcript data ends on
2026-08-07, the holdout covers only 2 weeks. The bootstrap therefore
resamples only 2 blocks, and we report the placebo share as the steadier
evidence (`specs_tried.md` §8).

## A4 and A5

Answered in full in `audits/05_audit_response.md`, sections "CP2 A4" and
"CP2 A5".
