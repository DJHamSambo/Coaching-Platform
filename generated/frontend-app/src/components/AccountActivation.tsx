import { useEffect, useMemo, useState } from 'react';
import { activateAccount, validateActivationToken } from '../api';

interface AccountActivationProps {
  token: string;
  onDone: () => void;
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

type Phase = 'validating' | 'invalid' | 'ready' | 'done';

export function AccountActivation({ token, onDone }: AccountActivationProps) {
  const [phase, setPhase] = useState<Phase>('validating');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setPhase('validating');
    validateActivationToken(token)
      .then((result) => {
        if (cancelled) return;
        setUsername(result.username);
        setEmail(result.email);
        setPhase('ready');
      })
      .catch(() => {
        if (!cancelled) setPhase('invalid');
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const ruleResults = useMemo(
    () => PASSWORD_RULES.map((rule) => ({ label: rule.label, met: rule.test(newPassword) })),
    [newPassword],
  );
  const allRulesMet = ruleResults.every((r) => r.met);
  const passwordsMatch = newPassword.length > 0 && newPassword === confirmPassword;
  const canSubmit = allRulesMet && passwordsMatch && !submitting;

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);

    if (!allRulesMet) {
      setError('Your password does not meet the requirements below.');
      return;
    }
    if (!passwordsMatch) {
      setError('The passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      await activateAccount({ token, newPassword });
      setPhase('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not activate your account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  if (phase === 'validating') {
    return (
      <main className='app-shell' style={{ maxWidth: 460, margin: '80px auto' }}>
        <p className='muted'>Checking your activation link...</p>
      </main>
    );
  }

  if (phase === 'invalid') {
    return (
      <main className='app-shell' style={{ maxWidth: 460, margin: '80px auto' }}>
        <div className='card'>
          <h1 style={{ marginBottom: 4 }}>Link no longer valid</h1>
          <p className='muted' style={{ marginBottom: 24 }}>
            This activation link is invalid, has expired, or has already been used. Please ask your
            coach or an administrator to resend the invitation.
          </p>
          <button type='button' className='tab' onClick={onDone}>
            Go to sign in
          </button>
        </div>
      </main>
    );
  }

  if (phase === 'done') {
    return (
      <main className='app-shell' style={{ maxWidth: 460, margin: '80px auto' }}>
        <div className='card'>
          <h1 style={{ marginBottom: 4 }}>Account activated</h1>
          <p className='muted' style={{ marginBottom: 12 }}>
            Your email is verified and your password is set. You can now sign in.
          </p>
          <p style={{ marginBottom: 24, fontSize: 14 }}>
            Sign in with your email (<strong>{email}</strong>) or your username (<strong>{username}</strong>) and the password you just set.
          </p>
          <button type='button' className='primary' onClick={onDone}>
            Continue to sign in
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className='app-shell' style={{ maxWidth: 460, margin: '80px auto' }}>
      <div className='card'>
        <h1 style={{ marginBottom: 4 }}>Activate your account</h1>
        <p className='muted' style={{ marginBottom: 24 }}>
          Welcome, {username}. Confirm your email ({email}) by choosing a password below.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <input type='text' name='username' value={username} autoComplete='username' readOnly hidden />

          <label>
            New password
            <input
              autoFocus
              required
              type='password'
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete='new-password'
            />
          </label>

          <label>
            Confirm password
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

          {error && (
            <p style={{ color: '#c0392b', margin: 0, fontSize: 14 }} role='alert'>
              {error}
            </p>
          )}

          <button type='submit' className='primary' disabled={!canSubmit}>
            {submitting ? 'Activating...' : 'Verify email & set password'}
          </button>
        </form>
      </div>
    </main>
  );
}
