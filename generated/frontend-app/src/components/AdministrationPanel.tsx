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
import type { AdminCoachee, AdminCoach, CurrentUser } from '../types';

interface AdministrationPanelProps {
  currentUser: CurrentUser;
}

export function AdministrationPanel({ currentUser }: AdministrationPanelProps) {
  const [coaches, setCoaches] = useState<AdminCoach[]>([]);
  const [coachees, setCoachees] = useState<AdminCoachee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newCoachUsername, setNewCoachUsername] = useState('');
  const [newCoachEmail, setNewCoachEmail] = useState('');
  const [newCoachPassword, setNewCoachPassword] = useState('');
  const [newCoachAdmin, setNewCoachAdmin] = useState(false);

  const [newCoacheeName, setNewCoacheeName] = useState('');
  const [newCoacheeEmail, setNewCoacheeEmail] = useState('');
  const [newCoacheeNotes, setNewCoacheeNotes] = useState('');

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

  async function handleCreateCoach(event: React.FormEvent) {
    event.preventDefault();
    if (!newCoachUsername.trim()) return;
    try {
      const created = await createAdminCoach({
        username: newCoachUsername.trim(),
        email: newCoachEmail.trim(),
        password: newCoachPassword.trim() || undefined,
        isAdmin: newCoachAdmin,
        isActive: true,
      });
      setCoaches((prev) => [...prev, created].sort((a, b) => a.username.localeCompare(b.username)));
      setNewCoachUsername('');
      setNewCoachEmail('');
      setNewCoachPassword('');
      setNewCoachAdmin(false);
      setError(null);
    } catch {
      setError('Could not create coach.');
    }
  }

  async function handleUpdateCoach(coach: AdminCoach, patch: Partial<{ email: string; isAdmin: boolean; isActive: boolean }>) {
    try {
      const updated = await updateAdminCoach(coach.id, patch);
      setCoaches((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
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
    if (!newCoacheeName.trim()) return;
    try {
      const created = await createAdminCoachee({
        name: newCoacheeName.trim(),
        email: newCoacheeEmail.trim(),
        notes: newCoacheeNotes.trim(),
      });
      setCoachees((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setNewCoacheeName('');
      setNewCoacheeEmail('');
      setNewCoacheeNotes('');
      setError(null);
    } catch {
      setError('Could not create coachee.');
    }
  }

  async function handleUpdateCoachee(coachee: AdminCoachee, patch: Partial<{ name: string; email: string; notes: string }>) {
    try {
      const updated = await updateAdminCoachee(coachee.id, patch);
      setCoachees((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
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
          <h3>Coaches</h3>
          <form onSubmit={handleCreateCoach} style={{ marginBottom: 12 }}>
            <label>
              Username
              <input value={newCoachUsername} onChange={(event) => setNewCoachUsername(event.target.value)} required />
            </label>
            <label>
              Email
              <input type='email' value={newCoachEmail} onChange={(event) => setNewCoachEmail(event.target.value)} />
            </label>
            <label>
              Temporary password
              <input type='password' value={newCoachPassword} onChange={(event) => setNewCoachPassword(event.target.value)} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <input
                type='checkbox'
                checked={newCoachAdmin}
                onChange={(event) => setNewCoachAdmin(event.target.checked)}
                style={{ width: 'auto', marginTop: 0 }}
              />
              Grant administrator access
            </label>
            <button type='submit' className='primary'>Add coach</button>
          </form>

          <div style={{ display: 'grid', gap: 8 }}>
            {coaches.map((coach) => (
              <div key={coach.id} className='card' style={{ marginBottom: 0 }}>
                <strong>{coach.username}</strong>
                <p className='muted' style={{ margin: '6px 0' }}>{coach.email || 'No email'}</p>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                  <input
                    type='checkbox'
                    checked={coach.isAdmin}
                    onChange={(event) => void handleUpdateCoach(coach, { isAdmin: event.target.checked })}
                    style={{ width: 'auto', marginTop: 0 }}
                  />
                  Administrator
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                  <input
                    type='checkbox'
                    checked={coach.isActive}
                    onChange={(event) => void handleUpdateCoach(coach, { isActive: event.target.checked })}
                    style={{ width: 'auto', marginTop: 0 }}
                  />
                  Active account
                </label>
                <button type='button' onClick={() => void handleDeleteCoach(coach.id)} style={{ marginTop: 8 }}>
                  Remove coach
                </button>
              </div>
            ))}
            {!loading && coaches.length === 0 && <p className='muted'>No coaches found.</p>}
          </div>
        </div>
      )}

      <div className='card'>
        <h3>Coachees</h3>
        <form onSubmit={handleCreateCoachee} style={{ marginBottom: 12 }}>
          <label>
            Name
            <input value={newCoacheeName} onChange={(event) => setNewCoacheeName(event.target.value)} required />
          </label>
          <label>
            Email
            <input type='email' value={newCoacheeEmail} onChange={(event) => setNewCoacheeEmail(event.target.value)} />
          </label>
          <label>
            Notes
            <textarea rows={2} value={newCoacheeNotes} onChange={(event) => setNewCoacheeNotes(event.target.value)} />
          </label>
          <button type='submit' className='primary'>Add coachee</button>
        </form>

        <div style={{ display: 'grid', gap: 8 }}>
          {coachees.map((coachee) => (
            <div key={coachee.id} className='card' style={{ marginBottom: 0 }}>
              <label>
                Name
                <input
                  value={coachee.name}
                  onChange={(event) => {
                    const name = event.target.value;
                    setCoachees((prev) => prev.map((item) => (item.id === coachee.id ? { ...item, name } : item)));
                  }}
                  onBlur={() => void handleUpdateCoachee(coachee, { name: coachee.name })}
                />
              </label>
              <label>
                Email
                <input
                  value={coachee.email}
                  onChange={(event) => {
                    const email = event.target.value;
                    setCoachees((prev) => prev.map((item) => (item.id === coachee.id ? { ...item, email } : item)));
                  }}
                  onBlur={() => void handleUpdateCoachee(coachee, { email: coachee.email })}
                />
              </label>
              <label>
                Notes
                <textarea
                  rows={2}
                  value={coachee.notes}
                  onChange={(event) => {
                    const notes = event.target.value;
                    setCoachees((prev) => prev.map((item) => (item.id === coachee.id ? { ...item, notes } : item)));
                  }}
                  onBlur={() => void handleUpdateCoachee(coachee, { notes: coachee.notes })}
                />
              </label>
              {currentUser.isAdmin && <p className='muted'>Added by: {coachee.addedByUsername || 'Unknown'}</p>}
              <button type='button' onClick={() => void handleDeleteCoachee(coachee.id)}>
                Remove coachee
              </button>
            </div>
          ))}
          {!loading && coachees.length === 0 && <p className='muted'>No coachees found.</p>}
        </div>
      </div>
    </div>
  );
}
