import { useState } from 'react';
import type { AdminCoachee, CoachingPlan, PlanStatus } from '../types';

interface PlanListProps {
  plans: CoachingPlan[];
  coachees: AdminCoachee[];
  onSelectPlan: (plan: CoachingPlan) => void;
  onCreatePlan: (plan: Omit<CoachingPlan, 'id' | 'createdAt' | 'coacheeName'>) => void;
  canCreatePlan: boolean;
  loading: boolean;
  error: string | null;
}

const STATUS_LABELS: Record<PlanStatus, string> = {
  todo: 'To Do',
  inProgress: 'In Progress',
  done: 'Done',
};

const STATUS_COLORS: Record<PlanStatus, string> = {
  todo: '#64748b',
  inProgress: '#2563eb',
  done: '#16a34a',
};

export function PlanList({ plans, coachees, onSelectPlan, onCreatePlan, canCreatePlan, loading, error }: PlanListProps) {
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [goal, setGoal] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [coacheeId, setCoacheeId] = useState('');

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    onCreatePlan({
      title: title.trim(),
      description: description.trim(),
      goal: goal.trim(),
      status: 'todo',
      targetDate,
      coacheeId: coacheeId || null,
    });
    setTitle('');
    setDescription('');
    setGoal('');
    setTargetDate('');
    setCoacheeId('');
    setShowForm(false);
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h2>Coaching Plans</h2>
          <p className='muted'>Plans sorted by target date. Select a plan to view its kanban board and discussions.</p>
        </div>
        {canCreatePlan && (
          <button type='button' className='primary' onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Cancel' : '+ New Plan'}
          </button>
        )}
      </div>

      {error && <p className='muted' style={{ color: '#c0392b' }}>{error}</p>}
      {loading && <p className='muted'>Loading plans…</p>}

      {canCreatePlan && showForm && (
        <form className='card' onSubmit={handleSubmit} style={{ marginBottom: 24 }}>
          <h3>Create coaching plan</h3>
          <label>
            Title *
            <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder='e.g. Q3 leadership development' />
          </label>
          <label>
            Overall goal
            <textarea rows={2} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder='What does success look like for this plan?' />
          </label>
          <label>
            Description
            <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <label>
            Target date
            <input type='date' value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
          </label>
          <label>
            Assign to coachee
            <select value={coacheeId} onChange={(e) => setCoacheeId(e.target.value)}>
              <option value=''>— unassigned —</option>
              {coachees.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <button type='submit' className='primary'>Create plan</button>
        </form>
      )}

      {!loading && plans.length === 0 && !showForm && (
        <div className='card' style={{ textAlign: 'center', padding: '40px 16px' }}>
          <p className='muted'>
            {canCreatePlan
              ? <>No coaching plans yet. Click <strong>+ New Plan</strong> to get started.</>
              : 'No coaching plans available yet.'}
          </p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {plans.map((plan) => (
          <button
            key={plan.id}
            type='button'
            className='card'
            onClick={() => onSelectPlan(plan)}
            style={{ textAlign: 'left', cursor: 'pointer', width: '100%', background: 'white' }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <strong style={{ display: 'block', fontSize: 16, marginBottom: 4 }}>{plan.title}</strong>
                {plan.goal && <p className='muted' style={{ marginBottom: 4, fontStyle: 'italic' }}>{plan.goal}</p>}
                {plan.description && <p className='muted' style={{ marginBottom: 4 }}>{plan.description}</p>}
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 6 }}>
                  {plan.coacheeName && (
                    <span className='muted'>👤 {plan.coacheeName}</span>
                  )}
                  {plan.targetDate && (
                    <span className='muted'>📅 {plan.targetDate}</span>
                  )}
                </div>
              </div>
              <span
                style={{
                  fontSize: 12,
                  padding: '2px 10px',
                  borderRadius: 12,
                  background: STATUS_COLORS[plan.status] + '22',
                  color: STATUS_COLORS[plan.status],
                  whiteSpace: 'nowrap',
                  fontWeight: 600,
                }}
              >
                {STATUS_LABELS[plan.status]}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
