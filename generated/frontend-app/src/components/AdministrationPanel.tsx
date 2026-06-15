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
  const [addingCoach, setAddingCoach] = useState(false);
  const [addingCoachee, setAddingCoachee] = useState(false);

  const [editingCoach, setEditingCoach] = useState<AdminCoach | null>(null);
  const [editCoachEmail, setEditCoachEmail] = useState('');
  const [editCoachAdmin, setEditCoachAdmin] = useState(false);
  const [editCoachActive, setEditCoachActive] = useState(true);

  const [editingCoachee, setEditingCoachee] = useState<AdminCoachee | null>(null);
  const [editCoacheeName, setEditCoacheeName] = useState('');
  const [editCoacheeEmail, setEditCoacheeEmail] = useState('');
  const [editCoacheeNotes, setEditCoacheeNotes] = useState('');

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
      setAddingCoach(false);
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

  function openCoachEditor(coach: AdminCoach) {
    setEditingCoach(coach);
    setEditCoachEmail(coach.email);
    setEditCoachAdmin(coach.isAdmin);
    setEditCoachActive(coach.isActive);
  }

  async function handleSaveCoachEdit() {
    if (!editingCoach) return;
    await handleUpdateCoach(editingCoach, {
      email: editCoachEmail,
      isAdmin: editCoachAdmin,
      isActive: editCoachActive,
    });
    setEditingCoach(null);
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
      setAddingCoachee(false);
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

  function openCoacheeEditor(coachee: AdminCoachee) {
    setEditingCoachee(coachee);
    setEditCoacheeName(coachee.name);
    setEditCoacheeEmail(coachee.email);
    setEditCoacheeNotes(coachee.notes);
  }

  async function handleSaveCoacheeEdit() {
    if (!editingCoachee) return;
    await handleUpdateCoachee(editingCoachee, {
      name: editCoacheeName,
      email: editCoacheeEmail,
      notes: editCoacheeNotes,
    });
    setEditingCoachee(null);
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Coaches</h3>
            <button type='button' className='primary' onClick={() => setAddingCoach(true)}>Add coach</button>
          </div>

          <div style={{ display: 'grid', gap: 8 }}>
            {coaches.map((coach) => (
              <div key={coach.id} className='card' style={{ marginBottom: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                <div>
                  <strong>{coach.username}</strong>
                  <p className='muted' style={{ margin: '4px 0' }}>{coach.email || 'No email'}</p>
                  <p className='muted' style={{ margin: 0 }}>
                    {coach.isAdmin ? 'Administrator' : 'Coach'} · {coach.isActive ? 'Active' : 'Inactive'}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type='button' onClick={() => openCoachEditor(coach)}>Edit</button>
                  <button type='button' onClick={() => void handleDeleteCoach(coach.id)}>Remove</button>
                </div>
              </div>
            ))}
            {!loading && coaches.length === 0 && <p className='muted'>No coaches found.</p>}
          </div>
        </div>
      )}

      <div className='card'>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Coachees</h3>
          <button type='button' className='primary' onClick={() => setAddingCoachee(true)}>Add coachee</button>
        </div>

        <div style={{ display: 'grid', gap: 8 }}>
          {coachees.map((coachee) => (
            <div key={coachee.id} className='card' style={{ marginBottom: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div>
                <strong>{coachee.name}</strong>
                <p className='muted' style={{ margin: '4px 0' }}>{coachee.email || 'No email'}</p>
                {currentUser.isAdmin && <p className='muted' style={{ margin: 0 }}>Added by: {coachee.addedByUsername || 'Unknown'}</p>}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button type='button' onClick={() => openCoacheeEditor(coachee)}>Edit</button>
                <button type='button' onClick={() => void handleDeleteCoachee(coachee.id)}>Remove</button>
              </div>
            </div>
          ))}
          {!loading && coachees.length === 0 && <p className='muted'>No coachees found.</p>}
        </div>
      </div>

      {editingCoach && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'grid', placeItems: 'center', zIndex: 60 }}>
          <div className='card' style={{ width: 'min(560px, 92vw)', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button
              type='button'
              aria-label='Close coach editor'
              onClick={() => setEditingCoach(null)}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'none', fontSize: 20, lineHeight: 1, cursor: 'pointer', color: '#475569' }}
            >
              x
            </button>
            <h3>Edit coach: {editingCoach.username}</h3>
            <label>
              Email
              <input type='email' value={editCoachEmail} onChange={(event) => setEditCoachEmail(event.target.value)} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <input type='checkbox' checked={editCoachAdmin} onChange={(event) => setEditCoachAdmin(event.target.checked)} style={{ width: 'auto', marginTop: 0 }} />
              Administrator
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <input type='checkbox' checked={editCoachActive} onChange={(event) => setEditCoachActive(event.target.checked)} style={{ width: 'auto', marginTop: 0 }} />
              Active account
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button type='button' className='primary' onClick={() => void handleSaveCoachEdit()}>Save coach</button>
            </div>
          </div>
        </div>
      )}

      {addingCoach && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'grid', placeItems: 'center', zIndex: 60 }}>
          <div className='card' style={{ width: 'min(560px, 92vw)', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button
              type='button'
              aria-label='Close add coach dialog'
              onClick={() => setAddingCoach(false)}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'none', fontSize: 20, lineHeight: 1, cursor: 'pointer', color: '#475569' }}
            >
              x
            </button>
            <h3>Add coach</h3>
            <form onSubmit={handleCreateCoach}>
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
              <button type='submit' className='primary'>Create coach</button>
            </form>
          </div>
        </div>
      )}

      {editingCoachee && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'grid', placeItems: 'center', zIndex: 60 }}>
          <div className='card' style={{ width: 'min(560px, 92vw)', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button
              type='button'
              aria-label='Close coachee editor'
              onClick={() => setEditingCoachee(null)}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'none', fontSize: 20, lineHeight: 1, cursor: 'pointer', color: '#475569' }}
            >
              x
            </button>
            <h3>Edit coachee</h3>
            <label>
              Name
              <input value={editCoacheeName} onChange={(event) => setEditCoacheeName(event.target.value)} />
            </label>
            <label>
              Email
              <input type='email' value={editCoacheeEmail} onChange={(event) => setEditCoacheeEmail(event.target.value)} />
            </label>
            <label>
              Notes
              <textarea rows={3} value={editCoacheeNotes} onChange={(event) => setEditCoacheeNotes(event.target.value)} />
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button type='button' className='primary' onClick={() => void handleSaveCoacheeEdit()}>Save coachee</button>
            </div>
          </div>
        </div>
      )}

      {addingCoachee && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)', display: 'grid', placeItems: 'center', zIndex: 60 }}>
          <div className='card' style={{ width: 'min(560px, 92vw)', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button
              type='button'
              aria-label='Close add coachee dialog'
              onClick={() => setAddingCoachee(false)}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'none', fontSize: 20, lineHeight: 1, cursor: 'pointer', color: '#475569' }}
            >
              x
            </button>
            <h3>Add coachee</h3>
            <form onSubmit={handleCreateCoachee}>
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
              <button type='submit' className='primary'>Create coachee</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
