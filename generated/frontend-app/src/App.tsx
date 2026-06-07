import { useEffect, useMemo, useState } from 'react';
import { clearToken, createItem, getToken, listItems } from './api';
import { DiscussionPanel } from './components/DiscussionPanel';
import { InsightsJournal } from './components/InsightsJournal';
import { KanbanBoard } from './components/KanbanBoard';
import { LoginScreen } from './components/LoginScreen';
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

// Map backend items to frontend types using seed shapes as defaults
function toTask(item: { id: number; title: string; description?: string }): PlanTask {
  return {
    id: String(item.id),
    title: item.title,
    description: item.description ?? '',
    status: 'backlog',
    assignee: 'Coachee',
    dueDate: new Date().toISOString().slice(0, 10),
  };
}

function toSession(item: { id: number; title: string; description?: string }): SessionItem {
  return {
    id: String(item.id),
    title: item.title,
    date: new Date().toISOString(),
    mode: 'video',
    requestedBy: 'coachee',
  };
}

function toDiscussion(item: { id: number; title: string; description?: string }): DiscussionItem {
  return {
    id: String(item.id),
    taskId: '',
    author: 'Coach',
    message: item.title,
    mentions: [],
    createdAt: new Date().toISOString().slice(0, 10),
  };
}

function toInsight(item: { id: number; title: string; description?: string }): InsightItem {
  return {
    id: String(item.id),
    author: 'Coach',
    note: item.title,
    createdAt: new Date().toISOString().slice(0, 10),
  };
}

function toResource(item: { id: number; title: string; description?: string }): ResourceItem {
  return {
    id: String(item.id),
    title: item.title,
    category: 'guide',
    scope: 'shared',
  };
}

export default function App() {
  const [username, setUsername] = useState<string | null>(getToken() ? 'user' : null);
  const [apiError, setApiError] = useState<string | null>(null);

  const enabledModules = useMemo(() => MODULES.filter((item) => item.enabled), []);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'planning');

  const [tasks, setTasks] = useState<PlanTask[]>(initialTasks);
  const [sessions, setSessions] = useState<SessionItem[]>(initialSessions);
  const [discussions, setDiscussions] = useState<DiscussionItem[]>(initialDiscussions);
  const [insights, setInsights] = useState<InsightItem[]>(initialInsights);
  const [resources, setResources] = useState<ResourceItem[]>(initialResources);

  // Load all data from the backend when authenticated
  useEffect(() => {
    if (!username) return;

    async function loadAll() {
      try {
        const [apiTasks, apiSessions, apiMessages, apiInsights, apiResources] = await Promise.all([
          listItems('tasks').catch(() => [] as Awaited<ReturnType<typeof listItems>>),
          listItems('sessions').catch(() => [] as Awaited<ReturnType<typeof listItems>>),
          listItems('messages').catch(() => [] as Awaited<ReturnType<typeof listItems>>),
          listItems('insights').catch(() => [] as Awaited<ReturnType<typeof listItems>>),
          listItems('resources').catch(() => [] as Awaited<ReturnType<typeof listItems>>),
        ]);
        if (apiTasks.length) setTasks(apiTasks.map(toTask));
        if (apiSessions.length) setSessions(apiSessions.map(toSession));
        if (apiMessages.length) setDiscussions(apiMessages.map(toDiscussion));
        if (apiInsights.length) setInsights(apiInsights.map(toInsight));
        if (apiResources.length) setResources(apiResources.map(toResource));
      } catch (err) {
        setApiError(err instanceof Error ? err.message : 'Failed to load data from backend');
      }
    }
    void loadAll();
  }, [username]);

  if (!username) {
    return <LoginScreen onAuthenticated={(name) => setUsername(name)} />;
  }

  return (
    <main className='app-shell'>
      <header className='hero'>
        <p className='eyebrow'>Coaching Platform</p>
        <h1>{requirementTitle}</h1>
        <p className='subtitle'>
          Coachees can request coaching sessions with a coach and sync them with Microsoft Outlook and Google Calendar.
        </p>
        <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
          <span className='muted' style={{ fontSize: 13 }}>Signed in as <strong>{username}</strong></span>
          <button
            type='button'
            style={{ fontSize: 12, padding: '2px 10px' }}
            onClick={() => { clearToken(); setUsername(null); }}
          >
            Sign out
          </button>
        </div>
        {apiError && <p style={{ color: '#c0392b', fontSize: 13, marginTop: 4 }}>Backend: {apiError}</p>}
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
            onAddTask={async (task: PlanTask) => {
              try {
                const saved = await createItem('tasks', { title: task.title, description: task.description });
                setTasks((current) => [{ ...task, id: String(saved.id) }, ...current]);
              } catch {
                setTasks((current) => [task, ...current]);
              }
            }}
          />
        )}

        {activeModule === 'sessions' && (
          <SessionPlanner
            sessions={sessions}
            onAddSession={async (session: SessionItem) => {
              try {
                const saved = await createItem('sessions', { title: session.title, description: session.mode });
                setSessions((current) => [{ ...session, id: String(saved.id) }, ...current]);
              } catch {
                setSessions((current) => [session, ...current]);
              }
            }}
          />
        )}

        {activeModule === 'discussions' && (
          <DiscussionPanel
            discussions={discussions}
            tasks={tasks}
            onAddDiscussion={async (discussion: DiscussionItem) => {
              try {
                const saved = await createItem('messages', { title: discussion.message });
                setDiscussions((current) => [{ ...discussion, id: String(saved.id) }, ...current]);
              } catch {
                setDiscussions((current) => [discussion, ...current]);
              }
            }}
          />
        )}

        {activeModule === 'insights' && (
          <InsightsJournal
            insights={insights}
            onAddInsight={async (insight: InsightItem) => {
              try {
                const saved = await createItem('insights', { title: insight.note });
                setInsights((current) => [{ ...insight, id: String(saved.id) }, ...current]);
              } catch {
                setInsights((current) => [insight, ...current]);
              }
            }}
          />
        )}

        {activeModule === 'resources' && (
          <ResourceLibrary
            resources={resources}
            onAddResource={async (resource: ResourceItem) => {
              try {
                const saved = await createItem('resources', { title: resource.title, description: resource.category });
                setResources((current) => [{ ...resource, id: String(saved.id) }, ...current]);
              } catch {
                setResources((current) => [resource, ...current]);
              }
            }}
          />
        )}
      </section>
    </main>
  );
}



