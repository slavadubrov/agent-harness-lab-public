# Article A1 results

**Every number in this directory is a single run** (one trial per task). Article A4 adds repeated trials and variance. Do not read differences between rows as effects without repeats.

Generated 2026-09-24T21:17:53Z by `scripts/report_a1.py` from the `results.jsonl` and `run.json` files next to this README. Raw traces (all messages and every model and tool call, failed runs included) are in each `traces.jsonl`.

Tokens are the provider-reported usage of each response (`usage_metadata`). Dollars are tokens × the per-token price of the pinned OpenRouter endpoint (see `versions.json`), including the Jev classifier calls. `openrouter_billed_cost` in the rows is OpenRouter's own billed cost for the chat calls and is a cross-check. τ³ latency is tau2's simulation duration and includes the user simulator.

## Summary (single run)

| env | spec | model | pass | pass rate | mean in tok | mean out tok | mean $/task | $/solved task | mean latency s | mean model calls | mean tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|
| custom | a1-base | `openai/gpt-6-luna` | 12/12 | 100% | 6373 | 684 | $0.00073 | $0.00073 | 11.9 | 4.6 | 3.1 |
| custom | a1-base-glm-5.3-flash | `z-ai/glm-5.3-flash` | 12/12 | 100% | 9887 | 708 | $0.00101 | $0.00101 | 9.7 | 4.5 | 3.0 |
| custom | a1-base-mimo-v2.6-flash | `xiaomi/mimo-v2.6-flash` | 7/12 | 58% | 15828 | 1225 | $0.00087 | $0.00149 | 18.6 | 6.6 | 2.5 |
| custom | a1-plain | `openai/gpt-6-luna` | 12/12 | 100% | 3446 | 138 | $0.00033 | $0.00033 | 5.8 | 3.3 | 3.9 |
| tau3 | a1-base | `openai/gpt-6-luna` | 6/8 | 75% | 62362 | 2693 | $0.00238 | $0.00318 | 59.0 | 11.2 | 6.4 |
| tau3 | a1-plain | `openai/gpt-6-luna` | 7/8 | 88% | 55594 | 825 | $0.00136 | $0.00156 | 38.9 | 11.4 | 6.2 |

| env | spec | summarization calls | Jev classifier calls | writes blocked by Jev | run errors | unpriced calls | user-simulator $ (tau2) |
|---|---|---|---|---|---|---|---|
| custom | a1-base | 0 | 6 | 0 | 0 | 0 | n/a |
| custom | a1-base-glm-5.3-flash | 0 | 6 | 0 | 0 | 0 | n/a |
| custom | a1-base-mimo-v2.6-flash | 0 | 4 | 0 | 5 | 0 | n/a |
| custom | a1-plain | 0 | 0 | 0 | 0 | 0 | n/a |
| tau3 | a1-base | 0 | 0 | 0 | 0 | 0 | $0.00453 |
| tau3 | a1-plain | 0 | 0 | 0 | 0 | 0 | $0.00471 |

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
| refund-full-damaged | pass | one refund O-1001/4800 | 14098 | 898 | $0.00126 | 12.5 | 6 | 4 |
| refund-partial-missing-item | pass | one refund O-1002/1500 | 14124 | 935 | $0.00128 | 13.2 | 6 | 4 |
| refund-outside-window | pass | no writes, as required | 9325 | 641 | $0.00096 | 8.3 | 4 | 3 |
| refund-over-agent-limit | pass | no writes, as required | 9156 | 1059 | $0.00114 | 12.3 | 4 | 3 |
| refund-not-delivered | pass | no writes, as required | 9330 | 718 | $0.00100 | 9.9 | 4 | 3 |
| refund-already-refunded | pass | no writes, as required | 9042 | 751 | $0.00098 | 10.3 | 4 | 3 |
| refund-other-customers-order | pass | no writes, as required | 9085 | 616 | $0.00093 | 7.6 | 4 | 3 |
| address-update-shipping | pass | address 7 replaced as requested | 10250 | 668 | $0.00096 | 8.8 | 5 | 3 |
| address-missing-fields | pass | no writes, as required | 4154 | 377 | $0.00058 | 4.7 | 2 | 1 |
| address-suspended-account | pass | no writes, as required | 6417 | 471 | $0.00072 | 8.4 | 3 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 13779 | 679 | $0.00134 | 11.5 | 7 | 4 |
| preferences-one-unsupported | pass | preferences set: {'sms_notifications': 'on'} | 9881 | 678 | $0.00095 | 8.7 | 5 | 3 |

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

## tau3 / a1-base (`openai/gpt-6-luna`), single run

Files: `tau3/a1-base/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | tool calls |
|---|---|---|---|---|---|---|---|---|
| 9 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 21850 | 1076 | $0.00086 | 30.6 | 5 | 1 |
| 17 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 28311 | 1283 | $0.00115 | 42.7 | 6 | 3 |
| 12 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 52012 | 2350 | $0.00204 | 47.8 | 10 | 6 |
| 5 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 75321 | 3576 | $0.00309 | 71.0 | 13 | 7 |
| 26 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 46535 | 2099 | $0.00191 | 39.0 | 9 | 7 |
| 18 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 64030 | 2664 | $0.00241 | 58.8 | 12 | 6 |
| 27 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 66822 | 3782 | $0.00308 | 64.3 | 12 | 9 |
| 32 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 144016 | 4716 | $0.00454 | 117.7 | 23 | 12 |

## tau3 / a1-plain (`openai/gpt-6-luna`), single run

Files: `tau3/a1-plain/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | tool calls |
|---|---|---|---|---|---|---|---|---|
| 17 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 28227 | 361 | $0.00065 | 18.3 | 7 | 4 |
| 12 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 38486 | 602 | $0.00088 | 29.1 | 9 | 5 |
| 9 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 72283 | 1076 | $0.00217 | 42.5 | 13 | 7 |
| 5 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 56419 | 945 | $0.00146 | 43.6 | 11 | 6 |
| 26 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 39678 | 565 | $0.00096 | 24.7 | 9 | 6 |
| 18 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 50607 | 836 | $0.00126 | 39.5 | 11 | 5 |
| 27 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 39645 | 691 | $0.00107 | 30.9 | 9 | 6 |
| 32 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 119405 | 1521 | $0.00246 | 82.9 | 22 | 11 |
