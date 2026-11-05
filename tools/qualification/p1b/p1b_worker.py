"""Launch the production Arctic S index worker under ``python.exe -I -B`` (P1b condition B).

``IndexSupervisor`` starts the worker as ``python -m app.backend.embeddings.index_worker``. Under ``-I`` the checkout
is not on ``sys.path`` and ``-m`` cannot find ``app``; without ``-B`` the interpreter writes bytecode into the
digest-verified runtime. This shim only adds the checkout to ``sys.path`` and calls the worker's own ``main`` with
the supervisor's argument list, so the model load, batch loop, checkpoints, heartbeat, disk guard and resource policy
are the production code paths.

    python.exe -I -B p1b_worker.py <repo> <index_worker arguments...>
"""

import sys

sys.path.insert(0, sys.argv[1])

from app.backend.embeddings import index_worker  # noqa: E402

sys.exit(index_worker.main(sys.argv[2:]))
