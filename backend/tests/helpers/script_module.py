"""Import a standalone `scripts/*.py` file as a module, the way importlib documents it.

REUSE-AUDIT: considered tests/helpers/api_paths.py (owns WHERE the script is, not HOW to load
it — this helper takes a path from there); considered importing the scripts as a package (they
are deliberately not one: `scripts/` has no `__init__.py`, and each file is an executable entry
point). 35 test files hand-rolled the load; 10 of them already included the registration below
and 25 did not, so this centralises a recipe the repo had already converged on twice over.

WHY THE `sys.modules` REGISTRATION IS NOT BOOKKEEPING. `module_from_spec` + `exec_module`
without it leaves the module absent from `sys.modules`, and anything that resolves a STRING
annotation at class-creation time then fails. `dataclasses._is_type` does exactly that:

    ns = sys.modules.get(cls.__module__).__dict__     # -> AttributeError: 'NoneType'

Every module in this repo carries `from __future__ import annotations`, which makes all
annotations strings, so the first `@dataclass` added to any script loaded the old way crashes
COLLECTION of its whole test file — measured 2026-09-02 on check_railway_logs.py: 10 errors,
and pytest still exited 0. The failure is invisible until someone adds a dataclass, which is
why 25 files carry it silently today.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_script_module(path: Path, name: str | None = None) -> ModuleType:
    """Load `path` as a module named `name` (default: the file stem) and return it.

    Raises ImportError rather than returning a half-built module: a test that silently gets
    `None` here reports as a collection error pages away from the cause.
    """
    module_name = name or path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path} as a module named {module_name!r}")
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec_module: the module body itself may define a dataclass, and the
    # lookup above happens while that body is still executing.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
