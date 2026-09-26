# Article A1 results

One run per task; A4 adds repeats. Notes: [`NOTES.md`](NOTES.md).

Generated 2026-09-26T11:32:22Z by `scripts/report_a1.py`. Each run directory has `results.jsonl`, `run.json` (spec, versions, git commit) and `traces.jsonl` (every message, model call and tool call).

Tokens are provider-reported usage. Dollars are tokens × the pinned endpoint price (`versions.json`), Jev calls included. τ³ latency includes the user simulator.

## Summary (single run)

| env | spec | model | pass | pass rate | mean in tok | mean out tok | mean $/task | $/solved task | mean latency s | mean model calls | mean proposed tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|
| custom | a1-base | `openai/gpt-6-luna` | 12/12 | 100% | 6662 | 728 | $0.00076 | $0.00076 | 10.3 | 4.8 | 3.2 |
| custom | a1-base-glm-5.3-flash | `z-ai/glm-5.3-flash` | 12/12 | 100% | 10051 | 677 | $0.00176 | $0.00176 | 9.5 | 4.6 | 3.1 |
| custom | a1-base-mimo-v2.6-flash | `xiaomi/mimo-v2.6-flash` | 7/12 | 58% | 16940 | 1270 | $0.00095 | $0.00163 | 106.5 | 7.2 | 2.8 |
| custom | a1-plain | `openai/gpt-6-luna` | 12/12 | 100% | 3418 | 143 | $0.00035 | $0.00035 | 4.6 | 3.3 | 3.8 |
| tau3 | a1-base | `openai/gpt-6-luna` | 5/8 | 62% | 52430 | 2441 | $0.00219 | $0.00351 | 35.5 | 10.0 | 5.9 |
| tau3 | a1-plain | `openai/gpt-6-luna` | 6/8 | 75% | 43713 | 730 | $0.00115 | $0.00154 | 26.6 | 9.4 | 5.4 |

| env | spec | summarization calls | Jev classifier calls | writes blocked by Jev | run errors | unpriced calls | user-simulator $ (tau2) |
|---|---|---|---|---|---|---|---|
| custom | a1-base | 0 | 6 | 0 | 0 | 0 | n/a |
| custom | a1-base-glm-5.3-flash | 0 | 6 | 0 | 0 | 0 | n/a |
| custom | a1-base-mimo-v2.6-flash | 0 | 5 | 0 | 5 | 0 | n/a |
| custom | a1-plain | 0 | 0 | 0 | 0 | 0 | n/a |
| tau3 | a1-base | 0 | 0 | 0 | 0 | 0 | $0.00423 |
| tau3 | a1-plain | 0 | 0 | 0 | 0 | 0 | $0.00414 |

## custom / a1-base (`openai/gpt-6-luna`), single run

Files: `custom/a1-base/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | proposed tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | pass | one refund O-1001/4800 | 11552 | 1225 | $0.00116 | 17.7 | 7 | 5 |
| refund-partial-missing-item | pass | one refund O-1002/1500 | 9660 | 956 | $0.00098 | 13.0 | 6 | 4 |
| refund-outside-window | pass | no writes, as required | 7220 | 809 | $0.00083 | 11.4 | 5 | 4 |
| refund-over-agent-limit | pass | no writes, as required | 3865 | 549 | $0.00059 | 7.7 | 3 | 2 |
| refund-not-delivered | pass | no writes, as required | 5742 | 707 | $0.00074 | 9.4 | 4 | 3 |
| refund-already-refunded | pass | no writes, as required | 5451 | 630 | $0.00067 | 9.6 | 4 | 3 |
| refund-other-customers-order | pass | no writes, as required | 6969 | 946 | $0.00088 | 11.9 | 5 | 4 |
| address-update-shipping | pass | address 7 replaced as requested | 6612 | 705 | $0.00074 | 10.1 | 5 | 3 |
| address-missing-fields | pass | no writes, as required | 3747 | 482 | $0.00055 | 6.0 | 3 | 2 |
| address-suspended-account | pass | no writes, as required | 3691 | 444 | $0.00052 | 6.0 | 3 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 9168 | 652 | $0.00078 | 11.5 | 7 | 4 |
| preferences-one-unsupported | pass | preferences set: {'sms_notifications': 'on'} | 6268 | 633 | $0.00069 | 9.0 | 5 | 3 |

## custom / a1-base-glm-5.3-flash (`z-ai/glm-5.3-flash`), single run

Files: `custom/a1-base-glm-5.3-flash/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | proposed tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | pass | one refund O-1001/4800 | 14052 | 811 | $0.00230 | 11.5 | 6 | 4 |
| refund-partial-missing-item | pass | one refund O-1002/1500 | 14066 | 876 | $0.00233 | 11.7 | 6 | 4 |
| refund-outside-window | pass | no writes, as required | 9325 | 776 | $0.00179 | 10.1 | 4 | 3 |
| refund-over-agent-limit | pass | no writes, as required | 9105 | 736 | $0.00173 | 10.3 | 4 | 3 |
| refund-not-delivered | pass | no writes, as required | 9297 | 618 | $0.00170 | 8.3 | 4 | 3 |
| refund-already-refunded | pass | no writes, as required | 9042 | 681 | $0.00170 | 8.2 | 4 | 3 |
| refund-other-customers-order | pass | no writes, as required | 9085 | 822 | $0.00177 | 8.8 | 4 | 3 |
| address-update-shipping | pass | address 7 replaced as requested | 10224 | 607 | $0.00168 | 8.7 | 5 | 3 |
| address-missing-fields | pass | no writes, as required | 6452 | 417 | $0.00118 | 5.1 | 3 | 2 |
| address-suspended-account | pass | no writes, as required | 6417 | 412 | $0.00117 | 5.2 | 3 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 13701 | 645 | $0.00208 | 17.9 | 7 | 4 |
| preferences-one-unsupported | pass | preferences set: {'sms_notifications': 'on'} | 9847 | 721 | $0.00170 | 8.4 | 5 | 3 |

## custom / a1-base-mimo-v2.6-flash (`xiaomi/mimo-v2.6-flash`), single run

Files: `custom/a1-base-mimo-v2.6-flash/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | proposed tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: no NextStep tool call in the response \| last raw: finish_reason=tool_calls, tool_calls=['reply_to_user'], content=''); state check: one refund O-1001/4800 | 25905 | 1798 | $0.00132 | 12.1 | 10 | 4 |
| refund-partial-missing-item | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: 9 validation errors for NextStep missing_information   Input should be a valid list [type=list_type, input_value='Order O-1002 status, del...mount already refunded.', input_type=str]     For further information visit https://errors.pydantic. | 14129 | 905 | $0.00080 | 5.9 | 6 | 2 |
| refund-outside-window | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: 9 validation errors for NextStep missing_information   Input should be a valid list [type=list_type, input_value='Order O-1003 status, del... refunded, item amount.', input_type=str]     For further information visit https://errors.pydantic. | 11859 | 906 | $0.00073 | 122.6 | 5 | 2 |
| refund-over-agent-limit | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: 9 validation errors for NextStep missing_information   Input should be a valid list [type=list_type, input_value='Order O-2002 status, del...mount already refunded.', input_type=str]     For further information visit https://errors.pydantic. | 14011 | 1001 | $0.00087 | 6.5 | 6 | 2 |
| refund-not-delivered | pass | no writes, as required | 17537 | 1310 | $0.00090 | 104.1 | 7 | 3 |
| refund-already-refunded | pass | no writes, as required | 16981 | 1390 | $0.00098 | 122.2 | 7 | 3 |
| refund-other-customers-order | FAIL | run error (SGRParseError: No valid NextStep after 2 tries: no NextStep tool call in the response \| last raw: finish_reason=stop, tool_calls=[], content='{\n  "current_state": "Customer Ben Ortiz (A-101, ben.ortiz@example.com) requested a refund for order O-4001, but that order is not listed on his  | 17439 | 1734 | $0.00100 | 165.0 | 7 | 3 |
| address-update-shipping | pass | address 7 replaced as requested | 18942 | 1557 | $0.00097 | 144.5 | 8 | 3 |
| address-missing-fields | pass | no writes, as required | 11579 | 1029 | $0.00070 | 107.3 | 5 | 2 |
| address-suspended-account | pass | no writes, as required | 11190 | 900 | $0.00092 | 70.4 | 5 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 24668 | 1493 | $0.00135 | 172.2 | 11 | 4 |
| preferences-one-unsupported | pass | preferences set: {'sms_notifications': 'on'} | 19039 | 1213 | $0.00090 | 245.5 | 9 | 3 |

## custom / a1-plain (`openai/gpt-6-luna`), single run

Files: `custom/a1-plain/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | proposed tool calls |
|---|---|---|---|---|---|---|---|---|
| refund-full-damaged | pass | one refund O-1001/4800 | 5022 | 158 | $0.00038 | 4.9 | 4 | 5 |
| refund-partial-missing-item | pass | one refund O-1002/1500 | 4521 | 142 | $0.00043 | 4.7 | 4 | 4 |
| refund-outside-window | pass | no writes, as required | 3387 | 137 | $0.00034 | 4.4 | 3 | 4 |
| refund-over-agent-limit | pass | no writes, as required | 3182 | 148 | $0.00032 | 5.5 | 3 | 4 |
| refund-not-delivered | pass | no writes, as required | 5351 | 158 | $0.00054 | 6.3 | 5 | 5 |
| refund-already-refunded | pass | no writes, as required | 2980 | 144 | $0.00030 | 4.6 | 3 | 3 |
| refund-other-customers-order | pass | no writes, as required | 3167 | 148 | $0.00032 | 4.3 | 3 | 4 |
| address-update-shipping | pass | address 7 replaced as requested | 3539 | 138 | $0.00045 | 4.9 | 4 | 3 |
| address-missing-fields | pass | no writes, as required | 2467 | 103 | $0.00030 | 3.9 | 3 | 2 |
| address-suspended-account | pass | no writes, as required | 1621 | 84 | $0.00020 | 2.7 | 2 | 2 |
| preferences-two-changes | pass | preferences set: {'marketing_emails': 'off', 'language': 'de'} | 2897 | 169 | $0.00031 | 4.0 | 3 | 5 |
| preferences-one-unsupported | pass | preferences set: {'sms_notifications': 'on'} | 2881 | 192 | $0.00032 | 5.1 | 3 | 4 |

## tau3 / a1-base (`openai/gpt-6-luna`), single run

Files: `tau3/a1-base/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | proposed tool calls |
|---|---|---|---|---|---|---|---|---|
| 17 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 28330 | 1263 | $0.00114 | 23.1 | 6 | 3 |
| 12 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 49079 | 2151 | $0.00186 | 33.2 | 10 | 6 |
| 9 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 58574 | 3126 | $0.00308 | 45.7 | 11 | 5 |
| 5 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 63271 | 3116 | $0.00270 | 45.9 | 11 | 6 |
| 26 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 45985 | 2185 | $0.00191 | 29.2 | 9 | 6 |
| 18 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 57030 | 2659 | $0.00232 | 39.7 | 11 | 5 |
| 32 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 48560 | 2051 | $0.00179 | 29.6 | 10 | 7 |
| 27 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 68609 | 2976 | $0.00275 | 37.8 | 12 | 9 |

## tau3 / a1-plain (`openai/gpt-6-luna`), single run

Files: `tau3/a1-plain/`

| task | result | reason | in tok | out tok | $ | latency s | model calls | proposed tool calls |
|---|---|---|---|---|---|---|---|---|
| 17 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 23709 | 308 | $0.00094 | 13.5 | 6 | 3 |
| 12 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 33409 | 628 | $0.00084 | 20.2 | 8 | 5 |
| 9 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 50127 | 878 | $0.00135 | 28.6 | 10 | 6 |
| 26 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 39641 | 577 | $0.00097 | 21.9 | 9 | 6 |
| 18 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 51048 | 881 | $0.00129 | 30.3 | 11 | 5 |
| 5 | pass | reward=1.0; db_match=True; breakdown={'DB': 1.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 77136 | 1301 | $0.00189 | 45.4 | 14 | 7 |
| 27 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 42025 | 757 | $0.00119 | 31.2 | 9 | 6 |
| 32 | FAIL | reward=0.0; db_match=False; breakdown={'DB': 0.0, 'NL_ASSERTION': 1.0}; termination=user_stop | 32608 | 506 | $0.00076 | 21.7 | 8 | 5 |
