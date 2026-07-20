import { useEffect, useState } from 'react';
import {
  createAdminCoachee,
  createAdminCoach,
  deleteAdminCoachee,
  deleteAdminCoach,
  listAdminCoachees,
  listAdminCoaches,
  updateAdminCoachee,
  updateAdminCoach,
} from '../api';
import { isValidInputEmail, sanitizeInput, sanitizeInputEmail } from './adminFormUtils';
import { CoacheeDetailPanel } from './CoacheeDetailPanel';
import type { AdminCoachee, AdminCoach, CurrentUser } from '../types';

interface AdministrationPanelProps {
  currentUser: CurrentUser;
  /** Coachee id to auto-open (e.g. deep-linked from a contract notification). */
  focusCoacheeId?: string | null;
  /** Contract id to auto-open within the focused coachee's detail view. */
  focusContractId?: string | null;
  onFocusHandled?: () => void;
}

interface CoachFormState {
  username: string;
  email: string;
  isAdmin: boolean;
}

interface CoacheeFormState {
  name: string;
  email: string;
  notes: string;
}

const EMPTY_COACH_FORM: CoachFormState = {
  username: '',
  email: '',
  isAdmin: false,
};

const EMPTY_COACHEE_FORM: CoacheeFormState = {
  name: '',
  email: '',
  notes: '',
};

export function AdministrationPanel({ currentUser, focusCoacheeId, focusContractId, onFocusHandled }: AdministrationPanelProps) {
  const [coaches, setCoaches] = useState<AdminCoach[]>([]);
  const [coachees, setCoachees] = useState<AdminCoachee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [addingCoach, setAddingCoach] = useState(false);
  const [addingCoachee, setAddingCoachee] = useState(false);
  const [coachForm, setCoachForm] = useState<CoachFormState>(EMPTY_COACH_FORM);
  const [coacheeForm, setCoacheeForm] = useState<CoacheeFormState>(EMPTY_COACHEE_FORM);

  const [editingCoach, setEditingCoach] = useState<AdminCoach | null>(null);
  const [editingCoachee, setEditingCoachee] = useState<AdminCoachee | null>(null);

  const [selectedCoacheeId, setSelectedCoacheeId] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [coacheesList, coachesList] = await Promise.all([
        listAdminCoachees(),
        currentUser.isAdmin ? listAdminCoaches() : Promise.resolve([]),
      ]);
      setCoachees(coacheesList);
      setCoaches(coachesList);
    } catch {
      setError('Could not load administration data.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  // Deep-link into a specific coachee's detail view (e.g. from a contract notification).
  useEffect(() => {
    if (!focusCoacheeId || loading) return;
    const match = coachees.find((c) => c.id === focusCoacheeId);
    if (match) setSelectedCoacheeId(match.id);
  }, [focusCoacheeId, loading, coachees]);

  async function handleCreateCoach(event: React.FormEvent) {
    event.preventDefault();
    const username = sanitizeInput(coachForm.username, 150);
    const email = sanitizeInputEmail(coachForm.email);

    if (!username) {
      setError('Coach username is required.');
      return;
    }
    if (!isValidInputEmail(email)) {
      setError('Please enter a valid coach email.');
      return;
    }

    try {
      const created = await createAdminCoach({
        username,
        email,
        isAdmin: coachForm.isAdmin,
        isActive: true,
      });
      setCoaches((prev) => [...prev, created].sort((a, b) => a.username.localeCompare(b.username)));
      setCoachForm(EMPTY_COACH_FORM);
      setAddingCoach(false);
      setError(null);
    } catch {
      setError('Could not create coach.');
    }
  }

  async function handleSaveCoachEdit() {
    if (!editingCoach) return;

    const email = sanitizeInputEmail(editingCoach.email);
    if (!isValidInputEmail(email)) {
      setError('Please enter a valid coach email.');
      return;
    }

    try {
      const updated = await updateAdminCoach(editingCoach.id, {
        email,
        isAdmin: editingCoach.isAdmin,
        isActive: editingCoach.isActive,
      });
      setCoaches((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setEditingCoach(null);
      setError(null);
    } catch {
      setError('Could not update coach.');
    }
  }

  async function handleDeleteCoach(coachId: string) {
    try {
      await deleteAdminCoach(coachId);
      setCoaches((prev) => prev.filter((item) => item.id !== coachId));
      setError(null);
    } catch {
      setError('Could not delete coach.');
    }
  }

  async function handleCreateCoachee(event: React.FormEvent) {
    event.preventDefault();
    const name = sanitizeInput(coacheeForm.name, 255);
    const email = sanitizeInputEmail(coacheeForm.email);
    const notes = sanitizeInput(coacheeForm.notes, 2000);

    if (!name) {
      setError('Coachee name is required.');
      return;
    }
    if (!isValidInputEmail(email)) {
      setError('Please enter a valid coachee email.');
      return;
    }

    try {
      const created = await createAdminCoachee({ name, email, notes });
      setCoachees((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setCoacheeForm(EMPTY_COACHEE_FORM);
      setAddingCoachee(false);
      setError(null);
    } catch {
      setError('Could not create coachee.');
    }
  }

  async function handleSaveCoacheeEdit() {
    if (!editingCoachee) return;

    const name = sanitizeInput(editingCoachee.name, 255);
    const email = sanitizeInputEmail(editingCoachee.email);
    const notes = sanitizeInput(editingCoachee.notes, 2000);

    if (!name) {
      setError('Coachee name is required.');
      return;
    }
    if (!isValidInputEmail(email)) {
      setError('Please enter a valid coachee email.');
      return;
    }

    try {
      const updated = await updateAdminCoachee(editingCoachee.id, { name, email, notes });
      setCoachees((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setEditingCoachee(null);
      setError(null);
    } catch {
      setError('Could not update coachee.');
    }
  }

  async function handleDeleteCoachee(coacheeId: string) {
    try {
      await deleteAdminCoachee(coacheeId);
      setCoachees((prev) => prev.filter((item) => item.id !== coacheeId));
      setError(null);
    } catch {
      setError('Could not delete coachee.');
    }
  }

  const selectedCoachee = selectedCoacheeId ? coachees.find((c) => c.id === selectedCoacheeId) ?? null : null;

  if (selectedCoachee) {
    return (
      <CoacheeDetailPanel
        coachee={selectedCoachee}
        currentUser={currentUser}
        onBack={() => {
          setSelectedCoacheeId(null);
          onFocusHandled?.();
        }}
        focusContractId={focusContractId}
        onFocusHandled={onFocusHandled}
      />
    );
  }

  return (
    <div>
      <h2>Administration</h2>
      <p className='muted'>
        {currentUser.isAdmin
          ? 'Admins can manage coaches and all coachees.'
          : 'Coach mode: you can only manage coachees that you added.'}
      </p>

      {error && <p className='muted' style={{ color: '#c0392b' }}>{error}</p>}
      {loading && <p className='muted'>Loading administration data...</p>}

      {currentUser.isAdmin && (
        <div className='card' style={{ marginBottom: 20 }}>
          <div className='admin-panel-header'>
            <h3>Coaches</h3>
            <button type='button' className='primary' onClick={() => setAddingCoach(true)}>Add coach</button>
          </div>

          <div style={{ display: 'grid', gap: 8 }}>
            {coaches.map((coach) => (
              <div key={coach.id} className='admin-panel-row'>
                <div>
                  <strong>{coach.username}</strong>
                  <p className='muted' style={{ margin: '4px 0' }}>{coach.email || 'No email'}</p>
                  <p className='muted' style={{ margin: 0 }}>
                    {coach.isAdmin ? 'Administrator' : 'Coach'} · {coach.isActive ? 'Active' : 'Inactive'}
                  </p>
                </div>
                <div className='admin-panel-actions'>
                  <button type='button' onClick={() => setEditingCoach(coach)}>Edit</button>
                  <button type='button' onClick={() => void handleDeleteCoach(coach.id)}>Remove</button>
                </div>
              </div>
            ))}
            {!loading && coaches.length === 0 && <p className='muted'>No coaches found.</p>}
          </div>
        </div>
      )}

      <div className='card'>
        <div className='admin-panel-header'>
          <h3>Coachees</h3>
          <button type='button' className='primary' onClick={() => setAddingCoachee(true)}>Add coachee</button>
        </div>

        <div style={{ display: 'grid', gap: 8 }}>
          {coachees.map((coachee) => (
            <div key={coachee.id} className='admin-panel-row'>
              <button
                type='button'
                onClick={() => setSelectedCoacheeId(coachee.id)}
                style={{ background: 'none', border: 'none', textAlign: 'left', padding: 0, cursor: 'pointer', flex: 1 }}
              >
                <strong>{coachee.name}</strong>
                <p className='muted' style={{ margin: '4px 0' }}>{coachee.email || 'No email'}</p>
                {currentUser.isAdmin && <p className='muted' style={{ margin: 0 }}>Added by: {coachee.addedByUsername || 'Unknown'}</p>}
              </button>
              <div className='admin-panel-actions'>
                <button type='button' onClick={() => setEditingCoachee(coachee)}>Edit</button>
                <button type='button' onClick={() => void handleDeleteCoachee(coachee.id)}>Remove</button>
              </div>
            </div>
          ))}
          {!loading && coachees.length === 0 && <p className='muted'>No coachees found.</p>}
        </div>
      </div>

      {addingCoach && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button type='button' aria-label='Close add coach dialog' onClick={() => setAddingCoach(false)} className='admin-panel-modal-close'>x</button>
            <h3>Add coach</h3>
            <form onSubmit={handleCreateCoach}>
              <label>
                Username
                <input
                  value={coachForm.username}
                  onChange={(event) => setCoachForm((prev) => ({ ...prev, username: event.target.value }))}
                  required
                />
              </label>
              <label>
                Email
                <input
                  type='email'
                  value={coachForm.email}
                  onChange={(event) => setCoachForm((prev) => ({ ...prev, email: event.target.value }))}
                />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                <input
                  type='checkbox'
                  checked={coachForm.isAdmin}
                  onChange={(event) => setCoachForm((prev) => ({ ...prev, isAdmin: event.target.checked }))}
                  style={{ width: 'auto', marginTop: 0 }}
                />
                Grant administrator access
              </label>
              <button type='submit' className='primary'>Create coach</button>
            </form>
          </div>
        </div>
      )}

      {editingCoach && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button type='button' aria-label='Close coach editor' onClick={() => setEditingCoach(null)} className='admin-panel-modal-close'>x</button>
            <h3>Edit coach: {editingCoach.username}</h3>
            <label>
              Email
              <input
                type='email'
                value={editingCoach.email}
                onChange={(event) => setEditingCoach({ ...editingCoach, email: event.target.value })}
              />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <input
                type='checkbox'
                checked={editingCoach.isAdmin}
                onChange={(event) => setEditingCoach({ ...editingCoach, isAdmin: event.target.checked })}
                style={{ width: 'auto', marginTop: 0 }}
              />
              Administrator
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <input
                type='checkbox'
                checked={editingCoach.isActive}
                onChange={(event) => setEditingCoach({ ...editingCoach, isActive: event.target.checked })}
                style={{ width: 'auto', marginTop: 0 }}
              />
              Active account
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button type='button' className='primary' onClick={() => void handleSaveCoachEdit()}>Save coach</button>
            </div>
          </div>
        </div>
      )}

      {addingCoachee && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button type='button' aria-label='Close add coachee dialog' onClick={() => setAddingCoachee(false)} className='admin-panel-modal-close'>x</button>
            <h3>Add coachee</h3>
            <form onSubmit={handleCreateCoachee}>
              <label>
                Name
                <input
                  value={coacheeForm.name}
                  onChange={(event) => setCoacheeForm((prev) => ({ ...prev, name: event.target.value }))}
                  required
                />
              </label>
              <label>
                Email
                <input
                  type='email'
                  value={coacheeForm.email}
                  onChange={(event) => setCoacheeForm((prev) => ({ ...prev, email: event.target.value }))}
                />
              </label>
              <label>
                Notes
                <textarea
                  rows={2}
                  value={coacheeForm.notes}
                  onChange={(event) => setCoacheeForm((prev) => ({ ...prev, notes: event.target.value }))}
                />
              </label>
              <button type='submit' className='primary'>Create coachee</button>
            </form>
          </div>
        </div>
      )}

      {editingCoachee && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button type='button' aria-label='Close coachee editor' onClick={() => setEditingCoachee(null)} className='admin-panel-modal-close'>x</button>
            <h3>Edit coachee</h3>
            <label>
              Name
              <input
                value={editingCoachee.name}
                onChange={(event) => setEditingCoachee({ ...editingCoachee, name: event.target.value })}
              />
            </label>
            <label>
              Email
              <input
                type='email'
                value={editingCoachee.email}
                onChange={(event) => setEditingCoachee({ ...editingCoachee, email: event.target.value })}
              />
            </label>
            <label>
              Notes
              <textarea
                rows={3}
                value={editingCoachee.notes}
                onChange={(event) => setEditingCoachee({ ...editingCoachee, notes: event.target.value })}
              />
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button type='button' className='primary' onClick={() => void handleSaveCoacheeEdit()}>Save coachee</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
