import { useEffect, useState } from 'react';
import { createQuestionnaire, listQuestionnaires } from '../api';
import type { QuestionnaireItem } from '../types';

interface FoundationalQuestionnaireProps {
  currentUsername: string;
  /** When set, shows the foundational questionnaires submitted by this coachee
   * (read-only \u2014 coaches/admins cannot take a questionnaire on someone else's
   * behalf) instead of the signed-in user's own questionnaires. */
  coacheeId?: string;
}

const QUESTIONS = [
  'What would you like to be different as a result of Coaching?',
  'What habits do you have that you feel might interfere with your potential?',
  'What thoughts do you have that you feel might interfere with your potential?',
  'What motivates you?',
  'What does success mean for you?',
  'What do you need most from me as your Coach?',
] as const;

function formatSubmitted(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function FoundationalQuestionnaire({
  currentUsername,
  coacheeId,
}: FoundationalQuestionnaireProps): JSX.Element {
  const readOnly = Boolean(coacheeId);
  const [items, setItems] = useState<QuestionnaireItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState(currentUsername);
  const [answers, setAnswers] = useState<string[]>(() => QUESTIONS.map(() => ''));
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [viewing, setViewing] = useState<QuestionnaireItem | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listQuestionnaires(coacheeId)
      .then((data) => {
        if (!cancelled) {
          setItems(data);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError('Could not load questionnaires.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [coacheeId]);

  function openForm(): void {
    setName(currentUsername);
    setAnswers(QUESTIONS.map(() => ''));
    setFormError(null);
    setFormOpen(true);
  }

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setFormError(null);
    if (answers.every((value) => !value.trim())) {
      setFormError('Please answer at least one question before saving.');
      return;
    }
    setSaving(true);
    try {
      const created = await createQuestionnaire({
        name: name.trim(),
        answers: QUESTIONS.map((question, index) => ({
          question,
          answer: answers[index].trim(),
        })),
      });
      setItems((prev) => [created, ...prev]);
      setFormOpen(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not save questionnaire.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className='card' aria-labelledby='profile-questionnaires-heading'>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h2 id='profile-questionnaires-heading' style={{ margin: 0 }}>Foundational questionnaires</h2>
        {!readOnly && (
          <button type='button' className='primary' style={{ marginTop: 0 }} onClick={openForm}>
            Take Questionnaire
          </button>
        )}
      </div>

      {loading && <p className='muted'>Loading questionnaires...</p>}
      {error && <p className='muted' role='alert'>{error}</p>}

      {!loading && !error && items.length === 0 && (
        <p className='muted'>{readOnly ? 'This coachee has not submitted a foundational questionnaire yet.' : 'No questionnaires submitted yet.'}</p>
      )}

      {items.length > 0 && (
        <ul className='questionnaire-list'>
          {items.map((item) => (
            <li key={item.id}>
              <button type='button' className='questionnaire-list-item' onClick={() => setViewing(item)}>
                <span className='questionnaire-list-name'>{item.name || 'Foundational questionnaire'}</span>
                <span className='muted'>{formatSubmitted(item.submittedAt)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {formOpen && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button
              type='button'
              aria-label='Close questionnaire form'
              onClick={() => setFormOpen(false)}
              className='admin-panel-modal-close'
            >
              x
            </button>
            <h3>Foundational Questionnaire</h3>
            <form onSubmit={(e) => { void handleSubmit(e); }}>
              <label htmlFor='questionnaire-name'>Name</label>
              <input
                id='questionnaire-name'
                type='text'
                value={name}
                onChange={(e) => setName(e.target.value)}
              />

              {QUESTIONS.map((question, index) => (
                <div key={question}>
                  <label htmlFor={`questionnaire-q${index}`}>{index + 1}. {question}</label>
                  <textarea
                    id={`questionnaire-q${index}`}
                    rows={3}
                    value={answers[index]}
                    onChange={(e) => {
                      const next = e.target.value;
                      setAnswers((prev) => prev.map((value, i) => (i === index ? next : value)));
                    }}
                  />
                </div>
              ))}

              {formError && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{formError}</p>}

              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button type='submit' className='primary' style={{ marginTop: 0 }} disabled={saving}>
                  {saving ? 'Saving...' : 'Save questionnaire'}
                </button>
                <button type='button' onClick={() => setFormOpen(false)} disabled={saving}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {viewing && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button
              type='button'
              aria-label='Close questionnaire'
              onClick={() => setViewing(null)}
              className='admin-panel-modal-close'
            >
              x
            </button>
            <h3>Foundational Questionnaire</h3>
            <p className='muted'>
              {viewing.name ? `${viewing.name} · ` : ''}Submitted {formatSubmitted(viewing.submittedAt)}
            </p>
            <dl className='questionnaire-view'>
              {viewing.answers.map((entry, index) => (
                <div key={`${viewing.id}-${index}`}>
                  <dt>{index + 1}. {entry.question}</dt>
                  <dd>{entry.answer ? entry.answer : <span className='muted'>No answer provided.</span>}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}
    </section>
  );
}
