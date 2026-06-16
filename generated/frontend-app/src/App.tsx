import { useEffect, useMemo, useState } from 'react';
import { PlanList } from './components/PlanList';
import { PlanDetail } from './components/PlanDetail';
import { CalendarPanel } from './components/CalendarPanel';
import { AdministrationPanel } from './components/AdministrationPanel';
import { LoginScreen } from './components/LoginScreen';
import { clearToken, createPlan, getMe, getToken, listAdminCoachees, listCoachDirectory, listPlans } from './api';
import { requirementTitle } from './data/seed';
import type { AdminCoachee, AdminCoach, CoachingPlan, CurrentUser } from './types';

const MODULES = [
  { key: 'plans', label: 'Coaching Plans', enabled: true },
  { key: 'calendar', label: 'Calendar', enabled: true },
  { key: 'administration', label: 'Administration', enabled: true },
] as const;

type ModuleKey = (typeof MODULES)[number]['key'];

export default function App() {
  const enabledModules = useMemo(() => MODULES.filter((item) => item.enabled), []);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'plans');

  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  const [plans, setPlans] = useState<CoachingPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<CoachingPlan | null>(null);

  const [coachees, setCoachees] = useState<AdminCoachee[]>([]);
  const [coaches, setCoaches] = useState<AdminCoach[]>([]);
  const [coacheesLoading, setCoacheesLoading] = useState(true);
  const [coacheesError, setCoacheesError] = useState<string | null>(null);

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
      setPlansError('Your session expired. Please sign in again.');
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
            loading={plansLoading}
            error={plansError}
          />
        )}

        {activeModule === 'plans' && selectedPlan && (
          <PlanDetail
            plan={selectedPlan}
            coachees={coachees}
            coaches={coaches}
            onBack={() => setSelectedPlan(null)}
            onPlanUpdated={handlePlanUpdated}
          />
        )}

        {activeModule === 'calendar' && <CalendarPanel coachees={coachees} />}

        {activeModule === 'administration' && <AdministrationPanel currentUser={currentUser} />}
      </section>
    </main>
  );
}
