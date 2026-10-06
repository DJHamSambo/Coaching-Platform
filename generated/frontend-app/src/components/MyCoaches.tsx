import { useEffect, useState } from 'react';
import { listShareableItems, respondToRelationship, revokeShare, shareItem } from '../api';
import type { CoachingRelationship, ShareableItem, ShareableItems, ShareItemType } from '../types';

interface MyCoachesProps {
  relationships: CoachingRelationship[];
  loading: boolean;
  error: string | null;
  onRelationshipUpdated: (updated: CoachingRelationship) => void;
}

const STATUS_LABELS: Record<CoachingRelationship['status'], string> = {
  invited: 'Invitation pending',
  active: 'Active',
  declined: 'Declined',
  ended: 'Ended',
};

const SHARE_GROUPS: { key: keyof ShareableItems; type: ShareItemType; label: string }[] = [
  { key: 'plans', type: 'plan', label: 'Coaching plans' },
  { key: 'insights', type: 'insight', label: 'Insights' },
  { key: 'questionnaires', type: 'questionnaire', label: 'Foundational questionnaires' },
];

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString();
}

/** Lets a coachee choose, item by item, what one coach may see from their
 * other coaching relationships. Nothing is shared until they tick it. */
function SharingManager({
  relationship,
  onShareCountChange,
}: {
  relationship: CoachingRelationship;
  onShareCountChange: (delta: number) => void;
}): JSX.Element {
  const [items, setItems] = useState<ShareableItems | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listShareableItems(relationship.id)
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load what you can share.');
      });
    return () => {
      cancelled = true;
    };
  }, [relationship.id]);

  async function toggle(group: keyof ShareableItems, type: ShareItemType, item: ShareableItem): Promise<void> {
    const key = `${type}-${item.id}`;
    setBusyKey(key);
    setError(null);
    try {
      let shareId: string | null = null;
      if (item.shareId) {
        await revokeShare(relationship.id, item.shareId);
      } else {
        shareId = await shareItem(relationship.id, type, item.id);
      }
      setItems((prev) =>
        prev && {
          ...prev,
          [group]: prev[group].map((entry) => (entry.id === item.id ? { ...entry, shareId } : entry)),
        },
      );
      onShareCountChange(shareId ? 1 : -1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update sharing.');
    } finally {
      setBusyKey(null);
    }
  }

  if (error && !items) return <p className='muted' role='alert'>{error}</p>;
  if (!items) return <p className='muted'>Loading...</p>;

  const total = items.plans.length + items.insights.length + items.questionnaires.length;
  return (
    <div style={{ marginTop: 8 }}>
      <p className='muted' style={{ margin: '0 0 8px' }}>
        Tick anything from your other coaching relationships that you'd like {relationship.coachName} to see.
        They can read it but not change it, and you can untick it at any time.
      </p>
      {total === 0 && <p className='muted'>There's nothing from other coaching relationships to share yet.</p>}
      {error && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{error}</p>}
      {SHARE_GROUPS.map(({ key, type, label }) =>
        items[key].length === 0 ? null : (
          <fieldset key={key} style={{ border: 'none', padding: 0, margin: '0 0 12px' }}>
            <legend style={{ fontWeight: 600 }}>{label}</legend>
            {items[key].map((item) => (
              <label key={item.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontWeight: 'normal' }}>
                <input
                  type='checkbox'
                  checked={Boolean(item.shareId)}
                  disabled={busyKey === `${type}-${item.id}`}
                  onChange={() => { void toggle(key, type, item); }}
                  style={{ width: 'auto', marginTop: 4 }}
                />
                <span>
                  {item.label}
                  <span className='muted'> · {item.source}</span>
                </span>
              </label>
            ))}
          </fieldset>
        ),
      )}
    </div>
  );
}

export function MyCoaches({ relationships, loading, error, onRelationshipUpdated }: MyCoachesProps): JSX.Element {
  const [sharingOpenFor, setSharingOpenFor] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function respond(relationship: CoachingRelationship, action: 'accept' | 'decline' | 'end'): Promise<void> {
    if (action === 'end' && !window.confirm(`End your coaching relationship with ${relationship.coachName}? You'll keep your history, but they'll no longer see anything you've shared.`)) {
      return;
    }
    setBusyId(relationship.id);
    setActionError(null);
    try {
      const updated = await respondToRelationship(relationship.id, action);
      onRelationshipUpdated(updated);
      if (action !== 'accept') setSharingOpenFor(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not update this coaching relationship.');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className='card' aria-labelledby='my-coaches-heading'>
      <h2 id='my-coaches-heading'>My coaches</h2>
      <p className='muted'>
        Each coach only sees what you create together. Nothing from one coach is shared with another unless you choose to share it.
      </p>
      {loading && <p className='muted'>Loading your coaches...</p>}
      {error && <p className='muted' role='alert'>{error}</p>}
      {actionError && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{actionError}</p>}
      {!loading && !error && relationships.length === 0 && <p className='muted'>You don't have any coaches yet.</p>}

      <div style={{ display: 'grid', gap: 8 }}>
        {relationships.map((rel) => (
          <div key={rel.id} className='admin-panel-row' style={{ flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong>{rel.coachName}</strong>
              <p className='muted' style={{ margin: '4px 0 0' }}>
                {rel.status === 'invited'
                  ? `${rel.coachName} would like to start coaching you.`
                  : `${STATUS_LABELS[rel.status]}${rel.respondedAt ? ` since ${formatDate(rel.respondedAt)}` : ''}`}
                {rel.status === 'active' && rel.activeShareCount > 0 && ` · ${rel.activeShareCount} item(s) shared`}
              </p>
            </div>
            <div className='admin-panel-actions'>
              {rel.status === 'invited' && (
                <>
                  <button type='button' className='primary' disabled={busyId === rel.id} onClick={() => { void respond(rel, 'accept'); }}>
                    Accept
                  </button>
                  <button type='button' disabled={busyId === rel.id} onClick={() => { void respond(rel, 'decline'); }}>
                    Decline
                  </button>
                </>
              )}
              {rel.status === 'active' && (
                <>
                  <button type='button' onClick={() => setSharingOpenFor(sharingOpenFor === rel.id ? null : rel.id)}>
                    {sharingOpenFor === rel.id ? 'Close sharing' : 'Manage sharing'}
                  </button>
                  <button type='button' disabled={busyId === rel.id} onClick={() => { void respond(rel, 'end'); }}>
                    End relationship
                  </button>
                </>
              )}
            </div>
            {sharingOpenFor === rel.id && rel.status === 'active' && (
              <div style={{ flexBasis: '100%' }}>
                <SharingManager
                  relationship={rel}
                  onShareCountChange={(delta) =>
                    onRelationshipUpdated({ ...rel, activeShareCount: Math.max(0, rel.activeShareCount + delta) })
                  }
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
