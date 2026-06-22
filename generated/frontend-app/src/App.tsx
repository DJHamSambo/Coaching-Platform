import { useEffect, useMemo, useState } from 'react';
import { PlanList } from './components/PlanList';
import { PlanDetail } from './components/PlanDetail';
import { CalendarPanel } from './components/CalendarPanel';
import { AdministrationPanel } from './components/AdministrationPanel';
import { InsightsJournal } from './components/InsightsJournal';
import { LoginScreen } from './components/LoginScreen';
import {
  clearToken,
  createInsight,
  createPlan,
  deleteInsight,
  getMe,
  getToken,
  listAdminCoachees,
  listCoachDirectory,
  listInsights,
  listPlans,
  updateInsight,
} from './api';
import { SESSION_EXPIRED_MESSAGE } from './constants/messages';
import { requirementTitle } from './data/seed';
import type { AdminCoachee, AdminCoach, CoachingPlan, CurrentUser, InsightItem } from './types';

const CALENDAR_FEATURE_ENABLED = import.meta.env.VITE_ENABLE_CALENDAR !== 'false';

const MODULES = [
  { key: 'plans', label: 'Coaching Plans', enabled: true },
  { key: 'insights', label: 'Insights', enabled: true },
  { key: 'calendar', label: 'Calendar', enabled: CALENDAR_FEATURE_ENABLED },
  { key: 'administration', label: 'Administration', enabled: true },
] as const;

type ModuleKey = (typeof MODULES)[number]['key'];

export default function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  const enabledModules = useMemo(() => 
    MODULES.filter((item) => {
      // Hide administration from coachees
      if (item.key === 'administration' && currentUser?.role === 'coachee') {
        return false;
      }
      return item.enabled;
    }), [currentUser?.role]);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'plans');

  const [plans, setPlans] = useState<CoachingPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<CoachingPlan | null>(null);

  const [coachees, setCoachees] = useState<AdminCoachee[]>([]);
  const [coaches, setCoaches] = useState<AdminCoach[]>([]);
  const [coacheesLoading, setCoacheesLoading] = useState(true);
  const [coacheesError, setCoacheesError] = useState<string | null>(null);

  const [insights, setInsights] = useState<InsightItem[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setAuthLoading(false);
      return () => {
        cancelled = true;
      };
    }

    getMe()
      .then((user) => {
        if (!cancelled) {
          setCurrentUser(user);
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearToken();
          setCurrentUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAuthLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function handleAuthExpired(): void {
      clearToken();
      setCurrentUser(null);
      setSelectedPlan(null);
      setActiveModule('plans');
      setPlansError(SESSION_EXPIRED_MESSAGE);
    }

    window.addEventListener('auth:expired', handleAuthExpired);
    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    let cancelled = false;
    setPlansLoading(true);
    listPlans()
      .then((data) => {
        if (!cancelled) {
          setPlans(data);
          setPlansError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setPlansError('Could not load plans.');
      })
      .finally(() => {
        if (!cancelled) setPlansLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser || activeModule !== 'insights') return;
    let cancelled = false;
    setInsightsLoading(true);
    listInsights()
      .then((items) => {
        if (!cancelled) {
          setInsights(items);
          setInsightsError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setInsightsError('Could not load insights.');
      })
      .finally(() => {
        if (!cancelled) setInsightsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeModule, currentUser]);

  useEffect(() => {
    if (!currentUser) return;
    let cancelled = false;
    setCoacheesLoading(true);
    Promise.all([listAdminCoachees(), listCoachDirectory()])
      .then(([coacheesData, coachesData]) => {
        if (!cancelled) {
          setCoachees(coacheesData);
          setCoaches(coachesData);
          setCoacheesError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setCoacheesError('Could not load coachees.');
      })
      .finally(() => {
        if (!cancelled) setCoacheesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  async function handleCreatePlan(planData: Omit<CoachingPlan, 'id' | 'createdAt' | 'coacheeName'>): Promise<void> {
    try {
      const created = await createPlan(planData);
      setPlans((prev) => [...prev, created].sort((a, b) => a.targetDate.localeCompare(b.targetDate)));
      setPlansError(null);
    } catch {
      setPlansError('Could not create plan. Please try again.');
    }
  }

  function handlePlanUpdated(updated: CoachingPlan): void {
    setPlans((prev) => prev.map((plan) => (plan.id === updated.id ? updated : plan)));
    setSelectedPlan(updated);
  }

  async function handleAddInsight(insight: InsightItem): Promise<void> {
    try {
      const created = await createInsight({ author: insight.author, note: insight.note, coacheeId: insight.coacheeId });
      setInsights((prev) => [created, ...prev]);
      setInsightsError(null);
    } catch {
      setInsightsError('Could not save insight. Please try again.');
    }
  }

  async function handleUpdateInsight(insightId: string, patch: { author: string; note: string; coacheeId?: string | null }): Promise<void> {
    try {
      const updated = await updateInsight(insightId, patch);
      setInsights((prev) => prev.map((item) => (item.id === insightId ? updated : item)));
      setInsightsError(null);
    } catch {
      setInsightsError('Could not update insight. Please try again.');
    }
  }

  async function handleDeleteInsight(insightId: string): Promise<void> {
    try {
      await deleteInsight(insightId);
      setInsights((prev) => prev.filter((item) => item.id !== insightId));
      setInsightsError(null);
    } catch {
      setInsightsError('Could not delete insight. Please try again.');
    }
  }

  async function handleAuthenticated(): Promise<void> {
    try {
      const user = await getMe();
      setCurrentUser(user);
      setActiveModule('plans');
    } catch {
      setCurrentUser(null);
    }
    setAuthLoading(false);
  }

  function handleLogout(): void {
    clearToken();
    setCurrentUser(null);
    setSelectedPlan(null);
    setActiveModule('plans');
  }

  if (authLoading) {
    return (
      <main className='app-shell'>
        <p className='muted'>Loading session...</p>
      </main>
    );
  }

  if (!currentUser) {
    return <LoginScreen onAuthenticated={() => { void handleAuthenticated(); }} />;
  }

  return (
    <main className='app-shell'>
      <header className='hero'>
        <p className='eyebrow'>Frontend Developer Agent Output</p>
        <h1>{requirementTitle}</h1>
        <p className='subtitle'>Coaches can create one to many coaching plans for a coachee.</p>
        <p className='muted' style={{ marginTop: 8 }}>
          Signed in as {currentUser.username} ({currentUser.role})
        </p>
        <button type='button' onClick={handleLogout} style={{ marginTop: 8 }}>
          Sign out
        </button>
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
            onCreatePlan={(data) => {
              void handleCreatePlan(data);
            }}
            canCreatePlan={currentUser.role !== 'coachee'}
            loading={plansLoading}
            error={plansError}
          />
        )}

        {activeModule === 'plans' && selectedPlan && (
          <PlanDetail
            plan={selectedPlan}
            coachees={coachees}
            coaches={coaches}
            currentUser={currentUser}
            onBack={() => setSelectedPlan(null)}
            onPlanUpdated={handlePlanUpdated}
          />
        )}

        {activeModule === 'calendar' && <CalendarPanel coachees={coachees} currentUser={currentUser} />}

        {activeModule === 'insights' && (
          <>
            {insightsLoading && <p className='muted'>Loading insights...</p>}
            {insightsError && <p className='muted' role='alert'>{insightsError}</p>}
            <InsightsJournal
              insights={insights}
              coachees={coachees}
              currentUserRole={currentUser.role}
              currentUsername={currentUser.username}
              onAddInsight={(item) => {
                void handleAddInsight(item);
              }}
              onUpdateInsight={(insightId, patch) => {
                void handleUpdateInsight(insightId, patch);
              }}
              onDeleteInsight={(insightId) => {
                void handleDeleteInsight(insightId);
              }}
            />
          </>
        )}

        {activeModule === 'administration' && <AdministrationPanel currentUser={currentUser} />}
      </section>
    </main>
  );
}
