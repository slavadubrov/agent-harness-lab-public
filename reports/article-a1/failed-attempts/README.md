# Failed attempts (kept, not in the summary)

Runs that failed for an infrastructure reason, not a harness or model result. They are
kept as recorded and excluded from `../README.md`.

| Directory | What happened |
|---|---|
| `custom-a1-base-glm-5.3-flash-fireworks-429/` | 2026-09-24. Every model call to `z-ai/glm-5.3-flash` pinned to the Fireworks endpoint returned HTTP 429: "temporarily rate-limited upstream", `limit_source: upstream_provider_shared_pool` (OpenRouter's shared key pool for that provider). No model output, no tokens. The spec was moved to the Together endpoint (same price, same tool-choice support) and rerun into `../custom/a1-base-glm-5.3-flash/`. |
