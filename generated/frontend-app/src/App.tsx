import { useEffect, useMemo, useState } from 'react';
import { DiscussionPanel } from './components/DiscussionPanel';
import { InsightsJournal } from './components/InsightsJournal';
import { KanbanBoard } from './components/KanbanBoard';
import { ResourceLibrary } from './components/ResourceLibrary';
import { SessionPlanner } from './components/SessionPlanner';
import { PlanList } from './components/PlanList';
import { PlanDetail } from './components/PlanDetail';
import { CoacheesManager } from './components/CoacheesManager';
      import { createDiscussion, createTask, listDiscussions, listTasks, updateTaskStatus } from './api';
import { createPlan, listCoachees, listPlans } from './api';
import {
  initialDiscussions,
  initialInsights,
  initialResources,
  initialSessions,
  initialTasks,
  requirementTitle,
} from './data/seed';
import type { DiscussionItem, InsightItem, PlanTask, ResourceItem, SessionItem, TaskStatus } from './types';
import type { Coachee, CoachingPlan } from './types';

const MODULES = [
  { key: 'plans', label: 'Coaching Plans', enabled: true },
  { key: 'coachees', label: 'Coachees', enabled: true },
  { key: 'sessions', label: 'Sessions', enabled: false },
  { key: 'discussions', label: 'Discussions', enabled: true },
  { key: 'insights', label: 'Insights & Journal', enabled: false },
  { key: 'resources', label: 'Resources', enabled: false },
] as const;

type ModuleKey = (typeof MODULES)[number]['key'];

export default function App() {
  const enabledModules = useMemo(() => MODULES.filter((item) => item.enabled), []);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'planning');

  const [tasks, setTasks] = useState<PlanTask[]>(initialTasks);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksError, setTasksError] = useState<string | null>(null);
  const [plans, setPlans] = useState<CoachingPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<CoachingPlan | null>(null);
  const [coachees, setCoachees] = useState<Coachee[]>([]);
  const [coacheesLoading, setCoacheesLoading] = useState(true);
  const [coacheesError, setCoacheesError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionItem[]>(initialSessions);
  const [discussions, setDiscussions] = useState<DiscussionItem[]>(initialDiscussions);
  const [discussionsError, setDiscussionsError] = useState<string | null>(null);
  const [insights, setInsights] = useState<InsightItem[]>(initialInsights);
  const [resources, setResources] = useState<ResourceItem[]>(initialResources);

  useEffect(() => {
    let cancelled = false;
    setPlansLoading(true);
    listPlans()
      .then((data) => { if (!cancelled) { setPlans(data); setPlansError(null); } })
      .catch(() => { if (!cancelled) setPlansError('Could not load plans. Showing local data.'); })
      .finally(() => { if (!cancelled) setPlansLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setCoacheesLoading(true);
    listCoachees()
      .then((data) => { if (!cancelled) { setCoachees(data); setCoacheesError(null); } })
      .catch(() => { if (!cancelled) setCoacheesError('Could not load coachees.'); })
      .finally(() => { if (!cancelled) setCoacheesLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const persisted = await listTasks();
        if (!cancelled) {
          setTasks(persisted);
          setTasksError(null);
        }
      } catch {
        if (!cancelled) {
          setTasks(initialTasks);
          setTasksError('Showing local tasks. Backend task API is unavailable.');
        }
      } finally {
        if (!cancelled) {
          setTasksLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const persisted = await listDiscussions();
        if (!cancelled) {
          setDiscussions(persisted);
          setDiscussionsError(null);
        }
      } catch {
        if (!cancelled) {
          setDiscussions(initialDiscussions);
          setDiscussionsError('Showing local discussions. Backend discussion API is unavailable.');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreatePlan(planData: Omit<CoachingPlan, 'id' | 'createdAt' | 'coacheeName'>): Promise<void> {
    try {
      const created = await createPlan(planData);
      setPlans((prev) => [...prev, created].sort((a, b) => a.targetDate.localeCompare(b.targetDate)));
      setPlansError(null);
    } catch {
      setPlansError('Could not create plan. Please try again.');
    }
  }

  async function handleMoveTask(taskId: string, status: TaskStatus): Promise<void> {
    const previous = tasks;
    setTasks((current) => current.map((task) => (task.id === taskId ? { ...task, status } : task)));
    try {
      const updated = await updateTaskStatus(taskId, status);
      setTasks((current) => current.map((task) => (task.id === taskId ? updated : task)));
      setTasksError(null);
    } catch {
      setTasks(previous);
      setTasksError('Unable to save task status. Please try again.');
    }
  }

  async function handleAddTask(task: PlanTask): Promise<void> {
    try {
      const created = await createTask({
        title: task.title,
        description: task.description,
        assignee: task.assignee,
        dueDate: task.dueDate,
      });
      setTasks((current) => [created, ...current]);
      setTasksError(null);
    } catch {
      setTasksError('Unable to save new task. Please try again.');
    }
  }

  async function handleAddDiscussion(discussion: DiscussionItem): Promise<void> {
    try {
      const created = await createDiscussion({
        taskId: discussion.taskId,
        author: discussion.author,
        message: discussion.message,
      });
      setDiscussions((current) => [created, ...current]);
      setDiscussionsError(null);
    } catch {
      setDiscussionsError('Unable to save discussion. Please try again.');
    }
  }

  return (
    <main className='app-shell'>
      <header className='hero'>
        <p className='eyebrow'>Frontend Developer Agent Output</p>
        <h1>{requirementTitle}</h1>
        <p className='subtitle'>Coaches can create one to many coaching plans for a coachee.</p>
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
        {activeModule === 'plans' && !selectedPlan && (
          <PlanList
            plans={plans}
            coachees={coachees}
            onSelectPlan={setSelectedPlan}
            onCreatePlan={(data) => { void handleCreatePlan(data); }}
            loading={plansLoading}
            error={plansError}
          />
        )}

        {activeModule === 'plans' && selectedPlan && (
          <PlanDetail
            plan={selectedPlan}
            coachees={coachees}
            onBack={() => setSelectedPlan(null)}
          />
        )}

        {activeModule === 'coachees' && (
          <CoacheesManager
            coachees={coachees}
            onAdded={(c) => setCoachees((prev) => [...prev, c])}
            loading={coacheesLoading}
            error={coacheesError}
          />
        )}

        {activeModule === 'sessions' && (
          <SessionPlanner
            sessions={sessions}
            onAddSession={(session: SessionItem) => setSessions((current) => [session, ...current])}
          />
        )}

        {activeModule === 'discussions' && (
          <>
            {discussionsError && <p className='muted'>{discussionsError}</p>}
            <DiscussionPanel
              discussions={discussions}
              tasks={tasks}
              onAddDiscussion={(discussion: DiscussionItem) => {
                void handleAddDiscussion(discussion);
              }}
            />
          </>
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
