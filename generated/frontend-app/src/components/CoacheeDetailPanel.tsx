import type { AdminCoachee, CurrentUser } from '../types';
import { CoachingContract } from './CoachingContract';
import { FoundationalQuestionnaire } from './FoundationalQuestionnaire';

interface CoacheeDetailPanelProps {
  coachee: AdminCoachee;
  currentUser: CurrentUser;
  onBack: () => void;
  focusContractId?: string | null;
  onFocusHandled?: () => void;
}

export function CoacheeDetailPanel({
  coachee,
  currentUser,
  onBack,
  focusContractId,
  onFocusHandled,
}: CoacheeDetailPanelProps): JSX.Element {
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
    </div>
  );
}
