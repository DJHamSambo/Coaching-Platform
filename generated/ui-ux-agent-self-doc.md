# UI/UX Agent

## Purpose

`agents/ui_ux_agent.py` critically reviews frontend UX quality, current UI trends, and WCAG accessibility coverage.
It outputs recommendations first, and only after approval emits developer-agent handoff instructions.

## Review focus

- Visual hierarchy and readability
- Interaction clarity and reduced friction
- Mobile responsiveness and touch targets
- Accessibility heuristics aligned to WCAG 2.2
- Modern frontend UX trends (progressive disclosure, density control, clear feedback states)

## Workflow

1. Run review mode to produce recommendations and a score.
2. Approve recommendation IDs.
3. Run approval mode to generate implementation instructions for developer agents.

## Usage

```bash
python agents/ui_ux_agent.py review \
  --frontend-root generated/frontend-app \
  --report generated/ui-ux-agent-report.md

python agents/ui_ux_agent.py approve \
  --recommendations-file generated/ui-ux-recommendations.json \
  --approved-ids UX-001,UX-003 \
  --handoff generated/ui-ux-approved-changes.md
```

## Notes

- Uses Python standard library only.
- Refreshes this document on each run so the docs stay current with agent behavior.
- Agent version: 1.0.0
