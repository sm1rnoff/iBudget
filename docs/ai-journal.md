# AI journal

A running log of how AI assistants were used to build iBudget, one entry per module. It is the raw material for the exam write-up: what was asked, which tool, key prompts, what had to be corrected, and how the result was tested.

## Template

```
## <Module name> — <date>

- **Tool:** Claude Code (model) / Copilot / Cursor …, and why
- **Goal:** what this step had to deliver
- **Key prompts:**
  1. "…"
  2. "…"
- **What the AI produced:** files, commands, design decisions
- **What I corrected or rejected:** and why
- **Testing:** what tests were added, how the result was checked
```

---

## 0. Planning & requirements — 2026-11-02

- **Tool:** Claude Code (Opus 5.5) in the Claude desktop app, plan mode. Chosen because it can read the repo, ask clarifying questions and write the plan before touching code.
- **Goal:** pick a project, agree on scope, write requirements and an implementation plan.
- **Key prompts:**
  1. "First help me choose some simple project to implement. Propose some ideas.."
  2. "Honestly do you think it would be a good idea to add also an UI" → chose option B: a read-only web dashboard on top of the CLI.
  3. "We will go with option B. Let's write requirements and plan it first"
- **What the AI produced:** project ideas, the iBudget scope, `docs/requirements.md`, a step-by-step plan (one commit per module), the CLAUDE.md rules.
- **What I corrected or rejected:**
  - Python had been upgraded to 3.14, so the plan's uv-based Python install was not needed; after the AI explained what uv still adds, I chose plain `venv` + `pip`.
  - Categories had to support rename and delete, not only add.
  - Skills must live in `.agents/skills/` and be linked from `.claude/skills/`.
  - The dashboard must use HTMX instead of Chart.js.
- **Testing:** n/a (planning only).
