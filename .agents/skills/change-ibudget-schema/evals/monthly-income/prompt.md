---
tags: [skill-creator]
max_turns: 80
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Add income tracking: `ibudget income set 2500` sets the income for the current month (or another one with --month), and `ibudget report` should show the month's income and what's left after expenses at the bottom.
