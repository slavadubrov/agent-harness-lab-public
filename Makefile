# agent-harness-lab. Needs uv. The offline targets (test, mine, show, failures, part4-regrade, part4-agreement,
# part4-compare) need no key. The a1-*, a2-* and part4-live targets call a model and need OPENROUTER_API_KEY
# (or OPEN_ROUTER_API_KEY) in .env or the environment. a1-* belongs to Part 2 of the series, a2-* to Part 3.
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
A2_SPECS := harness/spec/plain.yaml harness/spec/approval-agent.yaml harness/spec/workflows/refund-approval.yaml harness/spec/workflows/support-router.yaml harness/spec/workflows/support-code.yaml

.PHONY: help sync test fmt lint mine show failures a1-custom a1-custom-matrix a1-tau3 a1-tau3-matrix tau3-data report a2-custom a2-matrix a2-routes report-a2 part4-regrade part4-agreement part4-compare part4-live part5-report part5-regrade part5-show part5-loop part5-campaign

help:
	@echo "offline, no key:"
	@echo "make part4-regrade      grade the saved Part 4 runs, write reports/part-4/RESULTS.md and the plots"
	@echo "make failures DESIGN=5 [SPLIT=new] [LEVEL=judge]     which checks a design fails, task by task"
	@echo "make show DESIGN=5 TASK=policy-refund-window [RUN=1] [SPLIT=new] [LEVEL=judge]   one saved run"
	@echo "make part4-compare      BASE=3 CANDIDATE=5 (design numbers) [SPLIT=dev|new] [LEVEL=state|obligations|judge]"
	@echo "make part4-agreement    the judge and the held-reply check against labels"
	@echo "make mine               score the function in examples/your_harness.py on the 16 known tasks"
	@echo "make part5-regrade [CAMPAIGN=...]   regrade a Part 5 campaign using only public dependencies"
	@echo "make part5-report [CAMPAIGN=...]    grade a Part 5 campaign again, write its REPORT.md and trajectory.svg"
	@echo "make part5-show [CAMPAIGN=...] [CANDIDATE=003]   a campaign's ledger, or one candidate with its note and diff"
	@echo "                        CAMPAIGN defaults to reports/part-5/support; the saved sign-test campaign is"
	@echo "                        CAMPAIGN=reports/part-5/support-sign-test"
	@echo "make test | fmt | lint"
	@echo "paid, needs a key:"
	@echo "make a1-custom          Part 2: run the 12 support tasks with SPEC (default base.yaml)"
	@echo "make a1-custom-matrix   Part 2: run the 12 support tasks with every Part 2 spec"
	@echo "make a1-tau3            Part 2: run the τ³-bench retail subset with SPEC"
	@echo "make a1-tau3-matrix     Part 2: run the τ³-bench subset with base.yaml and plain.yaml"
	@echo "make report             rebuild reports/article-a1/README.md and versions.json"
	@echo "make a2-custom          Part 3: run the 16 support tasks with SPEC (agent or workflow)"
	@echo "make a2-matrix          Part 3: run the 16 support tasks with all five designs"
	@echo "make a2-routes          Part 3: score both routers' classifiers on 25 labelled requests"
	@echo "make report-a2          rebuild reports/article-a2/README.md"
	@echo "make part4-live         TRIALS=5 PART4_SPECS=\"<spec files>\" [SPLIT=dev|new]"
	@echo "paid, needs OPENAI_API_KEY:"
	@echo "make part5-loop         run or resume a campaign in CAMPAIGN (default reports/part-5/support)"

sync:
	$(UV) sync --frozen

test: sync
	$(UV) run --group loop pytest -q

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

# Part 4: the evaluator (evaluator/, built on harness-evals).
TRIALS ?= 5
SPLIT ?= dev
LEVEL ?= obligations
PART4_SPECS ?= $(A2_SPECS)

part4-regrade: sync
	$(UV) run python -m evaluator regrade

part4-agreement: sync
	$(UV) run python -m evaluator agreement

part4-compare: sync
	$(UV) run python -m evaluator compare $(BASE) $(CANDIDATE) --split $(SPLIT) --level $(LEVEL)

RUN ?= 1

failures: sync
	$(UV) run python -m evaluator failures $(DESIGN) --split $(SPLIT) --level $(LEVEL)

show: sync
	$(UV) run python -m evaluator show $(DESIGN) $(TASK) --run $(RUN) --split $(SPLIT) --level $(LEVEL)

mine: sync
	$(UV) run python -m examples.your_harness

part4-live: sync
	$(UV) run python -m evaluator live --trials $(TRIALS) --split $(SPLIT) $(PART4_SPECS)


# Part 5: the improvement loop on the workflow with no agent. The campaign decided with
# the sign test is in reports/part-5/support-sign-test. A campaign under the current rule
# (the Wilcoxon signed-rank test) goes to reports/part-5/support unless CAMPAIGN says otherwise.
CAMPAIGN ?= reports/part-5/support
CANDIDATES ?= 8
IMPROVER ?= gpt-6.2-sol
LOOP_TRIALS ?= dev=2,val=3,test=3
MAX_USD ?= 10

# The episode regrade uses the same evaluator as the full project and installs no runner.
REPLAY_EVALS ?= git+https://github.com/slavadubrov/harness-evals@d391e288d087671f94b09793d21dc5401e8b6296
part5-regrade: part5-campaign
	$(UV) run --no-project --with "$(REPLAY_EVALS)" python -m loop.regrade '$(CAMPAIGN)'

part5-report: part5-campaign sync
	$(UV) run --group loop harness-loop report loop.target:TARGET '$(CAMPAIGN)'

part5-show: part5-campaign sync
	$(UV) run --group loop harness-loop show - '$(CAMPAIGN)' $(CANDIDATE)

part5-campaign:
	@test -f '$(CAMPAIGN)/campaign.json' || { echo "No campaign in $(CAMPAIGN). For the saved sign-test campaign, add CAMPAIGN=reports/part-5/support-sign-test"; exit 1; }

# Needs OPENAI_API_KEY (default gpt-6.2-sol).
part5-loop: sync
	$(UV) run --group loop harness-loop run loop.target:TARGET $(CAMPAIGN) --max-candidates $(CANDIDATES) \
		--backend openai --max-usd $(MAX_USD) --model $(IMPROVER) --trials $(LOOP_TRIALS)
