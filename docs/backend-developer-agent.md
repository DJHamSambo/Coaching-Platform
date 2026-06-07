# Backend Developer Agent

## Purpose

`agents/backend_developer_agent.py` reads requirements markdown produced by the requirements agent,
selects the most appropriate backend technology stack, generates a fully functional backend scaffold,
and writes a frontend integration contract so the frontend developer agent can wire up cleanly.

## Technology selection

| Stack | Chosen when |
|---|---|
| Python + FastAPI | Typed async REST, data-heavy or ML adjacent requirements |
| Django + DRF | CRUD-heavy, content management, role-based access needs |
| Node.js + Express + TypeScript | Real-time, WebSocket, tight frontend coupling |

## Generated modules

Modules are inferred from requirements text:

- **users** — auth (JWT), registration, profile
- **sessions** — coaching session CRUD
- **tasks** — kanban/action-item CRUD
- **messages** — discussion threads
- **resources** — document/link library
- **insights** — journal/reflection entries

## Frontend integration

Every run writes `backend-integration-contract.json` to the output directory.
The frontend developer agent reads this file to discover base URL, CORS origins,
auth header format, and all available endpoints.

## Usage

```bash
python agents/backend_developer_agent.py \
  --requirements-file docs/coaching-platform-requirements.md \
  --output generated/backend-app \
  --project-name coaching-backend
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--requirements-file` | required | Path to requirements markdown |
| `--output` | `generated/backend-app` | Output directory |
| `--project-name` | `backend-app` | Project identifier used in configs |
| `--base-url` | `http://localhost:8000` | Backend base URL written to the contract |
| `--update-docs` | flag | Regenerate docs/backend-developer-agent.md |

## Notes

- Uses Python standard library only.
- Regenerates this doc and the run report on every execution.
- Agent version: 1.0.0
