from __future__ import annotations

import sys

if "--run-digest" in sys.argv:
    sys.argv.remove("--run-digest")
    from task_digest.bootstrap import resolve_runtime_dir

    runtime_dir, _ = resolve_runtime_dir()
    import os

    os.chdir(runtime_dir)
    from task_digest.main import main
else:
    from task_digest.app import main

raise SystemExit(main())
