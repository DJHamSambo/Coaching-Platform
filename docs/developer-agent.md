# Developer Agent

## Purpose

`agents/developer_agent.py` is a single end-to-end developer agent that reads requirements markdown and generates both backend and frontend implementations in one run.

## What it does

- Parses requirements markdown once
- Builds backend implementation and integration contract
- Builds frontend implementation scaffold
- Writes a unified run report

## Usage

```bash
python agents/developer_agent.py \
  --requirements-file docs/coaching-platform-requirements.md \
  --output generated/full-stack-app \
  --project-name coaching-platform
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--requirements-file` | required | Path to the requirements markdown file |
| `--output` | `generated/full-stack-app` | Output directory for all generated artifacts |
| `--project-name` | `coaching-platform` | Project name prefix used by backend/frontend outputs |
| `--backend-dir-name` | `backend-app` | Subdirectory name for backend output |
| `--frontend-dir-name` | `frontend-app` | Subdirectory name for frontend output |
| `--base-url` | `http://localhost:8000` | Backend base URL written to integration contract |
| `--update-docs` | flag | Regenerate docs/developer-agent.md |

## Output structure

- `backend-app/` (or custom name): generated backend implementation
- `frontend-app/` (or custom name): generated frontend implementation
- `developer-agent-report.md`: unified run report

## Notes

- Uses Python standard library only.
- Delegates backend and frontend generation to the existing implementation modules.
- Agent version: 1.0.0
