# Labels

Two samples of 30 replies, each labelled with the outcome of the reply (action, question,
refusal, handoff or answer) and whether it says a refund is still held. Each sample has
6 replies per expected outcome, from designs 1 to 6.

| File | Labelled | Used for |
| --- | --- | --- |
| `judge-check.jsonl` | before judge version 1 ran | finding version 1's errors |
| `judge-check-2.jsonl` | after version 2 was written and before it ran, without the replies of the first sample | measuring both versions |
| `judge-versions.jsonl` | | both versions' verdicts on all 2,160 saved replies, 1,989 of them non-empty |

The labels were written by Claude, not by a person, as the `labelled_by` field says.
Agreement with them is agreement with another model's labels, not with a customer or a
support lead. To review a label, edit `label_outcome` or `label_says_held` and rerun
`make part4-agreement`.

## How the judge was repaired

1. Version 1 ran, and agreed with 26 of the 30 labels of the first sample. The four
   disagreements were one mistake: it read "action" into a reply that only mentions a
   refund. Two were design 2's replies after an approved refund ("I submitted the \$350
   refund … it's on hold for supervisor approval"), and two were refusals saying that an
   order had already been refunded.
2. Version 2 added those cases to the outcome definitions (see `evaluator/README.md`).
3. The second sample was labelled before version 2 ran. On it, version 1 agreed with 27
   of 30, with the same mistake on three replies, and version 2 with all 30.
4. Without labels: among the 1,229 replies to tasks that must change nothing, from runs
   that changed nothing, version 1 called 65 an action and version 2 called 1.

`make part4-agreement` recomputes every number above from the files in this folder and
the saved runs. The verdicts in `judge-versions.jsonl` are the ones each version saved
next to the runs on 2026-10-15; the runs' own `judge.jsonl` files hold version 2.
