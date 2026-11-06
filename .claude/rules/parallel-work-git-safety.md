---
description: MANDATORY — never stash or discard another dev's or parallel agent's uncommitted work.
alwaysApply: true
---

# Parallel work & git safety (MANDATORY)

Canonical policy: `AGENTS.md` § Parallel work & git safety.

**Never** `git stash`, `git restore`, `git reset`, or `git clean` on paths outside your current task scope. Another developer or agent may be running tests on those files — stashing makes their work disappear from the working tree.

Commit and push **only your files**. If pre-push hooks fail due to unrelated dirty files, stop and report — do not stash others' work. Do not use `--no-verify` unless the user explicitly requests it.
