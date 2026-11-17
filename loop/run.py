"""The lab's runner with the loop's validation and test tasks registered:

    python -m loop.run --spec <harness>/workflow.yaml --suite loop --tasks <ids> ...

Same arguments as ``python -m envs.custom.run``.
"""

import loop  # noqa: F401 - registers the suite "loop"
from envs.custom.run import main

if __name__ == "__main__":
    main()
