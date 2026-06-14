import { useEffect, useState } from 'react';
import { createAction, listActions, updateActionStatus } from '../api';
import type { Coachee, CoachingPlan, PlanAction, TaskStatus } from '../types';

interface PlanDetailProps {
  plan: CoachingPlan;
  coachees: Coachee[];
  onBack: () => void;
}

const STATUS_LABEL: Record<TaskStatus, string> = {
  backlog: 'Backlog',
  inProgress: 'In Progress',
  done: 'Done',
};

const STATUS_OPTIONS: TaskStatus[] = ['backlog', 'inProgress', 'done'];

export function PlanDetail({ plan, coachees, onBack }: PlanDetailProps) {
  const [actions, setActions] = useState<PlanAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New action form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [assignee, setAssignee] = useState('Coachee');
  const [dueDate, setDueDate] = useState('');

  const coacheeName = plan.coacheeName ?? coachees.find((c) => c.id === plan.coacheeId)?.name ?? null;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listActions(plan.id)
      .then((data) => { if (!cancelled) { setActions(data); setError(null); } })
      .catch(() => { if (!cancelled) setError('Could not load actions from backend.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [plan.id]);

  async function handleAddAction(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    try {
      const created = await createAction(plan.id, {
        title: title.trim(),
        description: description.trim() || 'No description provided.',
        assignee,
        dueDate: dueDate || new Date().toISOString().slice(0, 10),
      });
      setActions((prev) => [...prev, created]);
      setTitle('');
      setDescription('');
      setDueDate('');
      setError(null);
    } catch {
      setError('Could not save action. Please try again.');
    }
  }

  async function handleMoveAction(actionId: string, status: TaskStatus) {
    const prev = actions;
    setActions((current) => current.map((a) => (a.id === actionId ? { ...a, status } : a)));
    try {
      const updated = await updateActionStatus(plan.id, actionId, status);
      setActions((current) => current.map((a) => (a.id === actionId ? updated : a)));
    } catch {
      setActions(prev);
      setError('Could not update action status.');
    }
  }

  const grouped: Record<TaskStatus, PlanAction[]> = {
    backlog: actions.filter((a) => a.status === 'backlog').sort((x, y) => x.order - y.order),
    inProgress: actions.filter((a) => a.status === 'inProgress').sort((x, y) => x.order - y.order),
    done: actions.filter((a) => a.status === 'done').sort((x, y) => x.order - y.order),
  };

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <button type='button' onClick={onBack} style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', padding: 0, fontSize: 14, marginBottom: 8 }}>
          ← Back to plans
        </button>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <h2 style={{ marginBottom: 4 }}>{plan.title}</h2>
            {plan.goal && <p style={{ fontStyle: 'italic', color: '#475569', marginBottom: 4 }}>Goal: {plan.goal}</p>}
            {plan.description && <p className='muted'>{plan.description}</p>}
            <div style={{ display: 'flex', gap: 16, marginTop: 4, flexWrap: 'wrap' }}>
              {coacheeName && <span className='muted'>👤 Coachee: {coacheeName}</span>}
              {plan.targetDate && <span className='muted'>📅 Target: {plan.targetDate}</span>}
            </div>
          </div>
        </div>
      </div>

      {error && <p className='muted' style={{ color: '#c0392b', marginBottom: 12 }}>{error}</p>}

      {/* Add action form */}
      <form className='card' onSubmit={handleAddAction} style={{ marginBottom: 20 }}>
        <h3>Add action</h3>
        <label>
          Action title *
          <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder='e.g. Schedule kick-off meeting' />
        </label>
        <label>
          Assignee
          <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value='Coachee'>Coachee</option>
            <option value='Coach'>Coach</option>
            {coacheeName && coacheeName !== 'Coachee' && <option value={coacheeName}>{coacheeName}</option>}
          </select>
        </label>
        <label>
          Description
          <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          Due date
          <input type='date' value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </label>
        <button type='submit' className='primary'>Add action</button>
      </form>

      {/* Kanban columns */}
      {loading ? (
        <p className='muted'>Loading actions…</p>
      ) : (
        <div className='kanban'>
          {STATUS_OPTIONS.map((status) => (
            <div key={status} className='kanban-col'>
              <h3>{STATUS_LABEL[status]}</h3>
              {grouped[status].length === 0 && (
                <p className='muted' style={{ fontSize: 13 }}>No actions</p>
              )}
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {grouped[status].map((action) => (
                  <li key={action.id} className='card' style={{ marginBottom: 8 }}>
                    <strong style={{ display: 'block', marginBottom: 2 }}>{action.title}</strong>
                    <span className='muted' style={{ fontSize: 12 }}>
                      {action.assignee} · #{action.order + 1} · {action.dueDate}
                    </span>
                    {action.description && <p className='muted' style={{ fontSize: 13, marginTop: 4 }}>{action.description}</p>}
                    <label style={{ display: 'block', marginTop: 6, fontSize: 13 }}>
                      Move to{' '}
                      <select
                        value={status}
                        onChange={(e) => handleMoveAction(action.id, e.target.value as TaskStatus)}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>{STATUS_LABEL[s]}</option>
                        ))}
                      </select>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
