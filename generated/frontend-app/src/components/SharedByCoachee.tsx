import { useEffect, useState } from 'react';
import { getCoacheeSharedData } from '../api';
import type { SharedData } from '../types';

interface SharedByCoacheeProps {
  coacheeId: string;
  coacheeName: string;
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString();
}

/** Read-only view of what a coachee chose to share from their other coaching
 * relationships. The coachee controls this list and can revoke it any time. */
export function SharedByCoachee({ coacheeId, coacheeName }: SharedByCoacheeProps): JSX.Element {
  const [data, setData] = useState<SharedData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCoacheeSharedData(coacheeId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load shared items.');
      });
    return () => {
      cancelled = true;
    };
  }, [coacheeId]);

  const empty = data && data.plans.length + data.insights.length + data.questionnaires.length === 0;

  return (
    <section className='card' aria-labelledby='shared-by-coachee-heading'>
      <h2 id='shared-by-coachee-heading'>Shared by {coacheeName}</h2>
      <p className='muted'>
        Items {coacheeName} has chosen to share from previous coaching engagements. They are read-only and {coacheeName} can stop sharing them at any time.
      </p>
      {error && <p className='muted' role='alert'>{error}</p>}
      {!data && !error && <p className='muted'>Loading...</p>}
      {empty && <p className='muted'>Nothing has been shared with you.</p>}

      {data && data.plans.length > 0 && (
        <>
          <h3>Coaching plans</h3>
          {data.plans.map((plan) => (
            <details key={plan.shareId} style={{ marginBottom: 8 }}>
              <summary>
                <strong>{plan.title}</strong>
                <span className='muted'> · {plan.status.replace('_', ' ')} · shared {formatDate(plan.sharedAt)}</span>
              </summary>
              {plan.goal && <p><strong>Goal:</strong> {plan.goal}</p>}
              {plan.description && <p>{plan.description}</p>}
              {plan.actions.length > 0 && (
                <ul className='list'>
                  {plan.actions.map((action, index) => (
                    <li key={`${plan.shareId}-${index}`}>
                      {action.title}
                      <span className='muted'> · {action.status.replace('_', ' ')}{action.dueDate ? ` · due ${formatDate(action.dueDate)}` : ''}</span>
                    </li>
                  ))}
                </ul>
              )}
            </details>
          ))}
        </>
      )}

      {data && data.insights.length > 0 && (
        <>
          <h3>Insights</h3>
          <ul className='list'>
            {data.insights.map((insight) => (
              <li key={insight.shareId}>
                <strong>{insight.author}</strong> · {formatDate(insight.createdAt)}
                <div>{insight.note}</div>
              </li>
            ))}
          </ul>
        </>
      )}

      {data && data.questionnaires.length > 0 && (
        <>
          <h3>Foundational questionnaires</h3>
          {data.questionnaires.map((q) => (
            <details key={q.shareId} style={{ marginBottom: 8 }}>
              <summary>
                <strong>{q.name || 'Foundational questionnaire'}</strong>
                <span className='muted'> · submitted {formatDate(q.submittedAt)}</span>
              </summary>
              <dl className='questionnaire-view'>
                {q.answers.map((entry, index) => (
                  <div key={`${q.shareId}-${index}`}>
                    <dt>{index + 1}. {entry.question}</dt>
                    <dd>{entry.answer ? entry.answer : <span className='muted'>No answer provided.</span>}</dd>
                  </div>
                ))}
              </dl>
            </details>
          ))}
        </>
      )}
    </section>
  );
}
