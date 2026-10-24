# External observation prototype

This offline prototype separates **what a task checks** from **who supplies its
evidence**. It evaluates reviewed, scripted Python targets through JSONL without
importing LangChain, LangGraph, or target harness code. It does not yet isolate
hostile candidate code or adapt the existing LangChain/SQLite and tau3 runners.

**Do not use this runner for untrusted code.** `-I`, an empty environment, a temporary
working directory and a subprocess are not a sandbox. The process has the caller's
filesystem and network privileges. Every result says `containment_verified: false`
and `eligible_for_adoption: false`, even when its task obligations pass.

## Run without models or credentials

From the repository root, with Python 3.12:

```bash
python3 -m evaluator --trusted-fixtures --output /tmp/observations.json
# Or use the pinned project environment:
uv run --frozen python -m evaluator --trusted-fixtures --output /tmp/observations.json
uv run --frozen pytest -q tests/test_external_evaluator.py
```

Choose a fresh output filename; the CLI refuses to overwrite an earlier report.
The 14 runs include valid refund/refusal/clarification/escalation, a second minimal
non-LangChain target, false completion, a no-op, a transient write, blocked and
failed operations, a forged event, a stale run ID and a partial tool message.
These are public development fixtures, not holdouts, live agent results, or a
measurement of exploit prevalence. Tests also cover time/output limits and a
nonzero exit after a final answer.

## Protocol `harness-observation/1`

The runner captures one candidate source file (up to 64 KiB), hashes those bytes,
and executes that copy. A fresh run ID binds messages to this invocation. It sends:

```json
{"protocol":"harness-observation/1","run_id":"fresh-id","task":{"request":"refund"}}
```

The target may send only `tool` or `finish` messages, one complete JSON object per
line. A tool proposal receives one JSON response before the next proposal:

```json
{"protocol":"harness-observation/1","run_id":"fresh-id","kind":"tool","name":"refund","arguments":{}}
{"protocol":"harness-observation/1","run_id":"fresh-id","kind":"finish","answer":{"kind":"refund"}}
```

Candidate-provided verdicts, events and guard labels are rejected. A partial line
never reaches dispatch. The runner bounds wall time, message count and stdout;
these are fixture safeguards, not OS-level memory/CPU/process containment.

`Environment` is a tiny in-memory service adapter, **not** the existing support
SQLite environment. The service owns state, deterministic authorization and event
recording. Each event identifies source, trust scope, sequence, run and monotonic
time. The action path records proposed → semantic decision status → authorization
→ attempted → completed/failed. Blocked calls stop before attempted execution.
No semantic classifier runs: its status is `not_invoked`, not a successful guard.

Final answers have a deliberately tiny structured vocabulary. Equality checks
here do not validate free-text customer replies. Task checks cover the answer,
final state, required effects, forbidden intermediate changes, blocked attempts,
failed operations and protocol completeness. Service permissions deliberately
allow address writes so the write-then-restore fixture can expose a task violation.
An allowed operation is not automatically a correct one.

## Result and reuse contract

The report retains every fixture, including rejected and partial runs. Each result
contains candidate/task/evaluator digests, Python version, run ID, public split and
exposure, before/after state, service events, answer, component checks, error,
process exit code, duration and a scoped model-cost subtotal. There are no provider
calls in these reviewed fixtures. The runner cannot measure out-of-protocol child
activity; zero here must not become a live-run cost claim.

`verdict` grades obligations; `termination` describes execution. Neither authorizes
adoption. The CLI is the initial process interface for an external controller or
audit client; there is no API accepting a supplied result JSON as trusted proof.
Hashes bind identities; they do not authenticate who executed them. Store original
reports outside the candidate's access and rerun when receiving untrusted reports.

A child using an old run ID fails the protocol. Changing source changes its hash,
even for an added comment. This is artifact binding, not a signed receipt or a
complete stale-adoption implementation. Controller-side storage and policy remain
necessary. The exact executed source is reconstructible from `fixtures.py` at the
report's source revision; compare its digest before using a stored report.

## Integration and security requirements still open

There is deliberately no silent fallback from a sandbox mode to local mode.
A supported hostile-code profile must be implemented and tested before enabling
adoption or claiming that the harness cannot touch its evaluator:

| Boundary | Required implementation and acceptance probe |
|---|---|
| Filesystem / identity | Separate nonprivileged identity; candidate-only read-only artifact mount, bounded scratch; grader, holdouts, host home, credentials and container socket absent. Test reads and writes against protected canaries and run an honest target. |
| Network / tools | Default-deny egress; evaluator brokers only approved model/tool requests. Test direct TCP, DNS and alternate endpoints, not just a monkey-patched client. |
| Processes / budgets | No host PID namespace or attach capability; drop capabilities, no privilege escalation, CPU/memory/PID/wall/output limits; test fork, timeout and memory exhaustion. |
| Observations | Service-owned state/action capture; provider requests captured at the last supported boundary; reject unsupported provider built-ins and external effects. |
| Provenance | Freeze complete candidate dependencies/config/task/evaluator/image versions; runner-owned result store; bind acceptance to exact versions and run. |

A container invocation alone does not establish these properties. No container
profile or direct-egress/tampered-grader acceptance test is delivered here.

The existing custom runner executes tools and callbacks in the target process.
The tau3 adapter uses `interrupt_before=["tools"]`, returns tool proposals to tau3,
and resumes with its tool results. Its tool middleware (including Jev) is bypassed;
a future adapter must record `bypassed`, never `captured` or “guard passed”. The
prototype's `not_invoked` is **not** evidence from a tau3 integration test.

For captured semantic decisions retain approved/synthetic context, question/schema
version, model and endpoint, only actually returned probabilities/confidence,
threshold, application decision, latency, unknown cost and failures. Keep these
predictions separate from independently authored expected labels and effects.
Current `UsageRecorder` retains normalized cache-read token counts, model IDs and
cost fields; it does not preserve full final model requests or Jev decision bodies.

The model-boundary extension must capture final observable request and response,
source roles, tool/prompt versions, transformations and usage availability. Record
steering enqueue source/order/drain separately; key child transcripts by spawning
call. Keep raw capture separate from redacted views and record redaction itself.
Test dropped constraints, wrong source roles, silent truncation, changed schemas
and partial streams using a recording fake through the real assembly path. These
checks are not implemented by this prototype. Replaying a captured request is an
experiment, not deterministic reproduction of provider state or full execution.
