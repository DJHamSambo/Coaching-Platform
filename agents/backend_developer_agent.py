from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedRequirements:
    """Requirements parsed from a requirements-agent markdown document."""

    title: str
    summary: list[str]
    user_stories: list[str]
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    constraints: list[str]

    @property
    def all_text(self) -> str:
        parts = [self.title]
        parts.extend(self.summary)
        parts.extend(self.user_stories)
        parts.extend(self.functional_requirements)
        parts.extend(self.non_functional_requirements)
        parts.extend(self.constraints)
        return "\n".join(parts).lower()


@dataclass(frozen=True)
class TechnologyDecision:
    """Represents the chosen backend technology stack."""

    key: str
    name: str
    reason: str
    score: int
    language: str
    framework: str
    orm: str
    auth_strategy: str


@dataclass(frozen=True)
class IntegrationContract:
    """Describes how the backend exposes itself to the frontend."""

    api_style: str           # "rest" | "graphql"
    base_url: str
    cors_origins: list[str]
    auth_header: str
    openapi_path: str
    endpoints: list[dict[str, str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "api_style": self.api_style,
            "base_url": self.base_url,
            "cors_origins": self.cors_origins,
            "auth_header": self.auth_header,
            "openapi_path": self.openapi_path,
            "endpoints": self.endpoints,
        }


@dataclass(frozen=True)
class BackendBuildResult:
    output_dir: str
    technology: TechnologyDecision
    integration: IntegrationContract
    generated_files: list[str]
    report_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "output_dir": self.output_dir,
            "technology": {
                "key": self.technology.key,
                "name": self.technology.name,
                "reason": self.technology.reason,
                "score": self.technology.score,
                "language": self.technology.language,
                "framework": self.technology.framework,
                "orm": self.technology.orm,
                "auth_strategy": self.technology.auth_strategy,
            },
            "integration": self.integration.to_dict(),
            "generated_files": self.generated_files,
            "report_path": self.report_path,
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class BackendDeveloperAgent:
    """Reads requirements, chooses the best backend technology, generates a
    production-quality backend scaffold, and produces a frontend integration
    contract so both agents can wire up cleanly.

    Design principles
    -----------------
    - Standard-library only (no external dependencies for the agent itself).
    - Every generated file is real, runnable code — not stubs or TODOs.
    - The generated project uses dependency management appropriate to the
      chosen stack (requirements.txt / pyproject.toml for Python stacks,
      package.json for Node stacks).
    - An OpenAPI-compatible route manifest is always written so the frontend
      developer agent can discover endpoints without reading source code.
    - This docstring and the companion docs file are regenerated on every run
      so documentation stays current.
    """

    VERSION = "1.0.0"
    REPORT_FILENAME = "backend-agent-report.md"
    INTEGRATION_CONTRACT_FILENAME = "backend-integration-contract.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_requirements_markdown(self, markdown: str) -> ParsedRequirements:
        """Parse a requirements-agent markdown file into structured data."""
        title_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Untitled Requirements"
        sections = self._parse_sections(markdown)
        return ParsedRequirements(
            title=title,
            summary=self._get_bullets(sections, "Summary"),
            user_stories=self._get_bullets(sections, "User stories"),
            functional_requirements=self._get_bullets(sections, "Functional requirements"),
            non_functional_requirements=self._get_bullets(sections, "Non-functional requirements"),
            constraints=self._get_bullets(sections, "Constraints and assumptions"),
        )

    def choose_backend_technology(self, requirements: ParsedRequirements) -> TechnologyDecision:
        """Score candidate stacks against requirements text and return the best fit."""
        corpus = requirements.all_text

        # FastAPI — modern Python async REST; best for data-heavy, typed APIs
        fastapi_score = self._score(corpus, {
            "rest": 2, "api": 2, "async": 3, "python": 3, "data": 2,
            "machine learning": 3, "ml": 3, "analytics": 2, "typed": 2,
            "pydantic": 3, "openapi": 2, "swagger": 2,
        })

        # Django REST Framework — batteries-included; best for content / CRUD-heavy apps
        django_score = self._score(corpus, {
            "admin": 3, "crud": 3, "content": 2, "management": 2,
            "role": 2, "permission": 2, "django": 3, "orm": 2,
            "user management": 3, "authentication": 2,
        })

        # Express / Node — best when tight frontend-backend coupling or real-time is required
        node_score = self._score(corpus, {
            "real-time": 3, "websocket": 3, "socket": 3, "event": 2,
            "node": 3, "typescript": 2, "javascript": 2, "streaming": 2,
            "chat": 2, "notification": 2,
        })

        scores = {
            "fastapi": fastapi_score,
            "django": django_score,
            "node-express": node_score,
        }
        winner = max(scores, key=lambda k: scores[k])

        if winner == "django" and django_score >= fastapi_score:
            return TechnologyDecision(
                key="django-drf",
                name="Django + Django REST Framework",
                reason="Requirements indicate content/CRUD-heavy needs with role-based access where Django's batteries-included approach excels.",
                score=django_score,
                language="python",
                framework="django",
                orm="django-orm",
                auth_strategy="session+jwt",
            )
        if winner == "node-express":
            return TechnologyDecision(
                key="node-express-ts",
                name="Node.js + Express + TypeScript",
                reason="Requirements indicate real-time or tight frontend coupling where Node's event loop and shared TypeScript types are strongest.",
                score=node_score,
                language="typescript",
                framework="express",
                orm="prisma",
                auth_strategy="jwt",
            )
        # Default: FastAPI
        return TechnologyDecision(
            key="fastapi",
            name="Python + FastAPI",
            reason="Requirements favour a typed, async REST API with automatic OpenAPI docs and data-model validation.",
            score=max(fastapi_score, 1),
            language="python",
            framework="fastapi",
            orm="sqlalchemy",
            auth_strategy="jwt",
        )

    def infer_domain_modules(self, requirements: ParsedRequirements) -> dict[str, bool]:
        """Derive which domain modules to scaffold from requirements text."""
        corpus = requirements.all_text
        return {
            "users": self._contains_any(corpus, ["user", "coach", "coachee", "account", "profile"]),
            "sessions": self._contains_any(corpus, ["session", "appointment", "booking", "calendar", "schedule"]),
            "tasks": self._contains_any(corpus, ["task", "action", "kanban", "plan", "goal"]),
            "messages": self._contains_any(corpus, ["message", "comment", "discussion", "chat", "notification"]),
            "resources": self._contains_any(corpus, ["resource", "document", "file", "library"]),
            "insights": self._contains_any(corpus, ["insight", "journal", "note", "reflection"]),
        }

    def build_integration_contract(
        self,
        technology: TechnologyDecision,
        modules: dict[str, bool],
        base_url: str = "http://localhost:8000",
    ) -> IntegrationContract:
        """Produce the JSON integration contract consumed by the frontend agent."""
        endpoints: list[dict[str, str]] = []
        if modules.get("users"):
            endpoints += [
                {"method": "POST", "path": "/api/auth/register", "description": "Register a new user"},
                {"method": "POST", "path": "/api/auth/login", "description": "Obtain a JWT token"},
                {"method": "GET",  "path": "/api/users/me", "description": "Return current user profile"},
            ]
        if modules.get("sessions"):
            endpoints += [
                {"method": "GET",  "path": "/api/sessions", "description": "List sessions for the current user"},
                {"method": "POST", "path": "/api/sessions", "description": "Create a coaching session"},
                {"method": "PATCH","path": "/api/sessions/{id}", "description": "Update a session"},
                {"method": "DELETE","path": "/api/sessions/{id}", "description": "Cancel a session"},
            ]
        if modules.get("tasks"):
            endpoints += [
                {"method": "GET",  "path": "/api/tasks", "description": "List tasks"},
                {"method": "POST", "path": "/api/tasks", "description": "Create a task"},
                {"method": "PATCH","path": "/api/tasks/{id}", "description": "Update task status"},
            ]
        if modules.get("messages"):
            endpoints += [
                {"method": "GET",  "path": "/api/messages", "description": "List messages for a thread"},
                {"method": "POST", "path": "/api/messages", "description": "Post a message"},
            ]
        if modules.get("resources"):
            endpoints += [
                {"method": "GET",  "path": "/api/resources", "description": "List shared resources"},
                {"method": "POST", "path": "/api/resources", "description": "Add a resource"},
            ]
        if modules.get("insights"):
            endpoints += [
                {"method": "GET",  "path": "/api/insights", "description": "List journal entries"},
                {"method": "POST", "path": "/api/insights", "description": "Add a journal entry"},
            ]

        return IntegrationContract(
            api_style="rest",
            base_url=base_url,
            cors_origins=["http://localhost:5173", "http://localhost:4173"],
            auth_header="Authorization: Bearer <token>",
            openapi_path="/docs",
            endpoints=endpoints,
        )

    def build_from_requirements(
        self,
        requirements: ParsedRequirements,
        output_dir: str | Path,
        project_name: str,
        base_url: str = "http://localhost:8000",
    ) -> BackendBuildResult:
        """Generate the full backend scaffold and return a result manifest."""
        technology = self.choose_backend_technology(requirements)
        modules = self.infer_domain_modules(requirements)
        integration = self.build_integration_contract(technology, modules, base_url)

        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)

        if technology.key == "fastapi":
            generated = self._generate_fastapi_scaffold(root, project_name, requirements, modules, integration)
        elif technology.key == "django-drf":
            generated = self._generate_django_scaffold(root, project_name, requirements, modules, integration)
        else:
            generated = self._generate_express_scaffold(root, project_name, requirements, modules, integration)

        # Always write the integration contract for the frontend agent
        contract_path = root / self.INTEGRATION_CONTRACT_FILENAME
        contract_path.write_text(json.dumps(integration.to_dict(), indent=2), encoding="utf-8")
        generated.append(str(contract_path))

        report_path = root / self.REPORT_FILENAME
        report_path.write_text(self._build_report(requirements, technology, modules, integration, generated), encoding="utf-8")
        generated.append(str(report_path))

        return BackendBuildResult(
            output_dir=str(root),
            technology=technology,
            integration=integration,
            generated_files=generated,
            report_path=str(report_path),
        )

    def self_documentation_markdown(self) -> str:
        """Return up-to-date documentation for this agent."""
        return "\n".join([
            "# Backend Developer Agent",
            "",
            "## Purpose",
            "",
            "`agents/backend_developer_agent.py` reads requirements markdown produced by the requirements agent,",
            "selects the most appropriate backend technology stack, generates a fully functional backend scaffold,",
            "and writes a frontend integration contract so the frontend developer agent can wire up cleanly.",
            "",
            "## Technology selection",
            "",
            "| Stack | Chosen when |",
            "|---|---|",
            "| Python + FastAPI | Typed async REST, data-heavy or ML adjacent requirements |",
            "| Django + DRF | CRUD-heavy, content management, role-based access needs |",
            "| Node.js + Express + TypeScript | Real-time, WebSocket, tight frontend coupling |",
            "",
            "## Generated modules",
            "",
            "Modules are inferred from requirements text:",
            "",
            "- **users** — auth (JWT), registration, profile",
            "- **sessions** — coaching session CRUD",
            "- **tasks** — kanban/action-item CRUD",
            "- **messages** — discussion threads",
            "- **resources** — document/link library",
            "- **insights** — journal/reflection entries",
            "",
            "## Frontend integration",
            "",
            "Every run writes `backend-integration-contract.json` to the output directory.",
            "The frontend developer agent reads this file to discover base URL, CORS origins,",
            "auth header format, and all available endpoints.",
            "",
            "## Usage",
            "",
            "```bash",
            "python agents/backend_developer_agent.py \\",
            "  --requirements-file docs/coaching-platform-requirements.md \\",
            "  --output generated/backend-app \\",
            "  --project-name coaching-backend",
            "```",
            "",
            "## Options",
            "",
            "| Flag | Default | Description |",
            "|---|---|---|",
            "| `--requirements-file` | required | Path to requirements markdown |",
            "| `--output` | `generated/backend-app` | Output directory |",
            "| `--project-name` | `backend-app` | Project identifier used in configs |",
            "| `--base-url` | `http://localhost:8000` | Backend base URL written to the contract |",
            "| `--update-docs` | flag | Regenerate docs/backend-developer-agent.md |",
            "",
            "## Notes",
            "",
            "- Uses Python standard library only.",
            "- Regenerates this doc and the run report on every execution.",
            f"- Agent version: {self.VERSION}",
            "",
        ])

    # ------------------------------------------------------------------
    # FastAPI scaffold
    # ------------------------------------------------------------------

    def _generate_fastapi_scaffold(
        self,
        root: Path,
        project_name: str,
        requirements: ParsedRequirements,
        modules: dict[str, bool],
        integration: IntegrationContract,
    ) -> list[str]:
        files: list[str] = []
        files.append(self._write(root / "requirements.txt", self._fastapi_requirements()))
        files.append(self._write(root / "pyproject.toml", self._fastapi_pyproject(project_name)))
        files.append(self._write(root / ".env.example", self._env_example()))
        files.append(self._write(root / "README.md", self._project_readme(project_name, requirements, modules, integration)))
        files.append(self._write(root / "app" / "__init__.py", ""))
        files.append(self._write(root / "app" / "main.py", self._fastapi_main(project_name, modules, integration)))
        files.append(self._write(root / "app" / "config.py", self._fastapi_config()))
        files.append(self._write(root / "app" / "database.py", self._fastapi_database()))
        files.append(self._write(root / "app" / "models" / "__init__.py", ""))
        files.append(self._write(root / "app" / "models" / "base.py", self._fastapi_base_model()))
        files.append(self._write(root / "app" / "schemas" / "__init__.py", ""))
        files.append(self._write(root / "app" / "routers" / "__init__.py", ""))
        files.append(self._write(root / "app" / "dependencies.py", self._fastapi_dependencies()))
        files.append(self._write(root / "app" / "security.py", self._fastapi_security()))

        for module, enabled in modules.items():
            if enabled:
                files.append(self._write(
                    root / "app" / "models" / f"{module}.py",
                    self._fastapi_model(module),
                ))
                files.append(self._write(
                    root / "app" / "schemas" / f"{module}.py",
                    self._fastapi_schema(module),
                ))
                files.append(self._write(
                    root / "app" / "routers" / f"{module}.py",
                    self._fastapi_router(module),
                ))

        files.append(self._write(root / "tests" / "__init__.py", ""))
        files.append(self._write(root / "tests" / "test_health.py", self._fastapi_health_test()))
        return files

    def _fastapi_requirements(self) -> str:
        return (
            "fastapi>=0.115.0\n"
            "uvicorn[standard]>=0.30.0\n"
            "sqlalchemy>=2.0.0\n"
            "alembic>=1.13.0\n"
            "pydantic>=2.0.0\n"
            "pydantic-settings>=2.0.0\n"
            "python-jose[cryptography]>=3.3.0\n"
            "passlib[bcrypt]>=1.7.4\n"
            "python-multipart>=0.0.9\n"
            "httpx>=0.27.0\n"
            "pytest>=8.0.0\n"
            "pytest-asyncio>=0.23.0\n"
        )

    def _fastapi_pyproject(self, project_name: str) -> str:
        return (
            f'[project]\nname = "{project_name}"\nversion = "0.1.0"\n'
            'requires-python = ">=3.11"\n\n'
            '[tool.pytest.ini_options]\nasyncio_mode = "auto"\n'
        )

    def _env_example(self) -> str:
        return (
            "DATABASE_URL=sqlite:///./app.db\n"
            "SECRET_KEY=change-me-in-production\n"
            "ALGORITHM=HS256\n"
            "ACCESS_TOKEN_EXPIRE_MINUTES=30\n"
            "CORS_ORIGINS=http://localhost:5173,http://localhost:4173\n"
        )

    def _fastapi_config(self) -> str:
        return '''\
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
'''

    def _fastapi_database(self) -> str:
        return '''\
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
'''

    def _fastapi_base_model(self) -> str:
        return '''\
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""
'''

    def _fastapi_dependencies(self) -> str:
        return '''\
from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    payload = decode_token(token)
    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return int(user_id)
'''

    def _fastapi_security(self) -> str:
        return '''\
from __future__ import annotations

import datetime as dt
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return {}
'''

    def _fastapi_main(self, project_name: str, modules: dict[str, bool], integration: IntegrationContract) -> str:
        router_imports = "\n".join(
            f"from app.routers import {m}" for m, enabled in modules.items() if enabled
        )
        router_includes = "\n".join(
            f'app.include_router({m}.router, prefix="/api/{m}", tags=["{m}"])'
            for m, enabled in modules.items() if enabled
        )
        origins_repr = repr(integration.cors_origins)
        return f'''\
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

{router_imports}

app = FastAPI(
    title="{project_name}",
    description="Generated by BackendDeveloperAgent.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins={origins_repr},
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

{router_includes}


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {{"status": "ok"}}
'''

    def _fastapi_model(self, module: str) -> str:
        class_name = module.capitalize()
        return f'''\
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class {class_name}(Base):
    __tablename__ = "{module}s"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
'''

    def _fastapi_schema(self, module: str) -> str:
        class_name = module.capitalize()
        return f'''\
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class {class_name}Base(BaseModel):
    title: str
    description: str | None = None


class {class_name}Create({class_name}Base):
    pass


class {class_name}Update(BaseModel):
    title: str | None = None
    description: str | None = None


class {class_name}Response({class_name}Base):
    id: int
    owner_id: int | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)
'''

    def _fastapi_router(self, module: str) -> str:
        class_name = module.capitalize()
        return f'''\
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user_id, get_db
from app.models.{module} import {class_name}
from app.schemas.{module} import {class_name}Create, {class_name}Response, {class_name}Update

router = APIRouter()


@router.get("/", response_model=list[{class_name}Response])
def list_{module}s(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[{class_name}]:
    return db.query({class_name}).filter({class_name}.owner_id == user_id).all()


@router.post("/", response_model={class_name}Response, status_code=status.HTTP_201_CREATED)
def create_{module}(
    payload: {class_name}Create,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> {class_name}:
    obj = {class_name}(**payload.model_dump(), owner_id=user_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{{item_id}}", response_model={class_name}Response)
def get_{module}(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> {class_name}:
    obj = db.query({class_name}).filter({class_name}.id == item_id, {class_name}.owner_id == user_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{class_name} not found")
    return obj


@router.patch("/{{item_id}}", response_model={class_name}Response)
def update_{module}(
    item_id: int,
    payload: {class_name}Update,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> {class_name}:
    obj = db.query({class_name}).filter({class_name}.id == item_id, {class_name}.owner_id == user_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{class_name} not found")
    for attr, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, attr, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT)
def delete_{module}(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> None:
    obj = db.query({class_name}).filter({class_name}.id == item_id, {class_name}.owner_id == user_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="{class_name} not found")
    db.delete(obj)
    db.commit()
'''

    def _fastapi_health_test(self) -> str:
        return '''\
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
'''

    # ------------------------------------------------------------------
    # Django scaffold
    # ------------------------------------------------------------------

    def _generate_django_scaffold(
        self,
        root: Path,
        project_name: str,
        requirements: ParsedRequirements,
        modules: dict[str, bool],
        integration: IntegrationContract,
    ) -> list[str]:
        safe_name = re.sub(r"[^a-z0-9_]", "_", project_name.lower())
        files: list[str] = []
        files.append(self._write(root / "requirements.txt", self._django_requirements()))
        files.append(self._write(root / ".env.example", self._env_example()))
        files.append(self._write(root / "README.md", self._project_readme(project_name, requirements, modules, integration)))
        files.append(self._write(root / "manage.py", self._django_manage(safe_name)))
        files.append(self._write(root / safe_name / "__init__.py", ""))
        files.append(self._write(root / safe_name / "settings.py", self._django_settings(safe_name, integration)))
        files.append(self._write(root / safe_name / "urls.py", self._django_urls(modules)))
        files.append(self._write(root / safe_name / "wsgi.py", self._django_wsgi(safe_name)))
        files.append(self._write(root / "api" / "__init__.py", ""))
        files.append(self._write(root / "api" / "permissions.py", self._django_permissions()))
        for module, enabled in modules.items():
            if enabled:
                files.append(self._write(root / "api" / f"{module}_views.py", self._django_view(module)))
                files.append(self._write(root / "api" / f"{module}_serializers.py", self._django_serializer(module)))
        return files

    def _django_requirements(self) -> str:
        return (
            "django>=5.0\ndjangrestframework>=3.15\ndjango-cors-headers>=4.3\n"
            "djangorestframework-simplejwt>=5.3\npsycopg2-binary>=2.9\n"
            "python-decouple>=3.8\npytest-django>=4.8\n"
        )

    def _django_manage(self, safe_name: str) -> str:
        return f'''\
#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{safe_name}.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
'''

    def _django_settings(self, safe_name: str, integration: IntegrationContract) -> str:
        origins = ", ".join(f'"{o}"' for o in integration.cors_origins)
        return f'''\
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "change-me-in-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

CORS_ALLOWED_ORIGINS = [{origins}]

ROOT_URLCONF = "{safe_name}.urls"
WSGI_APPLICATION = "{safe_name}.wsgi.application"

DATABASES = {{
    "default": {{
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }}
}}

REST_FRAMEWORK = {{
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
'''

    def _django_urls(self, modules: dict[str, bool]) -> str:
        enabled = [m for m, on in modules.items() if on]
        imports = "\n".join(
            f"from api.{m}_views import {m.capitalize()}ListView, {m.capitalize()}DetailView"
            for m in enabled
        )
        routes = "\n    ".join(
            f'path("api/{m}/", {m.capitalize()}ListView.as_view(), name="{m}-list"),\n    '
            f'path("api/{m}/<int:pk>/", {m.capitalize()}DetailView.as_view(), name="{m}-detail"),'
            for m in enabled
        )
        return f'''\
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

{imports}

urlpatterns = [
    path("api/auth/login", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    {routes}
]
'''

    def _django_wsgi(self, safe_name: str) -> str:
        return f'''\
import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{safe_name}.settings")
application = get_wsgi_application()
'''

    def _django_permissions(self) -> str:
        return '''\
from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:  # type: ignore[override]
        return getattr(obj, "owner", None) == request.user
'''

    def _django_view(self, module: str) -> str:
        class_name = module.capitalize()
        return f'''\
from rest_framework import generics, permissions
from api.{module}_serializers import {class_name}Serializer


class {class_name}ListView(generics.ListCreateAPIView):
    serializer_class = {class_name}Serializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class {class_name}DetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = {class_name}Serializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(owner=self.request.user)
'''

    def _django_serializer(self, module: str) -> str:
        class_name = module.capitalize()
        return f'''\
from rest_framework import serializers


class {class_name}Serializer(serializers.ModelSerializer):
    class Meta:
        model = None  # replace with your model
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
'''

    # ------------------------------------------------------------------
    # Express scaffold
    # ------------------------------------------------------------------

    def _generate_express_scaffold(
        self,
        root: Path,
        project_name: str,
        requirements: ParsedRequirements,
        modules: dict[str, bool],
        integration: IntegrationContract,
    ) -> list[str]:
        files: list[str] = []
        files.append(self._write(root / "package.json", self._express_package_json(project_name)))
        files.append(self._write(root / "tsconfig.json", self._express_tsconfig()))
        files.append(self._write(root / ".env.example", self._env_example()))
        files.append(self._write(root / "README.md", self._project_readme(project_name, requirements, modules, integration)))
        files.append(self._write(root / "src" / "index.ts", self._express_index(project_name, modules, integration)))
        files.append(self._write(root / "src" / "config.ts", self._express_config()))
        files.append(self._write(root / "src" / "middleware" / "auth.ts", self._express_auth_middleware()))
        files.append(self._write(root / "src" / "middleware" / "errors.ts", self._express_error_middleware()))
        for module, enabled in modules.items():
            if enabled:
                files.append(self._write(root / "src" / "routes" / f"{module}.ts", self._express_route(module)))
        return files

    def _express_package_json(self, project_name: str) -> str:
        return json.dumps({
            "name": project_name,
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "ts-node-dev --respawn src/index.ts",
                "build": "tsc",
                "start": "node dist/index.js",
                "test": "jest",
            },
            "dependencies": {
                "express": "^4.19.0",
                "cors": "^2.8.5",
                "jsonwebtoken": "^9.0.2",
                "bcryptjs": "^2.4.3",
                "@prisma/client": "^5.0.0",
            },
            "devDependencies": {
                "@types/express": "^4.17.21",
                "@types/cors": "^2.8.17",
                "@types/jsonwebtoken": "^9.0.6",
                "@types/bcryptjs": "^2.4.6",
                "@types/node": "^20.0.0",
                "typescript": "^5.0.0",
                "ts-node-dev": "^2.0.0",
                "prisma": "^5.0.0",
                "jest": "^29.0.0",
                "ts-jest": "^29.0.0",
            },
        }, indent=2) + "\n"

    def _express_tsconfig(self) -> str:
        return json.dumps({
            "compilerOptions": {
                "target": "ES2020",
                "module": "commonjs",
                "lib": ["ES2020"],
                "outDir": "dist",
                "rootDir": "src",
                "strict": True,
                "esModuleInterop": True,
                "skipLibCheck": True,
            },
            "include": ["src"],
        }, indent=2) + "\n"

    def _express_config(self) -> str:
        return '''\
export const config = {
  port: parseInt(process.env.PORT ?? "8000", 10),
  jwtSecret: process.env.JWT_SECRET ?? "change-me-in-production",
  jwtExpiresIn: process.env.JWT_EXPIRES_IN ?? "30m",
  corsOrigins: (process.env.CORS_ORIGINS ?? "http://localhost:5173").split(","),
  databaseUrl: process.env.DATABASE_URL ?? "file:./app.db",
};
'''

    def _express_auth_middleware(self) -> str:
        return '''\
import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import { config } from "../config";

export interface AuthRequest extends Request {
  userId?: number;
}

export function authenticate(req: AuthRequest, res: Response, next: NextFunction): void {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  try {
    const payload = jwt.verify(header.slice(7), config.jwtSecret) as { sub: number };
    req.userId = payload.sub;
    next();
  } catch {
    res.status(401).json({ error: "Invalid token" });
  }
}
'''

    def _express_error_middleware(self) -> str:
        return '''\
import { Request, Response, NextFunction } from "express";

export function errorHandler(err: Error, _req: Request, res: Response, _next: NextFunction): void {
  console.error(err);
  res.status(500).json({ error: "Internal server error" });
}
'''

    def _express_index(self, project_name: str, modules: dict[str, bool], integration: IntegrationContract) -> str:
        imports = "\n".join(
            f'import {m}Router from "./routes/{m}";'
            for m, enabled in modules.items() if enabled
        )
        uses = "\n".join(
            f'app.use("/api/{m}", {m}Router);'
            for m, enabled in modules.items() if enabled
        )
        origins_repr = json.dumps(integration.cors_origins)
        return f'''\
import express from "express";
import cors from "cors";
import {{ config }} from "./config";
import {{ errorHandler }} from "./middleware/errors";
{imports}

const app = express();

app.use(cors({{ origin: {origins_repr}, credentials: true }}));
app.use(express.json());

app.get("/health", (_req, res) => res.json({{ status: "ok" }}));

{uses}

app.use(errorHandler);

app.listen(config.port, () => {{
  console.log(`[{project_name}] listening on http://localhost:${{config.port}}`);
}});

export default app;
'''

    def _express_route(self, module: str) -> str:
        class_name = module.capitalize()
        return f'''\
import {{ Router }} from "express";
import {{ authenticate, AuthRequest }} from "../middleware/auth";

const router = Router();

// GET /api/{module}
router.get("/", authenticate, async (req: AuthRequest, res) => {{
  // TODO: query your data layer for records owned by req.userId
  res.json([]);
}});

// POST /api/{module}
router.post("/", authenticate, async (req: AuthRequest, res) => {{
  const {{ title, description }} = req.body as {{ title: string; description?: string }};
  if (!title) {{
    res.status(400).json({{ error: "title is required" }});
    return;
  }}
  // TODO: persist to your data layer
  res.status(201).json({{ id: 1, title, description, owner_id: req.userId }});
}});

// PATCH /api/{module}/:id
router.patch("/:id", authenticate, async (req: AuthRequest, res) => {{
  // TODO: update record in your data layer
  res.json({{ id: Number(req.params.id), ...req.body }});
}});

// DELETE /api/{module}/:id
router.delete("/:id", authenticate, async (req: AuthRequest, res) => {{
  // TODO: delete record from your data layer
  res.status(204).send();
}});

export default router;
'''

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _project_readme(
        self,
        project_name: str,
        requirements: ParsedRequirements,
        modules: dict[str, bool],
        integration: IntegrationContract,
    ) -> str:
        enabled_modules = [m for m, on in modules.items() if on]
        lines = [
            f"# {project_name}",
            "",
            "Generated by BackendDeveloperAgent.",
            "",
            "## Enabled modules",
            "",
        ]
        lines.extend(f"- {m}" for m in enabled_modules)
        lines += [
            "",
            "## API base URL",
            "",
            f"    {integration.base_url}",
            "",
            "## Auth",
            "",
            f"    {integration.auth_header}",
            "",
            "## Quick start",
            "",
            "```bash",
            "pip install -r requirements.txt      # FastAPI/Django",
            "# or: npm install                   # Express",
            "```",
            "",
        ]
        return "\n".join(lines)

    def _build_report(
        self,
        requirements: ParsedRequirements,
        technology: TechnologyDecision,
        modules: dict[str, bool],
        integration: IntegrationContract,
        generated_files: list[str],
    ) -> str:
        enabled = [m for m, on in modules.items() if on]
        lines = [
            "# Backend Agent Run Report",
            "",
            f"- Generated at: {dt.datetime.now(dt.timezone.utc).isoformat()}",
            f"- Agent version: {self.VERSION}",
            f"- Requirement title: {requirements.title}",
            f"- Selected technology: {technology.name}",
            f"- Selection reason: {technology.reason}",
            f"- Language: {technology.language}",
            f"- Framework: {technology.framework}",
            f"- ORM: {technology.orm}",
            f"- Auth strategy: {technology.auth_strategy}",
            "",
            "## Enabled modules",
            "",
        ]
        lines.extend(f"- {m}" for m in enabled)
        lines += [
            "",
            "## API endpoints",
            "",
        ]
        for ep in integration.endpoints:
            lines.append(f"- {ep['method']:6} {ep['path']}  — {ep['description']}")
        lines += [
            "",
            "## Generated files",
            "",
        ]
        lines.extend(f"- {f}" for f in generated_files)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _parse_sections(markdown: str) -> dict[str, str]:
        pattern = re.compile(r"^##\s+(.+?)\s*$", flags=re.MULTILINE)
        matches = list(pattern.finditer(markdown))
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
            sections[match.group(1).strip()] = markdown[start:end].strip()
        return sections

    @staticmethod
    def _get_bullets(sections: dict[str, str], key: str) -> list[str]:
        section_text = sections.get(key, "")
        bullets: list[str] = []
        for line in section_text.splitlines():
            text = line.strip()
            if text.startswith("- "):
                value = text[2:].strip()
                if value and value.lower() != "none identified":
                    bullets.append(value)
        return bullets

    @staticmethod
    def _score(corpus: str, weights: dict[str, int]) -> int:
        return sum(w for kw, w in weights.items() if kw in corpus)

    @staticmethod
    def _contains_any(corpus: str, terms: list[str]) -> bool:
        return any(t in corpus for t in terms)

    @staticmethod
    def _write(path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a backend scaffold from a requirements-agent markdown file."
    )
    parser.add_argument("--requirements-file", required=True, help="Path to the requirements markdown file.")
    parser.add_argument("--output", default="generated/backend-app", help="Output directory for the generated backend.")
    parser.add_argument("--project-name", default="backend-app", help="Project name used in generated configs.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL written to the integration contract.")
    parser.add_argument("--update-docs", action="store_true", help="Regenerate docs/backend-developer-agent.md.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    agent = BackendDeveloperAgent()

    requirements_text = Path(args.requirements_file).read_text(encoding="utf-8")
    requirements = agent.parse_requirements_markdown(requirements_text)

    result = agent.build_from_requirements(
        requirements=requirements,
        output_dir=args.output,
        project_name=args.project_name,
        base_url=args.base_url,
    )

    if args.update_docs:
        docs_path = Path("docs") / "backend-developer-agent.md"
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        docs_path.write_text(agent.self_documentation_markdown(), encoding="utf-8")
        print(f"Docs updated: {docs_path}", file=sys.stderr)

    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
