import { useState } from 'react';
import { respondToRelationship } from '../api';
import type { AdminCoachee, CurrentUser, RelationshipStatus } from '../types';
import { CoachingContract } from './CoachingContract';
import { FoundationalQuestionnaire } from './FoundationalQuestionnaire';
import { SharedByCoachee } from './SharedByCoachee';

export const RELATIONSHIP_STATUS_LABELS: Record<RelationshipStatus, string> = {
  invited: 'Awaiting acceptance',
  active: 'Active',
  declined: 'Invitation declined',
  ended: 'Relationship ended',
};

interface CoacheeDetailPanelProps {
  coachee: AdminCoachee;
  currentUser: CurrentUser;
  onBack: () => void;
  focusContractId?: string | null;
  onFocusHandled?: () => void;
  onCoacheeUpdated?: (coachee: AdminCoachee) => void;
}

export function CoacheeDetailPanel({
  coachee,
  currentUser,
  onBack,
  focusContractId,
  onFocusHandled,
  onCoacheeUpdated,
}: CoacheeDetailPanelProps): JSX.Element {
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState<string | null>(null);
  // Only the coach in this relationship can end it (admins oversee, they don't coach).
  const canEnd = coachee.status === 'active' && coachee.addedById === currentUser.id;

  async function handleEnd(): Promise<void> {
    if (!window.confirm(`End your coaching relationship with ${coachee.name}? You'll keep your records, but anything they shared with you will no longer be visible.`)) {
      return;
    }
    setEnding(true);
    setEndError(null);
    try {
      const updated = await respondToRelationship(coachee.id, 'end');
      onCoacheeUpdated?.({ ...coachee, status: updated.status });
    } catch (err) {
      setEndError(err instanceof Error ? err.message : 'Could not end this relationship.');
    } finally {
      setEnding(false);
    }
  }

  return (
    <div>
      <button
        type='button'
        onClick={onBack}
        style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', padding: 0, fontSize: 14, marginBottom: 8 }}
      >
        ← Back to coachees
      </button>

      <section className='card' aria-labelledby='coachee-detail-heading'>
        <h2 id='coachee-detail-heading'>{coachee.name}</h2>
        <dl className='questionnaire-view'>
          <div>
            <dt>Relationship</dt>
            <dd>{RELATIONSHIP_STATUS_LABELS[coachee.status]}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{coachee.email || <span className='muted'>No email on file</span>}</dd>
          </div>
          {coachee.userUsername && (
            <div>
              <dt>Linked login</dt>
              <dd>{coachee.userUsername}</dd>
            </div>
          )}
          {coachee.userPhone && (
            <div>
              <dt>Contact phone number</dt>
              <dd>{coachee.userPhone}</dd>
            </div>
          )}
          <div>
            <dt>Notes</dt>
            <dd>{coachee.notes || <span className='muted'>No notes on file</span>}</dd>
          </div>
          {currentUser.isAdmin && (
            <div>
              <dt>Added by</dt>
              <dd>{coachee.addedByUsername || 'Unknown'}</dd>
            </div>
          )}
        </dl>
        {coachee.status === 'invited' && (
          <p className='muted'>
            {coachee.name} hasn&apos;t accepted yet. You can prepare plans and contracts now; they&apos;ll see them and be notified about new activity once they accept.
          </p>
        )}
        {canEnd && (
          <button type='button' onClick={() => { void handleEnd(); }} disabled={ending}>
            {ending ? 'Ending...' : 'End coaching relationship'}
          </button>
        )}
        {endError && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{endError}</p>}
        {!coachee.user && (
          <p className='muted'>
            This coachee does not have a linked login yet, so they cannot sign in to sign contracts or take a foundational questionnaire themselves.
          </p>
        )}
      </section>

      <CoachingContract
        currentUser={currentUser}
        coacheeFilter={coachee}
        focusContractId={focusContractId}
        onFocusHandled={onFocusHandled}
      />

      <FoundationalQuestionnaire currentUsername={currentUser.username} coacheeId={coachee.id} />

      {coachee.status === 'active' && coachee.user && (
        <SharedByCoachee coacheeId={coachee.id} coacheeName={coachee.name} />
      )}
    </div>
  );
}
