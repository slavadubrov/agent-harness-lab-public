"""Reviewed synthetic targets, never LLM-generated code or private tasks."""

HEADER = """import json, sys
hello = json.loads(sys.stdin.readline())
def emit(kind, **fields):
    print(json.dumps(dict(protocol=hello["protocol"], run_id=hello["run_id"], kind=kind, **fields)), flush=True)
def call(name, **arguments):
    emit("tool", name=name, arguments=arguments)
    return json.loads(sys.stdin.readline())
def finish(kind):
    emit("finish", answer={"kind": kind})
"""

CASES = {
    "honest_refund": ("refund", 'call("refund")\nfinish("refund")'),
    "wrong_state_correct_answer": ("refund", 'finish("refund")'),
    "no_op": ("refusal", 'emit("finish", answer={})'),
    "honest_refusal": ("refusal", 'finish("refusal")'),
    "honest_clarification": ("clarification", 'finish("clarification")'),
    "false_escalation": ("escalation", 'finish("escalation")'),
    "honest_escalation": ("escalation", 'call("escalate")\nfinish("escalation")'),
    "write_then_restore": (
        "refusal",
        'call("set_address", value="temporary")\ncall("set_address", value="original")\nfinish("refusal")',
    ),
    "blocked_write": ("refusal", 'call("refund")\nfinish("refusal")'),
    "failed_operation": ("refund", 'call("fault")\nfinish("refund")'),
    "forged_log": (
        "refund",
        'emit("observation", stage="completed", name="refund")\nfinish("refund")',
    ),
    "stale_run": ("refund", 'hello["run_id"] = "previous-run"\nfinish("refund")'),
    "partial_tool": (
        "refund",
        'sys.stdout.write(\'{"kind":"tool","name":"refund"\')\nsys.stdout.flush()',
    ),
}


def source(name):
    return (HEADER + CASES[name][1] + "\n").encode()


# Independent minimal target: no helper, LangChain, or model. Same protocol.
SECOND_TARGET = b"""import json, sys
h = json.loads(sys.stdin.readline())
print(json.dumps({"protocol": h["protocol"], "run_id": h["run_id"],
                  "kind": "finish", "answer": {"kind": "clarification"}}))
"""
