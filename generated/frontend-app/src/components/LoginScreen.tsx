import { useState } from 'react';
import { login, register, setAuthTokens, setCurrentUsername } from '../api';

interface LoginScreenProps {
  onAuthenticated: (username: string) => void;
}

export function LoginScreen({ onAuthenticated }: LoginScreenProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === 'register') {
        await register({ username, password, email });
      }
      const tokens = await login({ username, password });
      setAuthTokens(tokens);
      setCurrentUsername(username);
      onAuthenticated(username);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className='app-shell' style={{ maxWidth: 420, margin: '80px auto' }}>
      <div className='card'>
        <h1 style={{ marginBottom: 4 }}>Coaching Platform</h1>
        <p className='muted' style={{ marginBottom: 24 }}>
          {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label>
            Username
            <input
              autoFocus
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete='username'
            />
          </label>

          {mode === 'register' && (
            <label>
              Email (optional)
              <input
                type='email'
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete='email'
              />
            </label>
          )}

          <label>
            Password
            <input
              required
              type='password'
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </label>

          {error && (
            <p style={{ color: '#c0392b', margin: 0, fontSize: 14 }}>{error}</p>
          )}

          <button type='submit' className='primary' disabled={loading}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p style={{ marginTop: 16, fontSize: 14, textAlign: 'center' }}>
          {mode === 'login' ? (
            <>No account? <button type='button' style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', padding: 0, fontSize: 'inherit' }} onClick={() => setMode('register')}>Register</button></>
          ) : (
            <>Already have an account? <button type='button' style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', padding: 0, fontSize: 'inherit' }} onClick={() => setMode('login')}>Sign in</button></>
          )}
        </p>
      </div>
    </main>
  );
}
