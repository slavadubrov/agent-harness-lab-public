# agent-harness-lab — Part 1 (a1-*) and Part 2 (a2-*) targets. Needs uv and OPENROUTER_API_KEY (or OPEN_ROUTER_API_KEY) in .env or the environment.
SHELL := /bin/bash
UV ?= uv
SPEC ?= harness/spec/base.yaml
# The spec path goes in through sys.argv, never into the Python source.
SPEC_PY = $(UV) run --quiet python -c "import sys; from harness.spec import load_spec; s = load_spec(sys.argv[1]); print($(1))" '$(SPEC)'
SPEC_NAME = $(shell $(call SPEC_PY,s.name))

TAU2_COMMIT := b7ea9074c1cba482b30687fecdb5c8425fd6f619
TAU2_DIR := .cache/tau2-bench
export TAU2_DATA_DIR := $(CURDIR)/$(TAU2_DIR)/data
# User simulator: a small model through OpenRouter (litellm), pinned to the OpenAI endpoint.
USER_LLM ?= openrouter/openai/gpt-6-luna
USER_LLM_ARGS ?= {"extra_body":{"provider":{"order":["openai"],"allow_fallbacks":false}}}
TAU3_CONCURRENCY ?= 4

CUSTOM_SPECS := harness/spec/base.yaml harness/spec/plain.yaml harness/spec/glm-5.3-flash.yaml harness/spec/mimo-v2.6-flash.yaml
A2_SPECS := harness/spec/plain.yaml harness/spec/approval-agent.yaml harness/spec/workflows/refund-approval.yaml harness/spec/workflows/support-router.yaml

.PHONY: help sync test fmt lint a1-custom a1-custom-matrix a1-tau3 a1-tau3-matrix tau3-data report a2-custom a2-matrix a2-routes report-a2

help:
	@echo "make a1-custom          run the custom environment dev set with SPEC (default base.yaml)"
	@echo "make a1-custom-matrix   run the custom dev set with every A1 spec"
	@echo "make a1-tau3            run the τ³ retail subset with SPEC"
	@echo "make a1-tau3-matrix     run the τ³ subset with base.yaml and plain.yaml"
	@echo "make report             rebuild reports/article-a1/README.md and versions.json"
	@echo "make a2-custom          run the Part 2 task set (16) with SPEC (agent or workflow)"
	@echo "make a2-matrix          run the Part 2 task set with plain, approval agent, workflow, router"
	@echo "make a2-routes          score both routers' classifiers on 25 labelled requests"
	@echo "make report-a2          rebuild reports/article-a2/README.md"
	@echo "make test | fmt | lint"

sync:
	$(UV) sync --frozen

test: sync
	$(UV) run pytest -q

fmt:
	$(UV) run ruff check --select I --fix .
	$(UV) run ruff format .

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

a1-custom: sync
	$(UV) run python -m envs.custom.run --suite a1 --spec $(SPEC)
	$(UV) run python scripts/report_a1.py

a1-custom-matrix: sync
	@for s in $(CUSTOM_SPECS); do $(UV) run python -m envs.custom.run --suite a1 --spec $$s || exit 1; done
	$(UV) run python scripts/report_a1.py

a2-custom: sync
	$(UV) run python -m envs.custom.run --suite a2 --spec $(SPEC)
	$(UV) run python scripts/report_a2.py

a2-matrix: sync
	@for s in $(A2_SPECS); do $(UV) run python -m envs.custom.run --suite a2 --spec $$s || exit 1; done
	$(UV) run python scripts/report_a2.py

a2-routes: sync
	$(UV) run python -m envs.custom.route_eval --spec harness/spec/workflows/support-router.yaml
	$(UV) run python -m envs.custom.route_eval --spec harness/spec/workflows/support-router-clarify.yaml
	$(UV) run python scripts/report_a2.py

report-a2:
	$(UV) run python scripts/report_a2.py

# Sparse checkout of the tau2 data the retail runs need, at the pinned commit.
tau3-data:
	@if [ "$$(git -C $(TAU2_DIR) rev-parse HEAD 2>/dev/null)" != "$(TAU2_COMMIT)" ]; then \
	  rm -rf $(TAU2_DIR) && git init -q $(TAU2_DIR) && \
	  git -C $(TAU2_DIR) remote add origin https://github.com/sierra-research/tau2-bench.git && \
	  git -C $(TAU2_DIR) sparse-checkout set --no-cone data/tau2/domains/retail data/tau2/user_simulator && \
	  git -C $(TAU2_DIR) fetch -q --depth 1 --filter=blob:none origin $(TAU2_COMMIT) && \
	  git -C $(TAU2_DIR) checkout -q FETCH_HEAD; \
	fi
	@echo "tau2 data at $(TAU2_DIR) ($$(git -C $(TAU2_DIR) rev-parse --short HEAD))"

a1-tau3: sync tau3-data
	$(eval NAME := $(SPEC_NAME))
	$(if $(NAME),,$(error could not read the spec name from $(SPEC)))
	$(eval IDS := $(shell $(UV) run --quiet python -m envs.tau3.subset))
	$(eval SAVE := a1-retail-$(NAME))
	$(eval TRACES := build/tau3/$(NAME)/traces.jsonl)
	rm -rf "$(TAU2_DATA_DIR)/simulations/$(SAVE)" "build/tau3/$(NAME)"
	$(UV) run python -m envs.tau3.cli run --domain retail --agent langchain_harness \
	  --agent-llm "$$($(call SPEC_PY,s.model.id))" \
	  --agent-llm-args '{"spec":"$(SPEC)","trace_path":"$(TRACES)"}' \
	  --user-llm $(USER_LLM) --user-llm-args '$(USER_LLM_ARGS)' \
	  --task-split-name test --task-ids $(IDS) --num-trials 1 \
	  --max-concurrency $(TAU3_CONCURRENCY) --max-steps 100 --save-to $(SAVE) --log-level ERROR
	$(UV) run python -m envs.tau3.collect --save-to $(SAVE) --traces $(TRACES) --spec $(SPEC) \
	  --out reports/article-a1/tau3/$(NAME) --user-llm $(USER_LLM) \
	  --command "tau2 run --domain retail --agent langchain_harness --task-split-name test --task-ids $(IDS) --num-trials 1 --user-llm $(USER_LLM)"
	$(UV) run python scripts/report_a1.py

a1-tau3-matrix:
	$(MAKE) a1-tau3 SPEC=harness/spec/base.yaml
	$(MAKE) a1-tau3 SPEC=harness/spec/plain.yaml

report:
	$(UV) run python scripts/report_a1.py
