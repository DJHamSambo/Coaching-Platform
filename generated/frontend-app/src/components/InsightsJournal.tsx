import { useState } from 'react';
import type { InsightItem, Coachee } from '../types';

interface InsightsJournalProps {
  insights: InsightItem[];
  coachees: Coachee[];
  currentUserRole: 'admin' | 'coach' | 'coachee';
  currentUsername: string;
  onAddInsight: (insight: InsightItem) => void;
  onUpdateInsight: (insightId: string, patch: { author: string; note: string; coacheeId?: string | null }) => void;
  onDeleteInsight: (insightId: string) => void;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function InsightsJournal({
  insights,
  coachees,
  currentUserRole,
  currentUsername,
  onAddInsight,
  onUpdateInsight,
  onDeleteInsight,
}: InsightsJournalProps) {
  const [note, setNote] = useState('');
  const [selectedCoachee, setSelectedCoachee] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editNote, setEditNote] = useState('');
  const [editCoachee, setEditCoachee] = useState<string | null>(null);

  const isCacheCoach = currentUserRole === 'coach';

  return (
    <div>
      <h2>Insights and Journal</h2>
      <p className='muted'>
        {isCacheCoach
          ? 'Track insights for your coachees and add your own coaching notes.'
          : 'Track insights shared by your coaches and add your own reflections.'}
      </p>
      <div className='card'>
        <h3>Add insight</h3>
        {isCacheCoach && (
          <label>
            Assign to coachee (optional)
            <select value={selectedCoachee || ''} onChange={(event) => setSelectedCoachee(event.target.value || null)}>
              <option value=''>None (personal note)</option>
              {coachees.map((coachee) => (
                <option key={coachee.id} value={coachee.id}>
                  {coachee.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Note
          <textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = note.trim();
            if (!trimmed) return;
            onAddInsight({
              id: `insight-${Date.now()}`,
              author: currentUsername,
              note: trimmed,
              createdAt: new Date().toISOString(),
              coacheeId: isCacheCoach ? selectedCoachee : null,
            });
            setNote('');
            setSelectedCoachee(null);
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
              {editingId === insight.id ? (
                <>
                  {isCacheCoach && (
                    <label>
                      Assign to coachee (optional)
                      <select
                        value={editCoachee || ''}
                        onChange={(event) => setEditCoachee(event.target.value || null)}
                      >
                        <option value=''>None (personal note)</option>
                        {coachees.map((coachee) => (
                          <option key={coachee.id} value={coachee.id}>
                            {coachee.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label>
                    Note
                    <textarea rows={3} value={editNote} onChange={(event) => setEditNote(event.target.value)} />
                  </label>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button
                      type='button'
                      className='primary'
                      onClick={() => {
                        const trimmed = editNote.trim();
                        if (!trimmed) return;
                        onUpdateInsight(insight.id, {
                          author: insight.author,
                          note: trimmed,
                          coacheeId: isCacheCoach ? editCoachee : undefined,
                        });
                        setEditingId(null);
                      }}
                    >
                      Save
                    </button>
                    <button
                      type='button'
                      onClick={() => {
                        setEditingId(null);
                        setEditNote('');
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <strong>{insight.author}</strong> · {formatTimestamp(insight.createdAt)}
                  {insight.coacheeName && <div className='muted'>for {insight.coacheeName}</div>}
                  <div>{insight.note}</div>
                  <div className='muted' style={{ marginTop: 4 }}>
                    Last updated: {formatTimestamp(insight.updatedAt ?? insight.createdAt)}
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button
                      type='button'
                      onClick={() => {
                        setEditingId(insight.id);
                        setEditNote(insight.note);
                        setEditCoachee(insight.coacheeId || null);
                      }}
                    >
                      Edit
                    </button>
                    <button type='button' onClick={() => onDeleteInsight(insight.id)}>
                      Delete
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
