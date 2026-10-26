---
name: Task
about: One issue, one service, one layer, about one PR
title: ""
labels: []
---

<!-- ck:{{R}}:{{slug}} -->

## Goal
{{One or two sentences: what exists when this is done}}

Delivers: {{R<n>}}
Touches: {{paths, one service}}
Depends on: {{#n, #m | none}}
Contract: {{docs/contracts/<name>.md | none}}
Budget: {{~files, ~lines}}

## My reading of {{R<n>}}
{{One sentence: how this issue interprets the requirement. The user approves this with the plan}}

## Decisions

<!-- Kickoff seeds boundary decisions; /orchestrate adds the plan's rows; the worker adds how-to rows. Chosen = `ask` makes the worker stop and ask. -->

| Question | Options | Chosen | Why |
|---|---|---|---|

## Acceptance criteria
- [ ] {{From R<n>'s acceptance bullets, narrowed to this issue}}
- [ ] `make check` passes

## Out of scope
- {{What this issue deliberately doesn't do, including neighbouring issues' work}}
