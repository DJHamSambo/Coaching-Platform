import { useState } from 'react';
import type { Coachee } from '../types';
import { createCoachee } from '../api';

interface CoacheesManagerProps {
  coachees: Coachee[];
  onAdded: (coachee: Coachee) => void;
  loading: boolean;
  error: string | null;
}

export function CoacheesManager({ coachees, onAdded, loading, error }: CoacheesManagerProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      const created = await createCoachee({ name: name.trim(), email: email.trim() || undefined });
      onAdded(created);
      setName('');
      setEmail('');
    } catch {
      setFormError('Could not save coachee. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h2>Coachees</h2>
      <p className='muted'>Manage the coachees you work with. Coachees can be assigned to coaching plans.</p>

      {error && <p className='muted' style={{ color: '#c0392b' }}>{error}</p>}
      {loading && <p className='muted'>Loading coachees…</p>}

      <form className='card' onSubmit={handleSubmit} style={{ marginBottom: 24 }}>
        <h3>Add coachee</h3>
        <label>
          Name *
          <input required value={name} onChange={(e) => setName(e.target.value)} placeholder='Full name' />
        </label>
        <label>
          Email
          <input type='email' value={email} onChange={(e) => setEmail(e.target.value)} placeholder='Optional' />
        </label>
        {formError && <p style={{ color: '#c0392b', margin: 0, fontSize: 14 }}>{formError}</p>}
        <button type='submit' className='primary' disabled={saving}>{saving ? 'Saving…' : 'Add coachee'}</button>
      </form>

      {!loading && coachees.length === 0 && (
        <div className='card' style={{ textAlign: 'center', padding: '32px 16px' }}>
          <p className='muted'>No coachees added yet.</p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {coachees.map((c) => (
          <div key={c.id} className='card' style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>{c.name}</strong>
              {c.email && <span className='muted' style={{ marginLeft: 12, fontSize: 13 }}>{c.email}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
