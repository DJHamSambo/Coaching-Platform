# Frontend Developer Agent

## Purpose

`agents/frontend_developer_agent.py` reads requirements markdown and generates a functional frontend scaffold.

## Delivered modules

- Planning board (kanban tasks with status movement)
- Session scheduler and availability requests
- Discussion threads with @mention extraction
- Insights/journal timeline
- Resource library and filtering

## Usage

```bash
python agents/frontend_developer_agent.py \
  --requirements-file docs/coaching-platform-requirements.md \
  --output generated/frontend-app \
  --project-name coaching-frontend
```

## Notes

- Uses Python standard library only.
- Regenerates this doc and frontend-agent-report.md each execution so documentation stays current.
- Agent version: 2.1.0
