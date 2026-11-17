"""Part 5: an improvement loop on the support assistant with no agent.

Importing this package registers the loop's validation and test tasks with the
environment, as the suite ``loop``, next to the 48 tasks of Parts 2 to 4.
"""

from envs.custom import tasks as _env
from loop.tasks import TEST_TASKS, VAL_TASKS

_env.SUITES["loop"] = _env.TASKS + _env.APPROVAL_TASKS + _env.OOT_TASKS + VAL_TASKS + TEST_TASKS
_env.TASKS_BY_ID.update({t.id: t for t in VAL_TASKS + TEST_TASKS})
