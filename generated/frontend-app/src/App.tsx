import { useEffect, useMemo, useState } from 'react';
import { PlanList } from './components/PlanList';
import { PlanDetail } from './components/PlanDetail';
import { CoacheesManager } from './components/CoacheesManager';
import { createPlan, listCoachees, listPlans } from './api';
import {
  requirementTitle,
} from './data/seed';
import type { Coachee, CoachingPlan } from './types';

const MODULES = [
  { key: 'plans', label: 'Coaching Plans', enabled: true },
  { key: 'coachees', label: 'Coachees', enabled: true },
] as const;

type ModuleKey = (typeof MODULES)[number]['key'];

export default function App() {
  const enabledModules = useMemo(() => MODULES.filter((item) => item.enabled), []);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'plans');

  const [plans, setPlans] = useState<CoachingPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<CoachingPlan | null>(null);
  const [coachees, setCoachees] = useState<Coachee[]>([]);
  const [coacheesLoading, setCoacheesLoading] = useState(true);
  const [coacheesError, setCoacheesError] = useState<string | null>(null);

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
            onPlanUpdated={handlePlanUpdated}
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

      </section>
    </main>
  );
}
