import { useState } from 'react';
import type { InsightItem } from '../types';

interface InsightsJournalProps {
  insights: InsightItem[];
  onAddInsight: (insight: InsightItem) => void;
}

export function InsightsJournal({ insights, onAddInsight }: InsightsJournalProps) {
  const [author, setAuthor] = useState('Coach');
  const [note, setNote] = useState('');

  return (
    <div>
      <h2>Insights and Journal</h2>
      <p className='muted'>Track coach insights and coachee reflections in chronological order.</p>
      <div className='card'>
        <h3>Add insight</h3>
        <label>
          Author
          <select value={author} onChange={(event) => setAuthor(event.target.value)}>
            <option>Coach</option>
            <option>Coachee</option>
          </select>
        </label>
        <label>Note<textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} /></label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = note.trim();
            if (!trimmed) return;
            onAddInsight({ id: `insight-${Date.now()}`, author, note: trimmed, createdAt: new Date().toISOString().slice(0, 10) });
            setNote('');
          }}
        >
          Save note
        </button>
      </div>

      <div className='card'>
        <h3>Timeline</h3>
        <ul className='list'>
          {insights.map((insight) => (
            <li key={insight.id}>
              <strong>{insight.author}</strong> · {insight.createdAt}
              <div>{insight.note}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
