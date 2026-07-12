import { useCallback, useEffect, useMemo, useState } from 'react';
import { PlanList } from './components/PlanList';
import { PlanDetail } from './components/PlanDetail';
import { CalendarPanel } from './components/CalendarPanel';
import { AdministrationPanel } from './components/AdministrationPanel';
import { InsightsJournal } from './components/InsightsJournal';
import { ResourceLibrary } from './components/ResourceLibrary';
import { ActivityFeed } from './components/ActivityFeed';
import { LoginScreen } from './components/LoginScreen';
import { ForcePasswordReset } from './components/ForcePasswordReset';
import {
  clearToken,
  createInsight,
  createPlan,
  deleteInsight,
  getMe,
  getToken,
  listAdminCoachees,
  listCoachDirectory,
  listInsights,
  listNotifications,
  listPlans,
  markAllNotificationsRead,
  markNotificationRead,
  updateInsight,
} from './api';
import { SESSION_EXPIRED_MESSAGE } from './constants/messages';
import type { AdminCoachee, AdminCoach, CoachingPlan, CurrentUser, InsightItem, NotificationItem } from './types';

const CALENDAR_FEATURE_ENABLED = import.meta.env.VITE_ENABLE_CALENDAR !== 'false';

const MODULES = [
  { key: 'plans', label: 'Coaching Plans', enabled: true },
  { key: 'insights', label: 'Insights', enabled: true },
  { key: 'calendar', label: 'Calendar', enabled: CALENDAR_FEATURE_ENABLED },
  { key: 'resources', label: 'Resources', enabled: true },
  { key: 'activity', label: 'Activity', enabled: true },
  { key: 'administration', label: 'Administration', enabled: true },
] as const;

type ModuleKey = (typeof MODULES)[number]['key'];

const MODULE_SUBTITLES: Record<CurrentUser['role'], Record<ModuleKey, string>> = {
  coach: {
    plans: 'Coaches can create one to many coaching plans for a coachee.',
    insights: 'Capture and revisit private reflections and progress notes for each coachee.',
    calendar: 'Schedule sessions and manage your availability with coachees.',
    resources: 'Upload and share documents, linking them to the coaching plans they support.',
    activity: 'Stay on top of mentions, session bookings, and actions assigned to you.',
    administration: 'Manage coaches, coachees, and their account access.',
  },
  admin: {
    plans: 'Oversee the coaching plans created across coaches and coachees.',
    insights: 'Review reflections and progress notes captured across the platform.',
    calendar: 'Oversee sessions and availability across coaches and coachees.',
    resources: 'Oversee documents shared across coaching plans on the platform.',
    activity: 'Stay on top of mentions, session bookings, and actions assigned to you.',
    administration: 'Manage coaches, coachees, and their account access.',
  },
  coachee: {
    plans: 'Follow the coaching plans your coach has created for you.',
    insights: 'Capture and revisit your private reflections and progress notes.',
    calendar: 'View upcoming sessions and request time with your coach.',
    resources: 'Upload and share documents with your coach to support your plans.',
    activity: 'Stay on top of mentions, session bookings, and actions assigned to you.',
    administration: 'Manage your account access.',
  },
};

export default function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  const enabledModules = useMemo(() => 
    MODULES.filter((item) => {
      // Hide administration from coachees
      if (item.key === 'administration' && currentUser?.role === 'coachee') {
        return false;
      }
      return item.enabled;
    }), [currentUser?.role]);
  const [activeModule, setActiveModule] = useState<ModuleKey>(enabledModules[0]?.key ?? 'plans');

  const [plans, setPlans] = useState<CoachingPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<CoachingPlan | null>(null);

  const [coachees, setCoachees] = useState<AdminCoachee[]>([]);
  const [coaches, setCoaches] = useState<AdminCoach[]>([]);
  const [coacheesLoading, setCoacheesLoading] = useState(true);
  const [coacheesError, setCoacheesError] = useState<string | null>(null);

  const [insights, setInsights] = useState<InsightItem[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [selectedInsightCoachee, setSelectedInsightCoachee] = useState<string | null>(null);

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState<string | null>(null);
  const [focusActionId, setFocusActionId] = useState<string | null>(null);
  const [focusResourceId, setFocusResourceId] = useState<string | null>(null);

  const unreadCount = useMemo(() => notifications.filter((item) => !item.isRead).length, [notifications]);

  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setAuthLoading(false);
      return () => {
        cancelled = true;
      };
    }

    getMe()
      .then((user) => {
        if (!cancelled) {
          setCurrentUser(user);
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearToken();
          setCurrentUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAuthLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function handleAuthExpired(): void {
      clearToken();
      setCurrentUser(null);
      setSelectedPlan(null);
      setSelectedInsightCoachee(null);
      setActiveModule('plans');
      setPlansError(SESSION_EXPIRED_MESSAGE);
    }

    window.addEventListener('auth:expired', handleAuthExpired);
    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    let cancelled = false;
    setPlansLoading(true);
    listPlans()
      .then((data) => {
        if (!cancelled) {
          setPlans(data);
          setPlansError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setPlansError('Could not load plans.');
      })
      .finally(() => {
        if (!cancelled) setPlansLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser || activeModule !== 'insights') return;
    let cancelled = false;
    setInsightsLoading(true);
    listInsights(currentUser.role === 'coach' ? selectedInsightCoachee : null)
      .then((items) => {
        if (!cancelled) {
          setInsights(items);
          setInsightsError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setInsightsError('Could not load insights.');
      })
      .finally(() => {
        if (!cancelled) setInsightsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeModule, currentUser, selectedInsightCoachee]);

  useEffect(() => {
    if (!currentUser) return;
    let cancelled = false;
    setCoacheesLoading(true);
    Promise.all([listAdminCoachees(), listCoachDirectory()])
      .then(([coacheesData, coachesData]) => {
        if (!cancelled) {
          setCoachees(coacheesData);
          setCoaches(coachesData);
          setCoacheesError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setCoacheesError('Could not load coachees.');
      })
      .finally(() => {
        if (!cancelled) setCoacheesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  const refreshNotifications = useCallback(async (): Promise<void> => {
    try {
      const items = await listNotifications();
      setNotifications(items);
      setNotificationsError(null);
    } catch {
      setNotificationsError('Could not load activity.');
    }
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    let cancelled = false;
    setNotificationsLoading(true);
    listNotifications()
      .then((items) => {
        if (!cancelled) {
          setNotifications(items);
          setNotificationsError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setNotificationsError('Could not load activity.');
      })
      .finally(() => {
        if (!cancelled) setNotificationsLoading(false);
      });

    const interval = setInterval(() => {
      listNotifications()
        .then((items) => {
          if (!cancelled) setNotifications(items);
        })
        .catch(() => {
          /* silent poll failure */
        });
    }, 20000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [currentUser]);

  async function handleOpenNotification(notification: NotificationItem): Promise<void> {
    if (!notification.isRead) {
      setNotifications((prev) =>
        prev.map((item) => (item.id === notification.id ? { ...item, isRead: true } : item)),
      );
      try {
        await markNotificationRead(notification.id);
      } catch {
        /* keep optimistic state; will resync on next poll */
      }
    }

    if ((notification.targetType === 'plan' || notification.targetType === 'action') && notification.planId) {
      const plan = plans.find((item) => item.id === notification.planId);
      if (plan) {
        setFocusActionId(
          notification.targetType === 'action' ? notification.actionId ?? notification.targetId : null,
        );
        setSelectedPlan(plan);
        setActiveModule('plans');
        return;
      }
    }
    if (notification.targetType === 'session') {
      setActiveModule('calendar');
      return;
    }
    if (notification.targetType === 'resource') {
      setFocusResourceId(notification.targetId ?? null);
      setActiveModule('resources');
      return;
    }
    if (notification.targetType === 'insight') {
      setActiveModule('insights');
      return;
    }
    setActiveModule('activity');
  }

  async function handleMarkAllNotificationsRead(): Promise<void> {
    setNotifications((prev) => prev.map((item) => ({ ...item, isRead: true })));
    try {
      await markAllNotificationsRead();
    } catch {
      void refreshNotifications();
    }
  }

  async function handleCreatePlan(planData: Omit<CoachingPlan, 'id' | 'createdAt' | 'coacheeName'>): Promise<void> {
    try {
      const created = await createPlan(planData);
      setPlans((prev) => [...prev, created].sort((a, b) => a.targetDate.localeCompare(b.targetDate)));
      setPlansError(null);
    } catch {
      setPlansError('Could not create plan. Please try again.');
    }
  }

  function handlePlanUpdated(updated: CoachingPlan): void {
    setPlans((prev) => prev.map((plan) => (plan.id === updated.id ? updated : plan)));
    setSelectedPlan(updated);
  }

  async function handleAddInsight(insight: InsightItem): Promise<void> {
    try {
      const created = await createInsight({ author: insight.author, note: insight.note, coacheeId: insight.coacheeId });
      setInsights((prev) => [created, ...prev]);
      setInsightsError(null);
    } catch {
      setInsightsError('Could not save insight. Please try again.');
    }
  }

  async function handleUpdateInsight(insightId: string, patch: { author: string; note: string; coacheeId?: string | null }): Promise<void> {
    try {
      const updated = await updateInsight(insightId, patch);
      setInsights((prev) => prev.map((item) => (item.id === insightId ? updated : item)));
      setInsightsError(null);
    } catch {
      setInsightsError('Could not update insight. Please try again.');
    }
  }

  async function handleDeleteInsight(insightId: string): Promise<void> {
    try {
      await deleteInsight(insightId);
      setInsights((prev) => prev.filter((item) => item.id !== insightId));
      setInsightsError(null);
    } catch {
      setInsightsError('Could not delete insight. Please try again.');
    }
  }

  async function handleAuthenticated(): Promise<void> {
    try {
      const user = await getMe();
      setCurrentUser(user);
      setActiveModule('plans');
    } catch {
      setCurrentUser(null);
    }
    setAuthLoading(false);
  }

  function handleLogout(): void {
    clearToken();
    setCurrentUser(null);
    setSelectedPlan(null);
    setSelectedInsightCoachee(null);
    setActiveModule('plans');
  }

  if (authLoading) {
    return (
      <main className='app-shell'>
        <p className='muted'>Loading session...</p>
      </main>
    );
  }

  if (!currentUser) {
    return <LoginScreen onAuthenticated={() => { void handleAuthenticated(); }} />;
  }

  if (currentUser.mustResetPassword) {
    return (
      <ForcePasswordReset
        username={currentUser.username}
        onComplete={() => { void handleAuthenticated(); }}
        onCancel={handleLogout}
      />
    );
  }

  return (
    <main className='app-shell'>
      <header className='hero'>
        <div className='hero-intro'>
          <h1>Coach</h1>
          <p className='subtitle'>{MODULE_SUBTITLES[currentUser.role][activeModule]}</p>
        </div>
        <div className='hero-account'>
          <p className='muted'>
            Signed in as {currentUser.username} ({currentUser.role})
          </p>
          <button type='button' className='tab' onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      <nav className='module-tabs' aria-label='Feature modules'>
        {enabledModules.map((module) => (
          <button
            key={module.key}
            className={module.key === activeModule ? 'tab active' : 'tab'}
            onClick={() => {
              setActiveModule(module.key);
              if (module.key === 'activity') {
                void refreshNotifications();
              }
            }}
            type='button'
          >
            {module.label}
            {module.key === 'activity' && unreadCount > 0 && (
              <span
                aria-label={`${unreadCount} unread`}
                style={{
                  marginLeft: 6,
                  background: '#e5484d',
                  color: '#fff',
                  borderRadius: 999,
                  padding: '0 6px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                }}
              >
                {unreadCount}
              </span>
            )}
          </button>
        ))}
      </nav>

      <section className='workspace'>
        {activeModule === 'plans' && !selectedPlan && (
          <PlanList
            plans={plans}
            coachees={coachees}
            onSelectPlan={setSelectedPlan}
            onCreatePlan={(data) => {
              void handleCreatePlan(data);
            }}
            canCreatePlan={currentUser.role !== 'coachee'}
            loading={plansLoading}
            error={plansError}
          />
        )}

        {activeModule === 'plans' && selectedPlan && (
          <PlanDetail
            plan={selectedPlan}
            coachees={coachees}
            coaches={coaches}
            currentUser={currentUser}
            onBack={() => setSelectedPlan(null)}
            onPlanUpdated={handlePlanUpdated}
            focusActionId={focusActionId}
            onFocusHandled={() => setFocusActionId(null)}
          />
        )}

        {activeModule === 'calendar' && <CalendarPanel coachees={coachees} currentUser={currentUser} />}

        {activeModule === 'resources' && (
          <ResourceLibrary
            plans={plans}
            currentUser={currentUser}
            focusResourceId={focusResourceId}
            onFocusHandled={() => setFocusResourceId(null)}
          />
        )}

        {activeModule === 'activity' && (
          <ActivityFeed
            notifications={notifications}
            loading={notificationsLoading}
            error={notificationsError}
            onOpen={(notification) => {
              void handleOpenNotification(notification);
            }}
            onMarkAllRead={() => {
              void handleMarkAllNotificationsRead();
            }}
          />
        )}

        {activeModule === 'insights' && (
          <>
            {insightsLoading && <p className='muted'>Loading insights...</p>}
            {insightsError && <p className='muted' role='alert'>{insightsError}</p>}
            <InsightsJournal
              insights={insights}
              coachees={coachees}
              currentUserRole={currentUser.role}
              currentUsername={currentUser.username}
              selectedFilterCoachee={selectedInsightCoachee}
              onFilterChange={setSelectedInsightCoachee}
              onAddInsight={(item) => {
                void handleAddInsight(item);
              }}
              onUpdateInsight={(insightId, patch) => {
                void handleUpdateInsight(insightId, patch);
              }}
              onDeleteInsight={(insightId) => {
                void handleDeleteInsight(insightId);
              }}
            />
          </>
        )}

        {activeModule === 'administration' && <AdministrationPanel currentUser={currentUser} />}
      </section>
    </main>
  );
}
