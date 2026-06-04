import { useMemo, useState } from 'react';
import { DiscussionPanel } from './components/DiscussionPanel';
import { InsightsJournal } from './components/InsightsJournal';
import { KanbanBoard } from './components/KanbanBoard';
import { ResourceLibrary } from './components/ResourceLibrary';
import { SessionPlanner } from './components/SessionPlanner';
import {
  initialDiscussions,
  initialInsights,
  initialResources,
  initialSessions,
  initialTasks,
  requirementTitle,
} from './data/seed';
import type { DiscussionItem, InsightItem, PlanTask, ResourceItem, SessionItem, TaskStatus } from './types';

const MODULES = [
  { key: 'planning', label: 'Planning Board', enabled: true },
  { key: 'sessions', label: 'Sessions', enabled: true },
  { key: 'discussions', label: 'Discussions', enabled: true },
  { key: 'insights', label: 'Insights & Journal', enabled: true },
  { key: 'resources', label: 'Resources', enabled: true },
] as const;

type ModuleKey = (typeof MODULES)[number]['key'];

export default function App() {
  const enabledModules = useMemo(() => MODULES.filter((item) => item.enabled), []);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'planning');

  const [tasks, setTasks] = useState<PlanTask[]>(initialTasks);
  const [sessions, setSessions] = useState<SessionItem[]>(initialSessions);
  const [discussions, setDiscussions] = useState<DiscussionItem[]>(initialDiscussions);
  const [insights, setInsights] = useState<InsightItem[]>(initialInsights);
  const [resources, setResources] = useState<ResourceItem[]>(initialResources);

  return (
    <main className='app-shell'>
      <header className='hero'>
        <p className='eyebrow'>Frontend Developer Agent Output</p>
        <h1>{requirementTitle}</h1>
        <p className='subtitle'>Coachees can request coaching sessions with a coach and sync them with Microsoft Outlook and Google Calendar so that session bookings stay aligned with preferred calendar tools.</p>
      </header>

      <nav className='module-tabs' aria-label='Feature modules'>
        {enabledModules.map((module) => (
          <button
            key={module.key}
            className={module.key === activeModule ? 'tab active' : 'tab'}
            onClick={() => setActiveModule(module.key)}
            type='button'
          >
            {module.label}
          </button>
        ))}
      </nav>

      <section className='workspace'>
        {activeModule === 'planning' && (
          <KanbanBoard
            tasks={tasks}
            onMoveTask={(taskId: string, status: TaskStatus) =>
              setTasks((current) => current.map((task) => (task.id === taskId ? { ...task, status } : task)))
            }
            onAddTask={(task: PlanTask) => setTasks((current) => [task, ...current])}
          />
        )}

        {activeModule === 'sessions' && (
          <SessionPlanner
            sessions={sessions}
            onAddSession={(session: SessionItem) => setSessions((current) => [session, ...current])}
          />
        )}

        {activeModule === 'discussions' && (
          <DiscussionPanel
            discussions={discussions}
            tasks={tasks}
            onAddDiscussion={(discussion: DiscussionItem) => setDiscussions((current) => [discussion, ...current])}
          />
        )}

        {activeModule === 'insights' && (
          <InsightsJournal
            insights={insights}
            onAddInsight={(insight: InsightItem) => setInsights((current) => [insight, ...current])}
          />
        )}

        {activeModule === 'resources' && (
          <ResourceLibrary
            resources={resources}
            onAddResource={(resource: ResourceItem) => setResources((current) => [resource, ...current])}
          />
        )}
      </section>
    </main>
  );
}
