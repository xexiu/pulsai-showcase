---
name: research
description: >-
  Delegate primary-source reading to ONE Sonnet subagent; write one cited Markdown
  file under .scratch/research/. Use for external facts a decision waits on — not
  for ADRs, grilling, or prototyping.
disable-model-invocation: true
---

Spin up a **background agent** to do the research, so you keep working while it reads.

Its job:

1. Investigate the question against **primary sources** — official docs, source code, specs, first-party APIs — not a secondary write-up of them. Follow every claim back to the source that owns it.
2. Write the findings to a single Markdown file, citing each claim's source.
3. Save it where the repo already keeps such notes; match the existing convention, and if there is none, put it somewhere sensible and say where.

## PulsAI usage (mandatory)

Guide: [aihero](https://www.aihero.dev/skills-research).

### Anti-nesting (upstream [#530](https://github.com/mattpocock/skills/issues/530))

The shipped skill's #1 failure is recursive research agents (hundreds of thousands of tokens).

- Parent may spawn **exactly one** research subagent for this question.
- If **you are already a subagent** running research: **do the reading yourself** — do **not** spawn another agent / Task / research skill.
- Watch the background-task list; kill near-duplicate second research runs immediately.
- Subagent model: **Sonnet** per `AGENTS.md` § Subagent model routing (never inherit Opus for this legwork).

### Output location

Write **one** file per run under:

```text
.scratch/research/<YYYY-MM-DD>-<short-slug>.md
```

That directory is **gitignored** (ephemeral). Do not commit research dumps by default — they go stale and poison later reads. Durable decisions → `/domain-modeling` / `docs/08-adr/` after the three-bar test. Point tickets/issues at the scratch path or paste a short gist when needed.

Wayfinder research tickets may also land findings on a throwaway `research/<name>` branch with a context pointer — still **never open a merge PR** for that branch ([#576](https://github.com/mattpocock/skills/issues/576)).

### Scope

- Narrow, answerable question (one API / one behaviour / one version claim). Broad "research X" underperforms.
- Primary sources only; if a citation lands on a blog summary of the thing, the run failed — replace with the owning doc/spec/code.
- This skill produces **facts** (short shelf life). Decisions → grill / domain-modeling / ADR. Codebase "does this work here?" → `/prototype`.
- User-invoked (`disable-model-invocation: true`) so casual "look this up" one-liners don't auto-spawn background agents; owner types `/research …` or a wayfinder research ticket names it.
- Shell via `./scripts/run-with-nohup.sh`. Do not stash foreign dirty files when creating `research/<name>` branches.
- Not a substitute for PulsAI edge-hunt EXTERNAL RESEARCH loops (those follow `edge_lab` HARD RULES); this skill is general primary-source legwork.
- Policy authority: `.cursorrules` / `CODING_STANDARDS.md` / `AGENTS.md`.
