# The runtime for candidates: Python 3.12 and the locked dependencies, and nothing else from
# this repository. The evaluator, the tasks and the reports are never copied in; the
# candidate's own files are mounted read-only at /candidate when an episode runs.
#   docker build -f evaluator/Dockerfile -t agent-harness-lab-candidate:py312 .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock /opt/lock/
# tau2 is a git dependency; git is removed again after the install.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && cd /opt/lock && UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-dev --no-install-project \
    && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /root/.cache
ENV PATH=/opt/venv/bin:$PATH
USER 65534:65534
