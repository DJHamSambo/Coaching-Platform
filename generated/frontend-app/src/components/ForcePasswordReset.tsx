import { useMemo, useState } from 'react';
import { changePassword } from '../api';

interface ForcePasswordResetProps {
  username: string;
  onComplete: () => void;
  onCancel: () => void;
}

interface Rule {
  label: string;
  test: (value: string) => boolean;
}

const PASSWORD_RULES: Rule[] = [
  { label: 'At least 12 characters', test: (v) => v.length >= 12 },
  { label: 'An uppercase letter', test: (v) => /[A-Z]/.test(v) },
  { label: 'A lowercase letter', test: (v) => /[a-z]/.test(v) },
  { label: 'A number', test: (v) => /\d/.test(v) },
  { label: 'A special character', test: (v) => /[^A-Za-z0-9]/.test(v) },
];

export function ForcePasswordReset({ username, onComplete, onCancel }: ForcePasswordResetProps) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const ruleResults = useMemo(
    () => PASSWORD_RULES.map((rule) => ({ label: rule.label, met: rule.test(newPassword) })),
    [newPassword],
  );
  const allRulesMet = ruleResults.every((r) => r.met);
  const passwordsMatch = newPassword.length > 0 && newPassword === confirmPassword;
  const canSubmit = currentPassword.length > 0 && allRulesMet && passwordsMatch && !submitting;

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);

    if (!allRulesMet) {
      setError('Your new password does not meet the requirements below.');
      return;
    }
    if (!passwordsMatch) {
      setError('The new passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ currentPassword, newPassword });
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update your password. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className='app-shell' style={{ maxWidth: 460, margin: '80px auto' }}>
      <div className='card'>
        <h1 style={{ marginBottom: 4 }}>Set a new password</h1>
        <p className='muted' style={{ marginBottom: 24 }}>
          Welcome, {username}. For your security, please choose a new password before continuing.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <input type='text' name='username' value={username} autoComplete='username' readOnly hidden />

          <label>
            Temporary password
            <input
              autoFocus
              required
              type='password'
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete='current-password'
            />
          </label>

          <label>
            New password
            <input
              required
              type='password'
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete='new-password'
            />
          </label>

          <label>
            Confirm new password
            <input
              required
              type='password'
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete='new-password'
            />
          </label>

          <ul style={{ listStyle: 'none', padding: 0, margin: '4px 0', fontSize: 13 }}>
            {ruleResults.map((rule) => (
              <li key={rule.label} style={{ color: rule.met ? '#15803d' : '#6b7280' }}>
                {rule.met ? '✓' : '○'} {rule.label}
              </li>
            ))}
            {confirmPassword.length > 0 && (
              <li style={{ color: passwordsMatch ? '#15803d' : '#6b7280' }}>
                {passwordsMatch ? '✓' : '○'} Passwords match
              </li>
            )}
          </ul>

          {error && <p style={{ color: '#c0392b', margin: 0, fontSize: 14 }} role='alert'>{error}</p>}

          <button type='submit' className='primary' disabled={!canSubmit}>
            {submitting ? 'Updating…' : 'Update password'}
          </button>
        </form>

        <p style={{ marginTop: 16, fontSize: 14, textAlign: 'center' }}>
          <button
            type='button'
            style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', padding: 0, fontSize: 'inherit' }}
            onClick={onCancel}
          >
            Sign out
          </button>
        </p>
      </div>
    </main>
  );
}
