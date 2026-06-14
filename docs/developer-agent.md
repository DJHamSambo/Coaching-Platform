# Developer Agent

## Purpose

`agents/developer_agent.py` is a single end-to-end developer agent that reads requirements markdown and generates both backend and frontend implementations in one run.

## What it does

- Parses requirements markdown once
- Builds backend implementation and integration contract
- Builds frontend implementation scaffold
- Writes a unified run report
- Applies persistence-ready backend/frontend scaffold alignment for tasks and discussions

## Usage

```bash
python agents/developer_agent.py \
  --requirements-file docs/coaching-platform-requirements.md \
  --output generated \
  --backend-dir-name backend-app \
  --frontend-dir-name frontend-app
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--requirements-file` | required | Path to the requirements markdown file |
| `--output` | `generated` | Output root for generated artifacts |
| `--project-name` | `coaching` | Legacy prefix used when backend/frontend project names are not provided |
| `--backend-dir-name` | `backend-app` | Subdirectory name for backend output |
| `--frontend-dir-name` | `frontend-app` | Subdirectory name for frontend output |
| `--backend-project-name` | `coaching-backend` | Backend project name used in generated configs |
| `--frontend-project-name` | `coaching-frontend` | Frontend package/project name |
| `--base-url` | `http://localhost:8000` | Backend base URL written to integration contract |
| `--update-docs` | flag | Regenerate docs/developer-agent.md |

## Output structure

- `generated/backend-app/` (or custom name): generated backend implementation
- `generated/frontend-app/` (or custom name): generated frontend implementation
- `generated/developer-agent-report.md`: unified run report

## Notes

- Uses Python standard library only.
- Delegates backend and frontend generation to the existing implementation modules.
- By default it updates `generated/backend-app` and `generated/frontend-app` in place.
- Emits aligned scaffolds so planning board actions and discussions can be persisted end to end.
- Agent version: 1.2.0
