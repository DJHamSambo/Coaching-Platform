import { useState } from 'react';
import type { SessionItem } from '../types';

interface SessionPlannerProps {
  sessions: SessionItem[];
  onAddSession: (session: SessionItem) => void;
}

export function SessionPlanner({ sessions, onAddSession }: SessionPlannerProps) {
  const [title, setTitle] = useState('Coaching Session');
  const [date, setDate] = useState('');
  const [mode, setMode] = useState<'video' | 'in-person'>('video');
  const [requestedBy, setRequestedBy] = useState<'coach' | 'coachee'>('coachee');

  return (
    <div>
      <h2>Session Scheduling</h2>
      <p className='muted'>Capture upcoming coaching sessions and availability decisions.</p>
      <div className='card'>
        <h3>Request a session</h3>
        <label>Session title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>Date and time<input type='datetime-local' value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <label>
          Mode
          <select value={mode} onChange={(event) => setMode(event.target.value as 'video' | 'in-person')}>
            <option value='video'>Video</option>
            <option value='in-person'>In person</option>
          </select>
        </label>
        <label>
          Requested by
          <select value={requestedBy} onChange={(event) => setRequestedBy(event.target.value as 'coach' | 'coachee')}>
            <option value='coachee'>Coachee</option>
            <option value='coach'>Coach</option>
          </select>
        </label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            if (!date) return;
            onAddSession({ id: `session-${Date.now()}`, title: title.trim() || 'Coaching Session', date, mode, requestedBy });
          }}
        >
          Add session
        </button>
      </div>

      <div className='card'>
        <h3>Upcoming sessions</h3>
        <ul className='list'>
          {sessions.map((session) => (
            <li key={session.id}>
              <strong>{session.title}</strong>
              <div className='muted'>{new Date(session.date).toLocaleString()} · {session.mode} · requested by {session.requestedBy}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
