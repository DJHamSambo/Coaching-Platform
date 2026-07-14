import type { NotificationItem } from '../types';

interface ActivityFeedProps {
  notifications: NotificationItem[];
  loading: boolean;
  error: string | null;
  onOpen: (notification: NotificationItem) => void;
  onMarkAllRead: () => void;
}

const TYPE_LABEL: Record<NotificationItem['type'], string> = {
  mention: 'Mention',
  session_booked: 'Session booked',
  task_assigned: 'Action assigned',
  action_created: 'Action assigned',
  plan_assigned: 'Plan assigned',
  resource_added: 'Resource shared',
};

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHours = Math.round(diffMin / 60);
  if (diffHours < 24) return `${diffHours} hr ago`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  return date.toLocaleString();
}

export function ActivityFeed({ notifications, loading, error, onOpen, onMarkAllRead }: ActivityFeedProps) {
  const hasUnread = notifications.some((item) => !item.isRead);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div>
          <h2>Activity</h2>
          <p className='muted'>Mentions, session bookings, and actions assigned to you — newest first.</p>
        </div>
        <button type='button' className='tab' onClick={onMarkAllRead} disabled={!hasUnread}>
          Mark all as read
        </button>
      </div>

      {loading && <p className='muted'>Loading activity…</p>}
      {error && <p className='muted' role='alert'>{error}</p>}

      {!loading && !error && notifications.length === 0 && (
        <div className='card'>
          <p className='muted'>No notifications yet. You're all caught up.</p>
        </div>
      )}

      {notifications.length > 0 && (
        <ul className='list' style={{ listStyle: 'none', padding: 0 }}>
          {notifications.map((item) => (
            <li key={item.id} style={{ marginBottom: 8 }}>
              <button
                type='button'
                className='card'
                onClick={() => onOpen(item)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  cursor: 'pointer',
                  border: item.isRead ? undefined : '1px solid #4f8cff',
                  background: item.isRead ? undefined : 'rgba(79, 140, 255, 0.08)',
                }}
                aria-label={`${item.isRead ? '' : 'Unread. '}${item.message}`}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <span className='muted' style={{ fontSize: '0.8rem' }}>{TYPE_LABEL[item.type]}</span>
                  <span className='muted' style={{ fontSize: '0.8rem' }}>{formatTimestamp(item.createdAt)}</span>
                </div>
                <div style={{ marginTop: 4 }}>
                  {!item.isRead && (
                    <span
                      aria-hidden='true'
                      style={{
                        display: 'inline-block',
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: '#4f8cff',
                        marginRight: 8,
                      }}
                    />
                  )}
                  {item.message}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
