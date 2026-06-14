from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedRequirements:
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
class FeatureSet:
    planning_board: bool
    sessions: bool
    discussions: bool
    resources: bool
    insights: bool


@dataclass(frozen=True)
class TechnologyDecision:
    key: str
    name: str
    reason: str
    score: int


@dataclass(frozen=True)
class BuildResult:
    output_dir: str
    technology: TechnologyDecision
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
            },
            "generated_files": self.generated_files,
            "report_path": self.report_path,
        }


class FrontendDeveloperAgent:
    VERSION = "2.1.0"
    REPORT_FILENAME = "frontend-agent-report.md"

    def parse_requirements_markdown(self, markdown: str) -> ParsedRequirements:
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

    def infer_features(self, requirements: ParsedRequirements) -> FeatureSet:
        corpus = requirements.all_text
        return FeatureSet(
            planning_board=self._contains_any(corpus, ["kanban", "task", "plan", "action"]),
            sessions=self._contains_any(corpus, ["session", "calendar", "availability", "booking"]),
            discussions=self._contains_any(corpus, ["comment", "discussion", "mention", "notification"]),
            resources=self._contains_any(corpus, ["resource", "document", "share"]),
            insights=self._contains_any(corpus, ["insight", "journal", "note", "profile"]),
        )

    def choose_frontend_technology(self, requirements: ParsedRequirements) -> TechnologyDecision:
        corpus = requirements.all_text
        next_score = self._score(corpus, {"seo": 3, "ssr": 3, "server-side": 3, "content": 2, "landing": 2})
        react_score = self._score(
            corpus,
            {
                "dashboard": 3,
                "kanban": 3,
                "task": 2,
                "session": 2,
                "calendar": 2,
                "comment": 2,
                "notification": 2,
                "workflow": 2,
            },
        )

        if next_score > react_score:
            return TechnologyDecision(
                key="nextjs-ts",
                name="Next.js + TypeScript",
                reason="Requirements indicate SSR/content-heavy delivery where Next.js is a stronger fit.",
                score=next_score,
            )

        return TechnologyDecision(
            key="react-vite-ts",
            name="React + Vite + TypeScript",
            reason="Requirements emphasize interactive product workflows where a typed SPA architecture is ideal.",
            score=react_score,
        )

    def build_from_requirements(self, requirements: ParsedRequirements, output_dir: str | Path, project_name: str) -> BuildResult:
        decision = self.choose_frontend_technology(requirements)
        features = self.infer_features(requirements)
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)

        generated = self._generate_vite_template(root, project_name, requirements, features)
        if decision.key == "nextjs-ts":
            generated.extend(self._generate_next_hint_files(root, requirements, features))

        report_path = root / self.REPORT_FILENAME
        report_path.write_text(self._build_report(requirements, decision, features, generated), encoding="utf-8")
        generated.append(str(report_path))

        return BuildResult(
            output_dir=str(root),
            technology=decision,
            generated_files=generated,
            report_path=str(report_path),
        )

    def self_documentation_markdown(self) -> str:
        return "\n".join(
            [
          "# Frontend Developer Agent (Deprecated)",
                "",
          "This document is kept for backward compatibility.",
                "",
          "Use the unified end-to-end Developer Agent instead:",
                "",
          "- Primary docs: `docs/developer-agent.md`",
              "- Primary CLI: `python agents/developer_agent.py --requirements-file docs/coaching-platform-requirements.md --output generated --backend-dir-name backend-app --frontend-dir-name frontend-app`",
          "",
          "The frontend developer agent implementation remains available as an internal building block used by the unified Developer Agent.",
          "",
                f"- Agent version: {self.VERSION}",
                "",
            ]
        )

    def _generate_vite_template(
        self,
        root: Path,
        project_name: str,
        requirements: ParsedRequirements,
        features: FeatureSet,
    ) -> list[str]:
        files: list[str] = []
        files.append(self._write(root / "package.json", self._package_json(project_name)))
        files.append(self._write(root / "tsconfig.json", self._tsconfig()))
        files.append(self._write(root / "vite.config.ts", self._vite_config()))
        files.append(self._write(root / "index.html", self._index_html()))
        files.append(self._write(root / "src" / "main.tsx", self._main_tsx()))
        files.append(self._write(root / "src" / "api.ts", self._api_ts()))
        files.append(self._write(root / "src" / "styles.css", self._styles_css()))
        files.append(self._write(root / "src" / "types.ts", self._types_ts()))
        files.append(self._write(root / "src" / "data" / "seed.ts", self._seed_ts(requirements)))
        files.append(self._write(root / "src" / "components" / "KanbanBoard.tsx", self._kanban_board_tsx()))
        files.append(self._write(root / "src" / "components" / "SessionPlanner.tsx", self._session_planner_tsx()))
        files.append(self._write(root / "src" / "components" / "DiscussionPanel.tsx", self._discussion_panel_tsx()))
        files.append(self._write(root / "src" / "components" / "InsightsJournal.tsx", self._insights_journal_tsx()))
        files.append(self._write(root / "src" / "components" / "ResourceLibrary.tsx", self._resource_library_tsx()))
        files.append(self._write(root / "src" / "App.tsx", self._app_tsx(requirements, features)))
        files.append(self._write(root / "README.md", self._project_readme(project_name, requirements, features)))
        return files

    def _generate_next_hint_files(self, root: Path, requirements: ParsedRequirements, features: FeatureSet) -> list[str]:
        handoff = root / "next-handoff.md"
        content = "\n".join(
            [
                "# Next.js Handoff",
                "",
                "Requirements scoring favored Next.js. This run still generated the full interactive React/Vite scaffold",
                "as the default executable artifact. Port module files into Next.js routes/components as needed.",
                "",
                f"Requirement title: {requirements.title}",
                f"planning_board: {features.planning_board}",
                f"sessions: {features.sessions}",
                f"discussions: {features.discussions}",
                f"insights: {features.insights}",
                f"resources: {features.resources}",
                "",
            ]
        )
        return [self._write(handoff, content)]

    def _project_readme(self, project_name: str, requirements: ParsedRequirements, features: FeatureSet) -> str:
        baseline = requirements.functional_requirements or requirements.user_stories or requirements.summary
        lines = [
            f"# {project_name}",
            "",
            "Generated by FrontendDeveloperAgent.",
            "",
            "## Enabled modules",
            "",
            f"- Planning board: {features.planning_board}",
            f"- Sessions: {features.sessions}",
            f"- Discussions: {features.discussions}",
            f"- Insights/journal: {features.insights}",
            f"- Resources: {features.resources}",
            "",
            "## Requirement baseline",
            "",
        ]
        if baseline:
            lines.extend(f"- {item}" for item in baseline[:10])
        else:
            lines.append("- No requirement baseline items were parsed.")
        lines.extend(["", "## Run", "", "- npm install", "- npm run dev", ""])
        return "\n".join(lines)

    def _build_report(
        self,
        requirements: ParsedRequirements,
        decision: TechnologyDecision,
        features: FeatureSet,
        generated_files: list[str],
    ) -> str:
        lines = [
            "# Frontend Agent Run Report",
            "",
            f"- Generated at: {dt.datetime.now(dt.timezone.utc).isoformat()}",
            f"- Agent version: {self.VERSION}",
            f"- Requirement title: {requirements.title}",
            f"- Selected technology: {decision.name}",
            f"- Selection reason: {decision.reason}",
            "",
            "## Inferred modules",
            "",
            f"- planning_board: {features.planning_board}",
            f"- sessions: {features.sessions}",
            f"- discussions: {features.discussions}",
            f"- insights: {features.insights}",
            f"- resources: {features.resources}",
            "",
            "## Generated files",
            "",
        ]
        lines.extend(f"- {item}" for item in generated_files)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _contains_any(corpus: str, terms: list[str]) -> bool:
        return any(term in corpus for term in terms)

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
        return sum(weight for keyword, weight in weights.items() if keyword in corpus)

    @staticmethod
    def _write(path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _package_json(self, project_name: str) -> str:
        return json.dumps(
            {
                "name": project_name,
                "private": True,
                "version": "0.3.0",
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "tsc -b && vite build",
                    "preview": "vite preview",
                },
                "dependencies": {
                    "react": "^18.3.1",
                    "react-dom": "^18.3.1",
                },
                "devDependencies": {
                    "@types/react": "^18.3.11",
                    "@types/react-dom": "^18.3.1",
                    "@vitejs/plugin-react": "^4.3.1",
                    "typescript": "^5.6.2",
                    "vite": "^5.4.8",
                },
            },
            indent=2,
        ) + "\n"

    @staticmethod
    def _tsconfig() -> str:
        return """{
  \"compilerOptions\": {
    \"target\": \"ES2020\",
    \"useDefineForClassFields\": true,
    \"lib\": [\"ES2020\", \"DOM\", \"DOM.Iterable\"],
    \"module\": \"ESNext\",
    \"skipLibCheck\": true,
    \"moduleResolution\": \"Bundler\",
    \"resolveJsonModule\": true,
    \"isolatedModules\": true,
    \"noEmit\": true,
    \"jsx\": \"react-jsx\",
    \"strict\": true
  },
  \"include\": [\"src\"]
}
"""

    @staticmethod
    def _vite_config() -> str:
        return """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
});
"""

    @staticmethod
    def _index_html() -> str:
        return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Frontend Delivery Workspace</title>
  </head>
  <body>
    <div id=\"root\"></div>
    <script type=\"module\" src=\"/src/main.tsx\"></script>
  </body>
</html>
"""

    @staticmethod
    def _main_tsx() -> str:
        return """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""

    @staticmethod
    def _api_ts() -> str:
        return """// API client — talks to the Django backend at http://localhost:8000
// All calls attach the stored JWT token automatically.

import type { DiscussionItem, PlanTask, TaskStatus } from './types';

const BASE_URL = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'coaching_jwt';

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface RegisterPayload {
  username: string;
  password: string;
  email?: string;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function register(payload: RegisterPayload): Promise<{ id: number; username: string; email: string }> {
  return request('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function login(payload: LoginPayload): Promise<AuthTokens> {
  return request('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status} ${text}`);
  }
  if (response.status === 204) return undefined as unknown as T;
  return response.json() as Promise<T>;
}

interface ApiTask {
  id: number;
  title: string;
  description: string;
  status: 'backlog' | 'in_progress' | 'done';
  assignee: string;
  due_date: string | null;
}

function toFrontendStatus(status: ApiTask['status']): TaskStatus {
  if (status === 'in_progress') return 'inProgress';
  return status;
}

function toApiStatus(status: TaskStatus): ApiTask['status'] {
  if (status === 'inProgress') return 'in_progress';
  return status;
}

function toPlanTask(task: ApiTask): PlanTask {
  return {
    id: String(task.id),
    title: task.title,
    description: task.description,
    status: toFrontendStatus(task.status),
    assignee: task.assignee,
    dueDate: task.due_date ?? new Date().toISOString().slice(0, 10),
  };
}

export async function listTasks(): Promise<PlanTask[]> {
  const tasks = await request<ApiTask[]>('/api/tasks/');
  return tasks.map(toPlanTask);
}

export async function createTask(task: Pick<PlanTask, 'title' | 'description' | 'assignee' | 'dueDate'>): Promise<PlanTask> {
  const payload = {
    title: task.title,
    description: task.description,
    status: 'backlog',
    assignee: task.assignee,
    due_date: task.dueDate,
  };
  const created = await request<ApiTask>('/api/tasks/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return toPlanTask(created);
}

export async function updateTaskStatus(taskId: string, status: TaskStatus): Promise<PlanTask> {
  const updated = await request<ApiTask>(`/api/tasks/${taskId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ status: toApiStatus(status) }),
  });
  return toPlanTask(updated);
}

interface ApiMessage {
  id: number;
  title: string;
  task_id: number | null;
  author: string;
  created_at: string;
}

function toDiscussionItem(message: ApiMessage): DiscussionItem {
  const text = message.title ?? '';
  const mentions = Array.from(new Set((text.match(/@\\w+/g) ?? []).map((token) => token.slice(1))));
  return {
    id: String(message.id),
    taskId: message.task_id ? String(message.task_id) : '',
    author: message.author,
    message: text,
    mentions,
    createdAt: message.created_at.slice(0, 10),
  };
}

export async function listDiscussions(): Promise<DiscussionItem[]> {
  const messages = await request<ApiMessage[]>('/api/messages/');
  return messages.map(toDiscussionItem);
}

export async function createDiscussion(payload: { taskId: string; author: string; message: string }): Promise<DiscussionItem> {
  const created = await request<ApiMessage>('/api/messages/', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.message,
      task_id: payload.taskId ? Number(payload.taskId) : null,
      author: payload.author,
    }),
  });
  return toDiscussionItem(created);
}
"""

    @staticmethod
    def _types_ts() -> str:
        return """export type TaskStatus = 'backlog' | 'inProgress' | 'done';

export interface PlanTask {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignee: string;
  dueDate: string;
}

export interface SessionItem {
  id: string;
  title: string;
  date: string;
  mode: 'video' | 'in-person';
  requestedBy: 'coach' | 'coachee';
}

export interface DiscussionItem {
  id: string;
  taskId: string;
  author: string;
  message: string;
  mentions: string[];
  createdAt: string;
}

export interface InsightItem {
  id: string;
  author: string;
  note: string;
  createdAt: string;
}

export interface ResourceItem {
  id: string;
  title: string;
  category: 'guide' | 'worksheet' | 'link';
  scope: 'plan' | 'shared';
}
"""

    def _seed_ts(self, requirements: ParsedRequirements) -> str:
        title = self._escape(requirements.title)
        return f"""import type {{ DiscussionItem, InsightItem, PlanTask, ResourceItem, SessionItem }} from '../types';

export const requirementTitle = '{title}';

export const initialTasks: PlanTask[] = [
  {{ id: 'task-1', title: 'Define coaching goal and milestones', description: 'Break goal into sequenced actions.', status: 'backlog', assignee: 'Coachee', dueDate: '2026-07-01' }},
  {{ id: 'task-2', title: 'Prepare coaching session agenda', description: 'Align outcomes and expectations.', status: 'inProgress', assignee: 'Coach', dueDate: '2026-06-20' }},
  {{ id: 'task-3', title: 'Capture progress insights', description: 'Document insights and next actions.', status: 'done', assignee: 'Coach', dueDate: '2026-06-12' }},
];

export const initialSessions: SessionItem[] = [
  {{ id: 'session-1', title: 'Weekly Coaching Session', date: '2026-06-18T14:00', mode: 'video', requestedBy: 'coachee' }},
  {{ id: 'session-2', title: 'Plan Review', date: '2026-06-25T10:00', mode: 'in-person', requestedBy: 'coach' }},
];

export const initialDiscussions: DiscussionItem[] = [
  {{ id: 'discussion-1', taskId: 'task-2', author: 'Coachee', message: '@Coach can we adjust this action priority?', mentions: ['Coach'], createdAt: '2026-06-14' }},
  {{ id: 'discussion-2', taskId: 'task-2', author: 'Coach', message: '@Coachee yes, move outreach to this week.', mentions: ['Coachee'], createdAt: '2026-06-14' }},
];

export const initialInsights: InsightItem[] = [
  {{ id: 'insight-1', author: 'Coach', note: 'Confidence increases when tasks are clearly scoped.', createdAt: '2026-06-10' }},
  {{ id: 'insight-2', author: 'Coachee', note: 'Morning planning sessions improve execution.', createdAt: '2026-06-11' }},
];

export const initialResources: ResourceItem[] = [
  {{ id: 'resource-1', title: 'Goal decomposition worksheet', category: 'worksheet', scope: 'plan' }},
  {{ id: 'resource-2', title: 'Feedback conversation guide', category: 'guide', scope: 'shared' }},
  {{ id: 'resource-3', title: 'Weekly reflection template', category: 'guide', scope: 'shared' }},
];
"""

    def _app_tsx(self, requirements: ParsedRequirements, features: FeatureSet) -> str:
        summary = requirements.summary[0] if requirements.summary else "Generated from requirements input"
        return f"""import {{ useEffect, useMemo, useState }} from 'react';
import {{ DiscussionPanel }} from './components/DiscussionPanel';
import {{ InsightsJournal }} from './components/InsightsJournal';
import {{ KanbanBoard }} from './components/KanbanBoard';
import {{ ResourceLibrary }} from './components/ResourceLibrary';
import {{ SessionPlanner }} from './components/SessionPlanner';
      import {{ createDiscussion, createTask, listDiscussions, listTasks, updateTaskStatus }} from './api';
import {{
  initialDiscussions,
  initialInsights,
  initialResources,
  initialSessions,
  initialTasks,
  requirementTitle,
}} from './data/seed';
import type {{ DiscussionItem, InsightItem, PlanTask, ResourceItem, SessionItem, TaskStatus }} from './types';

const MODULES = [
  {{ key: 'planning', label: 'Planning Board', enabled: {str(features.planning_board).lower()} }},
  {{ key: 'sessions', label: 'Sessions', enabled: {str(features.sessions).lower()} }},
  {{ key: 'discussions', label: 'Discussions', enabled: {str(features.discussions).lower()} }},
  {{ key: 'insights', label: 'Insights & Journal', enabled: {str(features.insights).lower()} }},
  {{ key: 'resources', label: 'Resources', enabled: {str(features.resources).lower()} }},
] as const;

type ModuleKey = (typeof MODULES)[number]['key'];

export default function App() {{
  const enabledModules = useMemo(() => MODULES.filter((item) => item.enabled), []);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'planning');

  const [tasks, setTasks] = useState<PlanTask[]>(initialTasks);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionItem[]>(initialSessions);
  const [discussions, setDiscussions] = useState<DiscussionItem[]>(initialDiscussions);
  const [discussionsError, setDiscussionsError] = useState<string | null>(null);
  const [insights, setInsights] = useState<InsightItem[]>(initialInsights);
  const [resources, setResources] = useState<ResourceItem[]>(initialResources);

  useEffect(() => {{
    let cancelled = false;
    (async () => {{
      try {{
        const persisted = await listTasks();
        if (!cancelled) {{
          setTasks(persisted);
          setTasksError(null);
        }}
      }} catch {{
        if (!cancelled) {{
          setTasks(initialTasks);
          setTasksError('Showing local tasks. Backend task API is unavailable.');
        }}
      }} finally {{
        if (!cancelled) {{
          setTasksLoading(false);
        }}
      }}
    }})();
    return () => {{
      cancelled = true;
    }};
  }}, []);

  useEffect(() => {{
    let cancelled = false;
    (async () => {{
      try {{
        const persisted = await listDiscussions();
        if (!cancelled) {{
          setDiscussions(persisted);
          setDiscussionsError(null);
        }}
      }} catch {{
        if (!cancelled) {{
          setDiscussions(initialDiscussions);
          setDiscussionsError('Showing local discussions. Backend discussion API is unavailable.');
        }}
      }}
    }})();
    return () => {{
      cancelled = true;
    }};
  }}, []);

  async function handleMoveTask(taskId: string, status: TaskStatus): Promise<void> {{
    const previous = tasks;
    setTasks((current) => current.map((task) => (task.id === taskId ? {{ ...task, status }} : task)));
    try {{
      const updated = await updateTaskStatus(taskId, status);
      setTasks((current) => current.map((task) => (task.id === taskId ? updated : task)));
      setTasksError(null);
    }} catch {{
      setTasks(previous);
      setTasksError('Unable to save task status. Please try again.');
    }}
  }}

  async function handleAddTask(task: PlanTask): Promise<void> {{
    try {{
      const created = await createTask({{
        title: task.title,
        description: task.description,
        assignee: task.assignee,
        dueDate: task.dueDate,
      }});
      setTasks((current) => [created, ...current]);
      setTasksError(null);
    }} catch {{
      setTasksError('Unable to save new task. Please try again.');
    }}
  }}

  async function handleAddDiscussion(discussion: DiscussionItem): Promise<void> {{
    try {{
      const created = await createDiscussion({{
        taskId: discussion.taskId,
        author: discussion.author,
        message: discussion.message,
      }});
      setDiscussions((current) => [created, ...current]);
      setDiscussionsError(null);
    }} catch {{
      setDiscussionsError('Unable to save discussion. Please try again.');
    }}
  }}

  return (
    <main className='app-shell'>
      <header className='hero'>
        <p className='eyebrow'>Frontend Developer Agent Output</p>
        <h1>{{requirementTitle}}</h1>
        <p className='subtitle'>{self._escape(summary)}</p>
      </header>

      <nav className='module-tabs' aria-label='Feature modules'>
        {{enabledModules.map((module) => (
          <button
            key={{module.key}}
            className={{module.key === activeModule ? 'tab active' : 'tab'}}
            onClick={{() => setActiveModule(module.key)}}
            type='button'
          >
            {{module.label}}
          </button>
        ))}}
      </nav>

      <section className='workspace'>
        {{activeModule === 'planning' && (
          <>
            {{tasksLoading && <p className='muted'>Loading tasks...</p>}}
            {{tasksError && <p className='muted'>{{tasksError}}</p>}}
            <KanbanBoard
              tasks={{tasks}}
              onMoveTask={{(taskId: string, status: TaskStatus) => {{
                void handleMoveTask(taskId, status);
              }}}}
              onAddTask={{(task: PlanTask) => {{
                void handleAddTask(task);
              }}}}
            />
          </>
        )}}

        {{activeModule === 'sessions' && (
          <SessionPlanner
            sessions={{sessions}}
            onAddSession={{(session: SessionItem) => setSessions((current) => [session, ...current])}}
          />
        )}}

        {{activeModule === 'discussions' && (
          <>
            {{discussionsError && <p className='muted'>{{discussionsError}}</p>}}
            <DiscussionPanel
              discussions={{discussions}}
              tasks={{tasks}}
              onAddDiscussion={{(discussion: DiscussionItem) => {{
                void handleAddDiscussion(discussion);
              }}}}
            />
          </>
        )}}

        {{activeModule === 'insights' && (
          <InsightsJournal
            insights={{insights}}
            onAddInsight={{(insight: InsightItem) => setInsights((current) => [insight, ...current])}}
          />
        )}}

        {{activeModule === 'resources' && (
          <ResourceLibrary
            resources={{resources}}
            onAddResource={{(resource: ResourceItem) => setResources((current) => [resource, ...current])}}
          />
        )}}
      </section>
    </main>
  );
}}
"""

    @staticmethod
    def _styles_css() -> str:
        return """:root {
  --bg: #eef5f4;
  --panel: #ffffff;
  --text: #1f2b2a;
  --accent: #0b766e;
  --muted: #5d7472;
  --line: #d3e1df;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  color: var(--text);
  background: radial-gradient(circle at top left, #d8eeea, var(--bg));
}

.app-shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 2rem 1rem 3rem;
}

.hero h1 { margin: 0.35rem 0 0.5rem; }
.eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--accent);
  font-weight: 700;
}
.subtitle { color: var(--muted); max-width: 72ch; }

.module-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 1rem 0 1.2rem;
}

.tab {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--text);
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
  cursor: pointer;
  font-size: 0.92rem;
}
.tab.active {
  border-color: var(--accent);
  color: #fff;
  background: var(--accent);
}

.workspace {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 1rem;
  box-shadow: 0 12px 24px rgba(27, 56, 52, 0.08);
}

.card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.8rem;
  background: #fff;
  margin-bottom: 0.8rem;
}

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}
@media (max-width: 960px) {
  .grid-3 { grid-template-columns: 1fr; }
}

.muted { color: var(--muted); font-size: 0.9rem; }
label { display: block; font-weight: 600; margin-top: 0.6rem; }
input, select, textarea {
  width: 100%;
  margin-top: 0.35rem;
  border: 1px solid #c7d8d6;
  border-radius: 8px;
  padding: 0.5rem 0.6rem;
  font: inherit;
}

button.primary {
  margin-top: 0.8rem;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  border-radius: 8px;
  padding: 0.5rem 0.8rem;
  cursor: pointer;
}

.list { margin: 0.8rem 0 0; padding-left: 1.15rem; }
.list li + li { margin-top: 0.45rem; }
"""

    @staticmethod
    def _kanban_board_tsx() -> str:
        return """import { useMemo, useState } from 'react';
import type { PlanTask, TaskStatus } from '../types';

interface KanbanBoardProps {
  tasks: PlanTask[];
  onMoveTask: (taskId: string, status: TaskStatus) => void;
  onAddTask: (task: PlanTask) => void;
}

const STATUS_LABEL: Record<TaskStatus, string> = {
  backlog: 'Backlog',
  inProgress: 'In Progress',
  done: 'Done',
};

export function KanbanBoard({ tasks, onMoveTask, onAddTask }: KanbanBoardProps) {
  const [title, setTitle] = useState('');
  const [assignee, setAssignee] = useState('Coachee');
  const [description, setDescription] = useState('');

  const grouped = useMemo(
    () => ({
      backlog: tasks.filter((task) => task.status === 'backlog'),
      inProgress: tasks.filter((task) => task.status === 'inProgress'),
      done: tasks.filter((task) => task.status === 'done'),
    }),
    [tasks],
  );

  return (
    <div>
      <h2>Planning Board</h2>
      <p className='muted'>Manage coaching plan actions on a kanban board with clear ownership.</p>
      <div className='card'>
        <h3>Add task</h3>
        <label>Task title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>
          Assignee
          <select value={assignee} onChange={(event) => setAssignee(event.target.value)}>
            <option>Coachee</option>
            <option>Coach</option>
          </select>
        </label>
        <label>Description<textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = title.trim();
            if (!trimmed) return;
            onAddTask({
              id: `task-${Date.now()}`,
              title: trimmed,
              description: description.trim() || 'No description provided.',
              status: 'backlog',
              assignee,
              dueDate: new Date().toISOString().slice(0, 10),
            });
            setTitle('');
            setDescription('');
          }}
        >
          Add task
        </button>
      </div>

      <div className='grid-3'>
        {(Object.keys(grouped) as TaskStatus[]).map((status) => (
          <div className='card' key={status}>
            <h3>{STATUS_LABEL[status]}</h3>
            <ul className='list'>
              {grouped[status].map((task) => (
                <li key={task.id}>
                  <strong>{task.title}</strong>
                  <div className='muted'>{task.assignee} · due {task.dueDate}</div>
                  <div>{task.description}</div>
                  <label>
                    Move to
                    <select value={task.status} onChange={(event) => onMoveTask(task.id, event.target.value as TaskStatus)}>
                      <option value='backlog'>Backlog</option>
                      <option value='inProgress'>In Progress</option>
                      <option value='done'>Done</option>
                    </select>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
"""

    @staticmethod
    def _session_planner_tsx() -> str:
        return """import { useState } from 'react';
import type { SessionItem } from '../types';

interface SessionPlannerProps {
  sessions: SessionItem[];
  onAddSession: (session: SessionItem) => void;
}

export function SessionPlanner({ sessions, onAddSession }: SessionPlannerProps) {
  const [title, setTitle] = useState('Coaching Session');
  const [date, setDate] = useState('');
  const [mode, setMode] = useState<'video' | 'in-person'>('video');
  const [requestedBy, setRequestedBy] = useState<'coach' | 'coachee'>('coachee');

  return (
    <div>
      <h2>Session Scheduling</h2>
      <p className='muted'>Capture upcoming coaching sessions and availability decisions.</p>
      <div className='card'>
        <h3>Request a session</h3>
        <label>Session title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>Date and time<input type='datetime-local' value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <label>
          Mode
          <select value={mode} onChange={(event) => setMode(event.target.value as 'video' | 'in-person')}>
            <option value='video'>Video</option>
            <option value='in-person'>In person</option>
          </select>
        </label>
        <label>
          Requested by
          <select value={requestedBy} onChange={(event) => setRequestedBy(event.target.value as 'coach' | 'coachee')}>
            <option value='coachee'>Coachee</option>
            <option value='coach'>Coach</option>
          </select>
        </label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            if (!date) return;
            onAddSession({ id: `session-${Date.now()}`, title: title.trim() || 'Coaching Session', date, mode, requestedBy });
          }}
        >
          Add session
        </button>
      </div>

      <div className='card'>
        <h3>Upcoming sessions</h3>
        <ul className='list'>
          {sessions.map((session) => (
            <li key={session.id}>
              <strong>{session.title}</strong>
              <div className='muted'>{new Date(session.date).toLocaleString()} · {session.mode} · requested by {session.requestedBy}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
"""

    @staticmethod
    def _discussion_panel_tsx() -> str:
        return """import { useState } from 'react';
import type { DiscussionItem, PlanTask } from '../types';

interface DiscussionPanelProps {
  discussions: DiscussionItem[];
  tasks: PlanTask[];
  onAddDiscussion: (discussion: DiscussionItem) => void;
}

export function DiscussionPanel({ discussions, tasks, onAddDiscussion }: DiscussionPanelProps) {
  const [taskId, setTaskId] = useState(tasks[0]?.id ?? '');
  const [author, setAuthor] = useState('Coachee');
  const [message, setMessage] = useState('');

  return (
    <div>
      <h2>Task Discussions</h2>
      <p className='muted'>Discuss task progress, ask for help, and trigger @mention notifications.</p>
      <div className='card'>
        <h3>Add discussion entry</h3>
        <label>
          Task
          <select value={taskId} onChange={(event) => setTaskId(event.target.value)}>
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>{task.title}</option>
            ))}
          </select>
        </label>
        <label>
          Author
          <select value={author} onChange={(event) => setAuthor(event.target.value)}>
            <option>Coach</option>
            <option>Coachee</option>
          </select>
        </label>
        <label>Message<textarea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} /></label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = message.trim();
            if (!trimmed || !taskId) return;
            const mentions = Array.from(new Set((trimmed.match(/@\\w+/g) ?? []).map((token) => token.slice(1))));
            onAddDiscussion({
              id: `discussion-${Date.now()}`,
              taskId,
              author,
              message: trimmed,
              mentions,
              createdAt: new Date().toISOString().slice(0, 10),
            });
            setMessage('');
          }}
        >
          Post discussion
        </button>
      </div>

      <div className='card'>
        <h3>Thread</h3>
        <ul className='list'>
          {discussions.map((discussion) => (
            <li key={discussion.id}>
              <strong>{discussion.author}</strong> on {discussion.createdAt}
              <div>{discussion.message}</div>
              <div className='muted'>Mentions: {discussion.mentions.length ? discussion.mentions.join(', ') : 'None'}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
"""

    @staticmethod
    def _insights_journal_tsx() -> str:
        return """import { useState } from 'react';
import type { InsightItem } from '../types';

interface InsightsJournalProps {
  insights: InsightItem[];
  onAddInsight: (insight: InsightItem) => void;
}

export function InsightsJournal({ insights, onAddInsight }: InsightsJournalProps) {
  const [author, setAuthor] = useState('Coach');
  const [note, setNote] = useState('');

  return (
    <div>
      <h2>Insights and Journal</h2>
      <p className='muted'>Track coach insights and coachee reflections in chronological order.</p>
      <div className='card'>
        <h3>Add insight</h3>
        <label>
          Author
          <select value={author} onChange={(event) => setAuthor(event.target.value)}>
            <option>Coach</option>
            <option>Coachee</option>
          </select>
        </label>
        <label>Note<textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} /></label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = note.trim();
            if (!trimmed) return;
            onAddInsight({ id: `insight-${Date.now()}`, author, note: trimmed, createdAt: new Date().toISOString().slice(0, 10) });
            setNote('');
          }}
        >
          Save note
        </button>
      </div>

      <div className='card'>
        <h3>Timeline</h3>
        <ul className='list'>
          {insights.map((insight) => (
            <li key={insight.id}>
              <strong>{insight.author}</strong> · {insight.createdAt}
              <div>{insight.note}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
"""

    @staticmethod
    def _resource_library_tsx() -> str:
        return """import { useMemo, useState } from 'react';
import type { ResourceItem } from '../types';

interface ResourceLibraryProps {
  resources: ResourceItem[];
  onAddResource: (resource: ResourceItem) => void;
}

export function ResourceLibrary({ resources, onAddResource }: ResourceLibraryProps) {
  const [query, setQuery] = useState('');
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<'guide' | 'worksheet' | 'link'>('guide');
  const [scope, setScope] = useState<'plan' | 'shared'>('shared');

  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();
    if (!lowered) return resources;
    return resources.filter((resource) => resource.title.toLowerCase().includes(lowered));
  }, [query, resources]);

  return (
    <div>
      <h2>Resource Library</h2>
      <p className='muted'>Manage shared and plan-specific resources exchanged between coach and coachee.</p>
      <div className='card'>
        <h3>Add resource</h3>
        <label>Title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>
          Category
          <select value={category} onChange={(event) => setCategory(event.target.value as 'guide' | 'worksheet' | 'link')}>
            <option value='guide'>Guide</option>
            <option value='worksheet'>Worksheet</option>
            <option value='link'>Link</option>
          </select>
        </label>
        <label>
          Scope
          <select value={scope} onChange={(event) => setScope(event.target.value as 'plan' | 'shared')}>
            <option value='shared'>Shared</option>
            <option value='plan'>Plan specific</option>
          </select>
        </label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = title.trim();
            if (!trimmed) return;
            onAddResource({ id: `resource-${Date.now()}`, title: trimmed, category, scope });
            setTitle('');
          }}
        >
          Add resource
        </button>
      </div>

      <div className='card'>
        <h3>Available resources</h3>
        <label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <ul className='list'>
          {filtered.map((resource) => (
            <li key={resource.id}>
              <strong>{resource.title}</strong>
              <div className='muted'>{resource.category} · {resource.scope}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
    description="(Deprecated) Generate frontend scaffold directly. Prefer agents/developer_agent.py for end-to-end runs."
    )
    parser.add_argument("--requirements-file", required=True, help="Path to markdown created by requirements_agent.py")
    parser.add_argument("--output", default="generated/frontend-app", help="Output directory for generated frontend code")
    parser.add_argument("--project-name", default="frontend-app", help="Package/project name")
    parser.add_argument(
        "--self-doc-output",
        default="",
        help="Optional markdown path for the agent to refresh its own documentation.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    print(
        "WARNING: frontend_developer_agent.py is deprecated for direct use. "
        "Use agents/developer_agent.py for end-to-end implementation.",
        file=sys.stderr,
    )
    requirements_path = Path(args.requirements_file)
    markdown = requirements_path.read_text(encoding="utf-8")

    agent = FrontendDeveloperAgent()
    requirements = agent.parse_requirements_markdown(markdown)
    result = agent.build_from_requirements(
        requirements=requirements,
        output_dir=args.output,
        project_name=args.project_name,
    )

    default_doc_path = Path(__file__).resolve().parents[1] / "docs" / "frontend-developer-agent.md"
    doc_path = Path(args.self_doc_output) if args.self_doc_output else default_doc_path
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(agent.self_documentation_markdown(), encoding="utf-8")

    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
