# Clean-clone check (kept, not in the summary)

On 2026-09-24, commit `9517977` was cloned into an empty directory with only `.env`
(the OpenRouter key) added, and `make test && make a1-custom && make a1-tau3` ran.
This checks that the repository runs from a clean clone. It is also a second single run
of a1-base, so it is kept here as recorded (`run.json` shows `dirty: false`).

| env | spec | pass | failed tasks | total $ |
|---|---|---|---|---|
| custom | a1-base | 12/12 | none | $0.00794 |
| tau3 | a1-base | 6/8 | 9, 17 | $0.02043 |

The committed τ³ a1-base run (`../tau3/a1-base/`) also passed 6/8, but it failed tasks 9
and 26. Tasks 17 and 26 changed result between two runs of the same harness, model,
tasks and user-simulator model. Two runs cannot estimate variance.
