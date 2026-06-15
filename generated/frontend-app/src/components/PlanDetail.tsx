import { useEffect, useMemo, useState } from 'react';
import { createAction, createDiscussion, getCurrentUsername, listActions, listDiscussions, updateAction, updateActionStatus, updatePlan } from '../api';
import type { AdminCoach, AdminCoachee, CoachingPlan, DiscussionItem, PlanAction, TaskStatus } from '../types';

interface PlanDetailProps {
  plan: CoachingPlan;
  coachees: AdminCoachee[];
  coaches: AdminCoach[];
  onBack: () => void;
  onPlanUpdated: (plan: CoachingPlan) => void;
}

const STATUS_LABEL: Record<TaskStatus, string> = {
  backlog: 'Backlog',
  inProgress: 'In Progress',
  done: 'Done',
};

const STATUS_OPTIONS: TaskStatus[] = ['backlog', 'inProgress', 'done'];

export function PlanDetail({ plan, coachees, coaches, onBack, onPlanUpdated }: PlanDetailProps) {
  const [actions, setActions] = useState<PlanAction[]>([]);
  const [discussions, setDiscussions] = useState<DiscussionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [discussionsLoading, setDiscussionsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<PlanAction | null>(null);

  const [editingPlan, setEditingPlan] = useState(false);
  const [planTitle, setPlanTitle] = useState(plan.title);
  const [planGoal, setPlanGoal] = useState(plan.goal);
  const [planDescription, setPlanDescription] = useState(plan.description);
  const [planTargetDate, setPlanTargetDate] = useState(plan.targetDate);
  const [planStatus, setPlanStatus] = useState(plan.status);
  const [planCoacheeId, setPlanCoacheeId] = useState(plan.coacheeId ?? '');
  const [addingAction, setAddingAction] = useState(false);

  const [planDiscussionText, setPlanDiscussionText] = useState('');
  const [actionDiscussionText, setActionDiscussionText] = useState('');

  // New action form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [assignee, setAssignee] = useState('');
  const [dueDate, setDueDate] = useState('');
  const currentUsername = useMemo(() => getCurrentUsername(), []);

  const coacheeName = plan.coacheeName ?? coachees.find((c) => c.id === plan.coacheeId)?.name ?? null;
  const assigneeOptions = useMemo(() => {
    const values = new Set<string>();
    coaches.filter((coach) => !coach.isAdmin).forEach((coach) => values.add(coach.username));
    coachees.forEach((coachee) => values.add(coachee.name));
    return Array.from(values).sort((a, b) => a.localeCompare(b));
  }, [coaches, coachees]);

  useEffect(() => {
    if (!assignee && assigneeOptions.length > 0) {
      setAssignee(assigneeOptions[0]);
    }
  }, [assignee, assigneeOptions]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listActions(plan.id)
      .then((data) => { if (!cancelled) { setActions(data); setError(null); } })
      .catch(() => { if (!cancelled) setError('Could not load actions from backend.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [plan.id]);

  useEffect(() => {
    let cancelled = false;
    setDiscussionsLoading(true);
    listDiscussions({ planId: plan.id })
      .then((items) => {
        if (!cancelled) {
          setDiscussions(items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load plan discussions.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDiscussionsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
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
      setAddingAction(false);
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

  async function handleSavePlan(): Promise<void> {
    try {
      const updated = await updatePlan(plan.id, {
        title: planTitle.trim(),
        goal: planGoal.trim(),
        description: planDescription.trim(),
        targetDate: planTargetDate,
        status: planStatus,
        coacheeId: planCoacheeId || null,
      });
      onPlanUpdated(updated);
      setEditingPlan(false);
      setError(null);
    } catch {
      setError('Could not update plan.');
    }
  }

  async function handleSaveAction(): Promise<void> {
    if (!activeAction) return;
    try {
      const updated = await updateAction(plan.id, activeAction.id, {
        title: activeAction.title,
        description: activeAction.description,
        assignee: activeAction.assignee,
        dueDate: activeAction.dueDate,
        status: activeAction.status,
      });
      setActions((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
      setActiveAction(updated);
      setError(null);
    } catch {
      setError('Could not update action.');
    }
  }

  async function handleAddPlanDiscussion(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    const text = planDiscussionText.trim();
    if (!text) return;
    try {
      const created = await createDiscussion({
        planId: plan.id,
        author: currentUsername,
        message: text,
      });
      setDiscussions((prev) => [created, ...prev]);
      setPlanDiscussionText('');
      setError(null);
    } catch {
      setError('Could not post plan discussion.');
    }
  }

  async function handleAddActionDiscussion(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (!activeAction) return;
    const text = actionDiscussionText.trim();
    if (!text) return;
    try {
      const created = await createDiscussion({
        planId: plan.id,
        taskId: activeAction.id,
        author: currentUsername,
        message: text,
      });
      setDiscussions((prev) => [created, ...prev]);
      setActionDiscussionText('');
      setError(null);
    } catch {
      setError('Could not post action discussion.');
    }
  }

  function handleDrop(event: React.DragEvent, status: TaskStatus): void {
    event.preventDefault();
    const actionId = event.dataTransfer.getData('text/plain');
    if (actionId) {
      void handleMoveAction(actionId, status);
    }
  }

  const planDiscussions = useMemo(
    () => discussions.filter((discussion) => discussion.planId === plan.id && !discussion.taskId),
    [discussions, plan.id],
  );

  const actionDiscussions = useMemo(() => {
    const map: Record<string, DiscussionItem[]> = {};
    discussions.forEach((discussion) => {
      if (!discussion.taskId) return;
      if (!map[discussion.taskId]) map[discussion.taskId] = [];
      map[discussion.taskId].push(discussion);
    });
    return map;
  }, [discussions]);

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
          <button type='button' className='primary' onClick={() => setEditingPlan(true)}>Edit plan</button>
        </div>
      </div>

      {error && <p className='muted' style={{ color: '#c0392b', marginBottom: 12 }}>{error}</p>}

      <div style={{ marginBottom: 16 }}>
        <button type='button' className='primary' onClick={() => setAddingAction(true)}>Add action</button>
      </div>

      {/* Kanban columns */}
      {loading ? (
        <p className='muted'>Loading actions…</p>
      ) : (
        <div className='kanban'>
          {STATUS_OPTIONS.map((status) => (
            <div
              key={status}
              className='kanban-col'
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => handleDrop(event, status)}
            >
              <h3>{STATUS_LABEL[status]}</h3>
              {grouped[status].length === 0 && (
                <p className='muted' style={{ fontSize: 13 }}>No actions</p>
              )}
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {grouped[status].map((action) => (
                  <li
                    key={action.id}
                    className='card'
                    style={{ marginBottom: 8, cursor: 'pointer' }}
                    draggable
                    onDragStart={(event) => event.dataTransfer.setData('text/plain', action.id)}
                    onClick={() => setActiveAction(action)}
                  >
                    <strong style={{ display: 'block', marginBottom: 2 }}>{action.title}</strong>
                    <span className='muted' style={{ fontSize: 12 }}>
                      {action.assignee} · #{action.order + 1} · {action.dueDate}
                    </span>
                    {action.description && <p className='muted' style={{ fontSize: 13, marginTop: 4 }}>{action.description}</p>}
                    <p className='muted' style={{ fontSize: 12, marginTop: 6 }}>
                      Discussions: {(actionDiscussions[action.id] ?? []).length}
                    </p>
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

      {/* Plan discussions (localized to this plan) */}
      <div className='card' style={{ marginTop: 20 }}>
        <h3>Plan Discussion</h3>
        <p className='muted'>Discuss this coaching plan as a whole.</p>
        <form onSubmit={(event) => void handleAddPlanDiscussion(event)} style={{ marginBottom: 12 }}>
          <p className='muted' style={{ margin: '0 0 8px 0' }}>Posting as {currentUsername}</p>
          <label>
            Message
            <textarea rows={2} value={planDiscussionText} onChange={(event) => setPlanDiscussionText(event.target.value)} />
          </label>
          <button type='submit' className='primary'>Post plan discussion</button>
        </form>
        {discussionsLoading ? (
          <p className='muted'>Loading discussions…</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {planDiscussions.map((discussion) => (
              <li key={discussion.id} className='card' style={{ marginBottom: 8 }}>
                <strong>{discussion.author}</strong>
                <span className='muted' style={{ marginLeft: 8 }}>{discussion.createdAt}</span>
                <p style={{ marginTop: 6 }}>{discussion.message}</p>
              </li>
            ))}
            {planDiscussions.length === 0 && <p className='muted'>No plan discussions yet.</p>}
          </ul>
        )}
      </div>

      {/* Plan edit modal */}
      {editingPlan && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'grid', placeItems: 'center', zIndex: 50 }}>
          <div className='card' style={{ width: 'min(680px, 92vw)', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button
              type='button'
              aria-label='Close plan editor'
              onClick={() => setEditingPlan(false)}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'none', fontSize: 20, lineHeight: 1, cursor: 'pointer', color: '#475569' }}
            >
              x
            </button>
            <h3>Edit plan</h3>
            <label>
              Title
              <input value={planTitle} onChange={(event) => setPlanTitle(event.target.value)} />
            </label>
            <label>
              Goal
              <textarea rows={2} value={planGoal} onChange={(event) => setPlanGoal(event.target.value)} />
            </label>
            <label>
              Description
              <textarea rows={3} value={planDescription} onChange={(event) => setPlanDescription(event.target.value)} />
            </label>
            <label>
              Status
              <select value={planStatus} onChange={(event) => setPlanStatus(event.target.value as typeof planStatus)}>
                <option value='todo'>To Do</option>
                <option value='inProgress'>In Progress</option>
                <option value='done'>Done</option>
              </select>
            </label>
            <label>
              Coachee
              <select value={planCoacheeId} onChange={(event) => setPlanCoacheeId(event.target.value)}>
                <option value=''>— unassigned —</option>
                {coachees.map((coachee) => (
                  <option key={coachee.id} value={coachee.id}>{coachee.name}</option>
                ))}
              </select>
            </label>
            <label>
              Target date
              <input type='date' value={planTargetDate} onChange={(event) => setPlanTargetDate(event.target.value)} />
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button type='button' className='primary' onClick={() => void handleSavePlan()}>Save plan</button>
            </div>
          </div>
        </div>
      )}

      {/* Add action modal */}
      {addingAction && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'grid', placeItems: 'center', zIndex: 55 }}>
          <div className='card' style={{ width: 'min(680px, 92vw)', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button
              type='button'
              aria-label='Close add action dialog'
              onClick={() => setAddingAction(false)}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'none', fontSize: 20, lineHeight: 1, cursor: 'pointer', color: '#475569' }}
            >
              x
            </button>
            <h3>Add action</h3>
            <form onSubmit={handleAddAction}>
              <label>
                Action title *
                <input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder='e.g. Schedule kick-off meeting' />
              </label>
              <label>
                Assignee
                <select value={assignee} onChange={(event) => setAssignee(event.target.value)}>
                  {assigneeOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>
                Description
                <textarea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
              </label>
              <label>
                Due date
                <input type='date' value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
              </label>
              <button type='submit' className='primary'>Save action</button>
            </form>
          </div>
        </div>
      )}

      {/* Action edit modal */}
      {activeAction && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'grid', placeItems: 'center', zIndex: 60 }}>
          <div className='card' style={{ width: 'min(760px, 94vw)', maxHeight: '92vh', overflowY: 'auto', position: 'relative' }}>
            <button
              type='button'
              aria-label='Close action editor'
              onClick={() => setActiveAction(null)}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'none', fontSize: 20, lineHeight: 1, cursor: 'pointer', color: '#475569' }}
            >
              x
            </button>
            <h3>Edit action</h3>
            <label>
              Title
              <input
                value={activeAction.title}
                onChange={(event) => setActiveAction({ ...activeAction, title: event.target.value })}
              />
            </label>
            <label>
              Description
              <textarea
                rows={3}
                value={activeAction.description}
                onChange={(event) => setActiveAction({ ...activeAction, description: event.target.value })}
              />
            </label>
            <label>
              Assignee
              <select
                value={activeAction.assignee}
                onChange={(event) => setActiveAction({ ...activeAction, assignee: event.target.value })}
              >
                {assigneeOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              Status
              <select
                value={activeAction.status}
                onChange={(event) => setActiveAction({ ...activeAction, status: event.target.value as TaskStatus })}
              >
                <option value='backlog'>Backlog</option>
                <option value='inProgress'>In Progress</option>
                <option value='done'>Done</option>
              </select>
            </label>
            <label>
              Due date
              <input
                type='date'
                value={activeAction.dueDate}
                onChange={(event) => setActiveAction({ ...activeAction, dueDate: event.target.value })}
              />
            </label>

            <div className='card' style={{ marginTop: 12 }}>
              <h4>Action Discussion</h4>
              <form onSubmit={(event) => void handleAddActionDiscussion(event)}>
                <p className='muted' style={{ margin: '0 0 8px 0' }}>Posting as {currentUsername}</p>
                <label>
                  Message
                  <textarea rows={2} value={actionDiscussionText} onChange={(event) => setActionDiscussionText(event.target.value)} />
                </label>
                <button type='submit' className='primary'>Post action discussion</button>
              </form>
              <ul style={{ listStyle: 'none', padding: 0, margin: '10px 0 0 0' }}>
                {(actionDiscussions[activeAction.id] ?? []).map((discussion) => (
                  <li key={discussion.id} className='card' style={{ marginBottom: 8 }}>
                    <strong>{discussion.author}</strong>
                    <span className='muted' style={{ marginLeft: 8 }}>{discussion.createdAt}</span>
                    <p style={{ marginTop: 6 }}>{discussion.message}</p>
                  </li>
                ))}
                {(actionDiscussions[activeAction.id] ?? []).length === 0 && <p className='muted'>No action discussions yet.</p>}
              </ul>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button type='button' className='primary' onClick={() => void handleSaveAction()}>Save action</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
