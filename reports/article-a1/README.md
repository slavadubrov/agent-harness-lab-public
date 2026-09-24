# Article A1 results

**Every number in this directory is a single run** (one trial per task). Article A4 adds repeated trials and variance. Do not read differences between rows as effects without repeats.

Generated 2026-09-24T21:06:53Z by `scripts/report_a1.py` from the `results.jsonl` and `run.json` files next to this README. Raw traces (all messages and every model and tool call, failed runs included) are in each `traces.jsonl`.

Tokens are the provider-reported usage of each response (`usage_metadata`). Dollars are tokens × the per-token price of the pinned OpenRouter endpoint (see `versions.json`), including the Jev classifier calls. `openrouter_billed_cost` in the rows is OpenRouter's own billed cost for the chat calls and is a cross-check. τ³ latency is tau2's simulation duration and includes the user simulator.

## Summary (single run)

| env | spec | model | pass | pass rate | mean in tok | mean out tok | mean $/task | $/solved task | mean latency s | mean model calls | mean tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|
| custom | a1-base | `openai/gpt-6-luna` | 12/12 | 100% | 6373 | 684 | $0.00073 | $0.00073 | 11.9 | 4.6 | 3.1 |
| custom | a1-base-glm-5.3-flash | `z-ai/glm-5.3-flash` | 0/12 | 0% | 0 | 0 | $0.00000 | n/a | 0.4 | 1.0 | 0.0 |
| custom | a1-base-mimo-v2.6-flash | `xiaomi/mimo-v2.6-flash` | 7/12 | 58% | 15828 | 1225 | $0.00087 | $0.00149 | 18.6 | 6.6 | 2.5 |
| custom | a1-plain | `openai/gpt-6-luna` | 12/12 | 100% | 3446 | 138 | $0.00033 | $0.00033 | 5.8 | 3.3 | 3.9 |

| env | spec | summarization calls | Jev classifier calls | writes blocked by Jev | run errors | unpriced calls | user-simulator $ (tau2) |
|---|---|---|---|---|---|---|---|
| custom | a1-base | 0 | 6 | 0 | 0 | 0 | n/a |
| custom | a1-base-glm-5.3-flash | 0 | 0 | 0 | 12 | 12 | n/a |
| custom | a1-base-mimo-v2.6-flash | 0 | 4 | 0 | 5 | 0 | n/a |
| custom | a1-plain | 0 | 0 | 0 | 0 | 0 | n/a |

## custom / a1-base (`openai/gpt-6-luna`), single run

Files: `custom/a1-base/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | pass | one refund O-1001/4800 | 9608 | 912 | $0.00095 | 14.5 | 6 | 4 |
| refund-partial-missing-item | pass | one refund O-1002/1500 | 9630 | 831 | $0.00092 | 13.8 | 6 | 4 |
| refund-outside-window | pass | no writes, as required | 5762 | 691 | $0.00074 | 11.5 | 4 | 3 |
| refund-over-agent-limit | pass | no writes, as required | 3815 | 468 | $0.00055 | 9.0 | 3 | 2 |
| refund-not-delivered | pass | no writes, as required | 5742 | 743 | $0.00076 | 11.5 | 4 | 3 |
| refund-already-refunded | pass | no writes, as required | 5486 | 711 | $0.00071 | 10.5 | 4 | 3 |
| refund-other-customers-order | pass | no writes, as required | 6969 | 864 | $0.00084 | 19.8 | 5 | 4 |
| address-update-shipping | pass | address 7 replaced as requested | 6618 | 644 | $0.00071 | 9.9 | 5 | 3 |
| address-missing-fields | pass | no writes, as required | 3699 | 528 | $0.00057 | 7.4 | 3 | 2 |
| address-suspended-account | pass | no writes, as required | 3707 | 466 | $0.00053 | 7.5 | 3 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 9182 | 702 | $0.00080 | 15.0 | 7 | 4 |
| preferences-one-unsupported | pass | preferences set: {'sms_notifications': 'on'} | 6262 | 648 | $0.00069 | 13.0 | 5 | 3 |

## custom / a1-base-glm-5.3-flash (`z-ai/glm-5.3-flash`), single run

Files: `custom/a1-base-glm-5.3-flash/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: expected 1 new refund, found 0: [] | 0 | 0 | $0.00000 | 0.5 | 1 | 0 |
| refund-partial-missing-item | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: expected 1 new refund, found 0: [] | 0 | 0 | $0.00000 | 0.5 | 1 | 0 |
| refund-outside-window | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: no writes, as required | 0 | 0 | $0.00000 | 0.5 | 1 | 0 |
| refund-over-agent-limit | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: no writes, as required | 0 | 0 | $0.00000 | 0.5 | 1 | 0 |
| refund-not-delivered | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: no writes, as required | 0 | 0 | $0.00000 | 0.5 | 1 | 0 |
| refund-already-refunded | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: no writes, as required | 0 | 0 | $0.00000 | 0.3 | 1 | 0 |
| refund-other-customers-order | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: no writes, as required | 0 | 0 | $0.00000 | 0.3 | 1 | 0 |
| address-update-shipping | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: expected exactly 1 changed address: no changes | 0 | 0 | $0.00000 | 0.3 | 1 | 0 |
| address-missing-fields | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: no writes, as required | 0 | 0 | $0.00000 | 0.3 | 1 | 0 |
| address-suspended-account | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: no writes, as required | 0 | 0 | $0.00000 | 0.5 | 1 | 0 |
| preferences-two-changes | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: expected preference writes {('A-103', 'marketing_emails'): 'off', ('A-103', 'language'): 'de'}, got {} | 0 | 0 | $0.00000 | 0.3 | 1 | 0 |
| preferences-one-unsupported | FAIL | run error (TooManyRequestsResponseError: Provider returned error); state check: expected preference writes {('A-101', 'sms_notifications'): 'on'}, got {} | 0 | 0 | $0.00000 | 0.3 | 1 | 0 |

## custom / a1-base-mimo-v2.6-flash (`xiaomi/mimo-v2.6-flash`), single run

Files: `custom/a1-base-mimo-v2.6-flash/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: no NextStep tool call in the response); state check: expected 1 new refund, found 0: [] | 13810 | 1123 | $0.00055 | 15.9 | 6 | 2 |
| refund-partial-missing-item | pass | one refund O-1002/1500 | 28422 | 2011 | $0.00141 | 23.1 | 11 | 4 |
| refund-outside-window | pass | no writes, as required | 20534 | 1439 | $0.00106 | 17.0 | 8 | 3 |
| refund-over-agent-limit | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: no NextStep tool call in the response); state check: no writes, as required | 6453 | 516 | $0.00049 | 6.9 | 3 | 1 |
| refund-not-delivered | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: Function NextStep arguments:  {"current_state": "Identified account A-100 for ana.novak@example.com. Refund policy reviewed; order details for O-1004 not yet retrieved.", "policy_check": "REFUNDS: allowed only for delivered orders within 30  | 11690 | 877 | $0.00094 | 11.9 | 5 | 2 |
| refund-already-refunded | pass | no writes, as required | 17267 | 1409 | $0.00090 | 45.6 | 7 | 3 |
| refund-other-customers-order | pass | no writes, as required | 20054 | 1983 | $0.00126 | 22.8 | 8 | 3 |
| address-update-shipping | pass | address 7 replaced as requested | 15599 | 1068 | $0.00093 | 13.5 | 7 | 3 |
| address-missing-fields | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: no NextStep tool call in the response); state check: no writes, as required | 11454 | 976 | $0.00041 | 11.8 | 5 | 2 |
| address-suspended-account | pass | no writes, as required | 11266 | 852 | $0.00064 | 9.6 | 5 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 27014 | 2012 | $0.00141 | 24.0 | 11 | 4 |
| preferences-one-unsupported | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: 9 validation errors for NextStep missing_information   Input should be a valid list [type=list_type, input_value='Whether dark mode is a s...rted account preference', input_type=str]     For further information visit https://errors.pydantic. | 6373 | 433 | $0.00046 | 21.6 | 3 | 1 |

## custom / a1-plain (`openai/gpt-6-luna`), single run

Files: `custom/a1-plain/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | pass | one refund O-1001/4800 | 5020 | 156 | $0.00020 | 6.1 | 4 | 5 |
| refund-partial-missing-item | pass | one refund O-1002/1500 | 5039 | 157 | $0.00038 | 5.9 | 4 | 5 |
| refund-outside-window | pass | no writes, as required | 3387 | 136 | $0.00034 | 5.4 | 3 | 4 |
| refund-over-agent-limit | pass | no writes, as required | 3182 | 150 | $0.00032 | 5.4 | 3 | 4 |
| refund-not-delivered | pass | no writes, as required | 3372 | 139 | $0.00034 | 5.0 | 3 | 4 |
| refund-already-refunded | pass | no writes, as required | 3116 | 119 | $0.00030 | 5.0 | 3 | 4 |
| refund-other-customers-order | pass | no writes, as required | 3167 | 136 | $0.00032 | 6.0 | 3 | 4 |
| address-update-shipping | pass | address 7 replaced as requested | 4599 | 155 | $0.00047 | 8.7 | 5 | 4 |
| address-missing-fields | pass | no writes, as required | 1637 | 111 | $0.00022 | 3.6 | 2 | 2 |
| address-suspended-account | pass | no writes, as required | 2427 | 72 | $0.00028 | 6.1 | 3 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 2897 | 169 | $0.00031 | 4.8 | 3 | 5 |
| preferences-one-unsupported | pass | preferences set: {'sms_notifications': 'on'} | 3507 | 158 | $0.00046 | 7.7 | 4 | 4 |
