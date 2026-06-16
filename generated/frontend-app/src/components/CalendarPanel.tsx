import { useEffect, useMemo, useState } from 'react';
import {
  createAvailabilityWindow,
  createSession,
  createUnavailablePeriod,
  deleteAvailabilityWindow,
  deleteSession,
  deleteUnavailablePeriod,
  listAvailabilityWindows,
  listSessions,
  listUnavailablePeriods,
  updateUnavailablePeriod,
  updateSession,
} from '../api';
import type { AdminCoachee, CalendarSession, UnavailablePeriod, WeeklyAvailabilityWindow } from '../types';

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
type CalendarViewMode = 'month' | 'week' | 'year';
const WEEK_START_STORAGE_KEY = 'calendar_week_start_hour';
const WEEK_END_STORAGE_KEY = 'calendar_week_end_hour';

interface CalendarPanelProps {
  coachees: AdminCoachee[];
}

interface SessionFormState {
  id: string | null;
  title: string;
  date: string;
  durationMinutes: number;
  coacheeId: string;
  notes: string;
}

interface UnavailableFormState {
  id: string | null;
  startAt: string;
  endAt: string;
  reason: string;
}

const EMPTY_SESSION_FORM: SessionFormState = {
  id: null,
  title: 'Coaching Session',
  date: '',
  durationMinutes: 60,
  coacheeId: '',
  notes: '',
};

const EMPTY_UNAVAILABLE_EDIT_FORM: UnavailableFormState = {
  id: null,
  startAt: '',
  endAt: '',
  reason: '',
};

function createDefaultUnavailableForm(): UnavailableFormState {
  const start = new Date();
  start.setHours(9, 0, 0, 0);
  const end = new Date(start);
  end.setHours(10, 0, 0, 0);
  return {
    id: null,
    startAt: toDateInputValue(start),
    endAt: toDateInputValue(end),
    reason: '',
  };
}

function toDateInputValue(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  const hours = String(value.getHours()).padStart(2, '0');
  const minutes = String(value.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function toLocalDateTimeInputValue(dateText: string): string {
  const parsed = new Date(dateText);
  if (Number.isNaN(parsed.getTime())) {
    return dateText.slice(0, 16);
  }
  return toDateInputValue(parsed);
}

function toDateKey(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function formatHourLabel(hour: number): string {
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const normalized = hour % 12 === 0 ? 12 : hour % 12;
  return `${normalized}:00 ${suffix}`;
}

function getStoredHour(key: string, fallback: number): number {
  const raw = window.localStorage.getItem(key);
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value)) return fallback;
  return Math.min(23, Math.max(0, Math.trunc(value)));
}

export function CalendarPanel({ coachees }: CalendarPanelProps) {
  const [monthCursor, setMonthCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [viewMode, setViewMode] = useState<CalendarViewMode>('month');
  const [weekStartHour, setWeekStartHour] = useState(() => getStoredHour(WEEK_START_STORAGE_KEY, 7));
  const [weekEndHour, setWeekEndHour] = useState(() => getStoredHour(WEEK_END_STORAGE_KEY, 20));
  const [sessions, setSessions] = useState<CalendarSession[]>([]);
  const [availability, setAvailability] = useState<WeeklyAvailabilityWindow[]>([]);
  const [unavailablePeriods, setUnavailablePeriods] = useState<UnavailablePeriod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showSessionModal, setShowSessionModal] = useState(false);
  const [sessionForm, setSessionForm] = useState<SessionFormState>(EMPTY_SESSION_FORM);
  const [showUnavailableModal, setShowUnavailableModal] = useState(false);
  const [unavailableEditForm, setUnavailableEditForm] = useState<UnavailableFormState>(EMPTY_UNAVAILABLE_EDIT_FORM);

  const [availabilityForm, setAvailabilityForm] = useState({ weekdays: [0], startTime: '09:00', endTime: '17:00' });

  function toggleAvailabilityDay(weekday: number): void {
    setAvailabilityForm((prev) => {
      const exists = prev.weekdays.includes(weekday);
      const nextWeekdays = exists ? prev.weekdays.filter((value) => value !== weekday) : [...prev.weekdays, weekday].sort((a, b) => a - b);
      return { ...prev, weekdays: nextWeekdays };
    });
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([listSessions(), listAvailabilityWindows(), listUnavailablePeriods()])
      .then(([sessionsData, availabilityData, unavailableData]) => {
        if (cancelled) return;
        setSessions(sessionsData);
        setAvailability(availabilityData);
        setUnavailablePeriods(unavailableData);
        setError(null);
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load calendar data.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    window.localStorage.setItem(WEEK_START_STORAGE_KEY, String(weekStartHour));
  }, [weekStartHour]);

  useEffect(() => {
    window.localStorage.setItem(WEEK_END_STORAGE_KEY, String(weekEndHour));
  }, [weekEndHour]);

  const calendarTitle = useMemo(() => {
    if (viewMode === 'year') {
      return String(monthCursor.getFullYear());
    }
    if (viewMode === 'week') {
      const start = new Date(monthCursor);
      start.setDate(monthCursor.getDate() - ((monthCursor.getDay() + 6) % 7));
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      return `${start.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })}`;
    }
    return monthCursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  }, [monthCursor, viewMode]);

  const calendarDays = useMemo(() => {
    if (viewMode === 'week') {
      const start = new Date(monthCursor);
      start.setDate(monthCursor.getDate() - ((monthCursor.getDay() + 6) % 7));
      const cells: Array<{ date: Date; inCurrentMonth: boolean }> = [];
      for (let i = 0; i < 7; i += 1) {
        const day = new Date(start);
        day.setDate(start.getDate() + i);
        cells.push({ date: day, inCurrentMonth: true });
      }
      return cells;
    }

    const year = monthCursor.getFullYear();
    const month = monthCursor.getMonth();
    const first = new Date(year, month, 1);
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const offset = (first.getDay() + 6) % 7;
    const cells: Array<{ date: Date; inCurrentMonth: boolean }> = [];

    for (let i = offset; i > 0; i -= 1) {
      cells.push({ date: new Date(year, month, 1 - i), inCurrentMonth: false });
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      cells.push({ date: new Date(year, month, day), inCurrentMonth: true });
    }

    while (cells.length < 42) {
      const nextIndex = cells.length - (offset + daysInMonth) + 1;
      cells.push({ date: new Date(year, month + 1, nextIndex), inCurrentMonth: false });
    }

    return cells;
  }, [monthCursor, viewMode]);

  const weekDays = useMemo(() => {
    const start = new Date(monthCursor);
    start.setDate(monthCursor.getDate() - ((monthCursor.getDay() + 6) % 7));
    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      return date;
    });
  }, [monthCursor]);

  const weekHours = useMemo(() => {
    const start = Math.min(weekStartHour, weekEndHour - 1);
    const end = Math.max(weekEndHour, start + 1);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }, [weekStartHour, weekEndHour]);

  const sessionsByDate = useMemo(() => {
    const buckets = new Map<string, CalendarSession[]>();
    for (const session of sessions) {
      const key = session.date.slice(0, 10);
      const existing = buckets.get(key) ?? [];
      existing.push(session);
      buckets.set(key, existing);
    }
    for (const values of buckets.values()) {
      values.sort((a, b) => a.date.localeCompare(b.date));
    }
    return buckets;
  }, [sessions]);

  const unavailableByDate = useMemo(() => {
    const buckets = new Map<string, UnavailablePeriod[]>();

    for (const period of unavailablePeriods) {
      const start = new Date(period.startAt);
      const end = new Date(period.endAt);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        continue;
      }

      const current = new Date(start.getFullYear(), start.getMonth(), start.getDate());
      const endDate = new Date(end.getFullYear(), end.getMonth(), end.getDate());

      while (current <= endDate) {
        const key = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`;
        const existing = buckets.get(key) ?? [];
        existing.push(period);
        buckets.set(key, existing);
        current.setDate(current.getDate() + 1);
      }
    }

    return buckets;
  }, [unavailablePeriods]);

  const weekSessionsByHour = useMemo(() => {
    const buckets = new Map<string, CalendarSession[]>();
    for (const session of sessions) {
      const startAt = new Date(session.date);
      if (Number.isNaN(startAt.getTime())) continue;
      const key = `${toDateKey(startAt)}|${startAt.getHours()}`;
      const existing = buckets.get(key) ?? [];
      existing.push(session);
      buckets.set(key, existing);
    }
    return buckets;
  }, [sessions]);

  const weekUnavailableByHour = useMemo(() => {
    const buckets = new Map<string, UnavailablePeriod[]>();

    for (const period of unavailablePeriods) {
      const start = new Date(period.startAt);
      const end = new Date(period.endAt);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) continue;

      for (const day of weekDays) {
        const dayKey = toDateKey(day);
        for (const hour of weekHours) {
          const slotStart = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, 0, 0, 0);
          const slotEnd = new Date(slotStart);
          slotEnd.setHours(slotStart.getHours() + 1);
          if (start < slotEnd && end > slotStart) {
            const key = `${dayKey}|${hour}`;
            const existing = buckets.get(key) ?? [];
            existing.push(period);
            buckets.set(key, existing);
          }
        }
      }
    }

    return buckets;
  }, [unavailablePeriods, weekDays, weekHours]);

  function handleToday(): void {
    const now = new Date();
    if (viewMode === 'year') {
      setMonthCursor(new Date(now.getFullYear(), 0, 1));
      return;
    }
    setMonthCursor(now);
  }

  const yearMonthSummary = useMemo(() => {
    const year = monthCursor.getFullYear();
    return Array.from({ length: 12 }, (_, month) => {
      const prefix = `${year}-${String(month + 1).padStart(2, '0')}`;
      let sessionCount = 0;
      let unavailableCount = 0;

      for (const [dayKey, daySessions] of sessionsByDate.entries()) {
        if (dayKey.startsWith(prefix)) {
          sessionCount += daySessions.length;
        }
      }

      for (const [dayKey, dayUnavailable] of unavailableByDate.entries()) {
        if (dayKey.startsWith(prefix)) {
          unavailableCount += dayUnavailable.length;
        }
      }

      return {
        month,
        label: new Date(year, month, 1).toLocaleDateString(undefined, { month: 'long' }),
        sessionCount,
        unavailableCount,
      };
    });
  }, [monthCursor, sessionsByDate, unavailableByDate]);

  function handlePreviousView(): void {
    if (viewMode === 'year') {
      setMonthCursor((prev) => new Date(prev.getFullYear() - 1, 0, 1));
      return;
    }
    if (viewMode === 'week') {
      setMonthCursor((prev) => {
        const next = new Date(prev);
        next.setDate(prev.getDate() - 7);
        return next;
      });
      return;
    }
    setMonthCursor((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  }

  function handleNextView(): void {
    if (viewMode === 'year') {
      setMonthCursor((prev) => new Date(prev.getFullYear() + 1, 0, 1));
      return;
    }
    if (viewMode === 'week') {
      setMonthCursor((prev) => {
        const next = new Date(prev);
        next.setDate(prev.getDate() + 7);
        return next;
      });
      return;
    }
    setMonthCursor((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  }

  function openCreateSession(dayDate?: Date): void {
    const defaultCoachee = coachees[0]?.id ?? '';
    const start = dayDate ? new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate(), 9, 0, 0) : new Date();
    if (!dayDate) {
      start.setHours(9, 0, 0, 0);
    }
    const defaultDate = toDateInputValue(start);
    setSessionForm({ ...EMPTY_SESSION_FORM, date: defaultDate, coacheeId: defaultCoachee });
    setShowSessionModal(true);
  }

  function openEditSession(session: CalendarSession): void {
    const localDate = toLocalDateTimeInputValue(session.date);
    setSessionForm({
      id: session.id,
      title: session.title,
      date: localDate,
      durationMinutes: session.durationMinutes,
      coacheeId: session.coacheeId ?? '',
      notes: session.notes,
    });
    setShowSessionModal(true);
  }

  async function handleSaveSession(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (!sessionForm.date || !sessionForm.coacheeId) {
      setError('Date/time and coachee are required.');
      return;
    }

    try {
      if (sessionForm.id) {
        const updated = await updateSession(sessionForm.id, {
          title: sessionForm.title,
          date: sessionForm.date,
          durationMinutes: sessionForm.durationMinutes,
          coacheeId: sessionForm.coacheeId,
          notes: sessionForm.notes,
        });
        setSessions((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      } else {
        const created = await createSession({
          title: sessionForm.title,
          date: sessionForm.date,
          durationMinutes: sessionForm.durationMinutes,
          coacheeId: sessionForm.coacheeId,
          notes: sessionForm.notes,
        });
        setSessions((prev) => [...prev, created]);
      }
      setShowSessionModal(false);
      setSessionForm(EMPTY_SESSION_FORM);
      setError(null);
    } catch {
      setError('Could not save session.');
    }
  }

  async function handleDeleteSession(): Promise<void> {
    if (!sessionForm.id) return;
    try {
      await deleteSession(sessionForm.id);
      setSessions((prev) => prev.filter((item) => item.id !== sessionForm.id));
      setShowSessionModal(false);
      setSessionForm(EMPTY_SESSION_FORM);
      setError(null);
    } catch {
      setError('Could not delete session.');
    }
  }

  async function handleAddAvailability(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (!availabilityForm.weekdays.length) {
      setError('Choose at least one day of week.');
      return;
    }

    try {
      const pendingWeekdays = availabilityForm.weekdays.filter(
        (weekday) =>
          !availability.some(
            (window) =>
              window.weekday === weekday &&
              window.startTime.slice(0, 5) === availabilityForm.startTime &&
              window.endTime.slice(0, 5) === availabilityForm.endTime,
          ),
      );

      if (!pendingWeekdays.length) {
        setError('That weekly availability already exists for the selected day(s).');
        return;
      }

      const createdWindows = await Promise.all(
        pendingWeekdays.map((weekday) =>
          createAvailabilityWindow({
            weekday,
            startTime: availabilityForm.startTime,
            endTime: availabilityForm.endTime,
          }),
        ),
      );
      setAvailability((prev) => [...prev, ...createdWindows].sort((a, b) => a.weekday - b.weekday || a.startTime.localeCompare(b.startTime)));
      setError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not save weekly availability.';
      setError(message);
    }
  }

  async function handleRemoveAvailability(id: string): Promise<void> {
    try {
      await deleteAvailabilityWindow(id);
      setAvailability((prev) => prev.filter((item) => item.id !== id));
      setError(null);
    } catch {
      setError('Could not remove weekly availability.');
    }
  }

  function openCreateUnavailable(): void {
    setUnavailableEditForm(createDefaultUnavailableForm());
    setShowUnavailableModal(true);
  }

  function openEditUnavailable(period: UnavailablePeriod): void {
    setUnavailableEditForm({
      id: period.id,
      startAt: toLocalDateTimeInputValue(period.startAt),
      endAt: toLocalDateTimeInputValue(period.endAt),
      reason: period.reason,
    });
    setShowUnavailableModal(true);
  }

  async function handleSaveUnavailableEdit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (!unavailableEditForm.startAt || !unavailableEditForm.endAt) {
      setError('Unavailable period requires start and end date/time.');
      return;
    }

    try {
      if (unavailableEditForm.id) {
        const updated = await updateUnavailablePeriod(unavailableEditForm.id, {
          startAt: unavailableEditForm.startAt,
          endAt: unavailableEditForm.endAt,
          reason: unavailableEditForm.reason,
        });
        setUnavailablePeriods((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      } else {
        const created = await createUnavailablePeriod({
          startAt: unavailableEditForm.startAt,
          endAt: unavailableEditForm.endAt,
          reason: unavailableEditForm.reason,
        });
        setUnavailablePeriods((prev) => [...prev, created].sort((a, b) => a.startAt.localeCompare(b.startAt)));
      }
      setShowUnavailableModal(false);
      setUnavailableEditForm(EMPTY_UNAVAILABLE_EDIT_FORM);
      setError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not update unavailable period.';
      setError(message);
    }
  }

  async function handleDeleteUnavailableFromModal(): Promise<void> {
    if (!unavailableEditForm.id) return;
    try {
      await deleteUnavailablePeriod(unavailableEditForm.id);
      setUnavailablePeriods((prev) => prev.filter((item) => item.id !== unavailableEditForm.id));
      setShowUnavailableModal(false);
      setUnavailableEditForm(EMPTY_UNAVAILABLE_EDIT_FORM);
      setError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not remove unavailable period.';
      setError(message);
    }
  }

  async function handleRemoveUnavailable(id: string): Promise<void> {
    try {
      await deleteUnavailablePeriod(id);
      setUnavailablePeriods((prev) => prev.filter((item) => item.id !== id));
      setError(null);
    } catch {
      setError('Could not remove unavailable period.');
    }
  }

  return (
    <div className='calendar-layout'>
      <div className='calendar-main'>
        <div className='calendar-toolbar'>
          <div>
            <h2 style={{ margin: 0 }}>Calendar</h2>
            <p className='muted' style={{ margin: '6px 0 0' }}>Book coaching sessions and manage your month, week, or year view.</p>
          </div>
          <div className='calendar-toolbar-actions'>
            <div className='calendar-view-toggle'>
              <button type='button' className={viewMode === 'month' ? 'active' : ''} onClick={() => setViewMode('month')}>Month</button>
              <button type='button' className={viewMode === 'week' ? 'active' : ''} onClick={() => setViewMode('week')}>Week</button>
              <button type='button' className={viewMode === 'year' ? 'active' : ''} onClick={() => setViewMode('year')}>Year</button>
            </div>
            <button type='button' onClick={handlePreviousView}>Previous</button>
            <strong>{calendarTitle}</strong>
            <button type='button' onClick={handleNextView}>Next</button>
            <button type='button' onClick={handleToday}>Today</button>
            <button type='button' className='primary' onClick={() => openCreateSession()}>New Session</button>
          </div>
        </div>

        {viewMode === 'week' && (
          <div className='calendar-week-config'>
            <label>
              Start hour
              <select value={weekStartHour} onChange={(event) => setWeekStartHour(Number(event.target.value))}>
                {Array.from({ length: 24 }, (_, hour) => (
                  <option key={`start-${hour}`} value={hour}>{formatHourLabel(hour)}</option>
                ))}
              </select>
            </label>
            <label>
              End hour
              <select value={weekEndHour} onChange={(event) => setWeekEndHour(Number(event.target.value))}>
                {Array.from({ length: 24 }, (_, hour) => (
                  <option key={`end-${hour}`} value={hour}>{formatHourLabel(hour)}</option>
                ))}
              </select>
            </label>
          </div>
        )}

        {error && <p className='muted' style={{ color: '#9f1239' }}>{error}</p>}
        {loading ? (
          <p className='muted'>Loading calendar...</p>
        ) : (
          <>
            {viewMode === 'month' ? (
              <>
                <div className='calendar-weekdays'>
                  {WEEKDAY_LABELS.map((label) => (
                    <div key={label} className='calendar-weekday'>{label}</div>
                  ))}
                </div>

                <div className='calendar-grid'>
                  {calendarDays.map(({ date, inCurrentMonth }) => {
                    const key = date.toISOString().slice(0, 10);
                    const daySessions = sessionsByDate.get(key) ?? [];
                    const dayUnavailable = unavailableByDate.get(key) ?? [];
                    return (
                      <div key={key} className={inCurrentMonth ? 'calendar-cell' : 'calendar-cell outside-month'}>
                        <div className='calendar-cell-header'>
                          <span>{date.getDate()}</span>
                          <button type='button' className='calendar-add' onClick={() => openCreateSession(date)}>+</button>
                        </div>
                        <div className='calendar-events'>
                          {dayUnavailable.map((period) => (
                            <button
                              type='button'
                              key={`${key}-unavailable-${period.id}`}
                              className='calendar-unavailable'
                              title='Edit unavailable period'
                              onClick={() => openEditUnavailable(period)}
                            >
                              {period.reason?.trim() ? period.reason : 'Unavailable'}
                            </button>
                          ))}
                          {daySessions.map((session) => (
                            <button
                              type='button'
                              key={session.id}
                              className='calendar-event'
                              onClick={() => openEditSession(session)}
                              title={`Edit ${session.title}`}
                            >
                              <span>{new Date(session.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              <strong>{session.coacheeName || 'Coachee'}</strong>
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : viewMode === 'week' ? (
              <div className='week-scheduler'>
                <div className='week-header-row'>
                  <div className='week-time-header'>Time</div>
                  {weekDays.map((day) => {
                    const dayKey = toDateKey(day);
                    return (
                      <div key={dayKey} className='week-day-header'>
                        <span>{WEEKDAY_LABELS[(day.getDay() + 6) % 7]}</span>
                        <strong>{day.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</strong>
                        <button type='button' className='calendar-add' onClick={() => openCreateSession(day)}>+</button>
                      </div>
                    );
                  })}
                </div>

                <div className='week-body-grid'>
                  {weekHours.map((hour) => (
                    <div key={hour} className='week-row'>
                      <div className='week-time-label'>{formatHourLabel(hour)}</div>
                      {weekDays.map((day) => {
                        const dayKey = toDateKey(day);
                        const daySessions = weekSessionsByHour.get(`${dayKey}|${hour}`) ?? [];
                        const dayUnavailable = weekUnavailableByHour.get(`${dayKey}|${hour}`) ?? [];
                        return (
                          <div key={`${dayKey}-${hour}`} className='week-slot'>
                            {dayUnavailable.map((period) => (
                              <button
                                type='button'
                                key={`unavailable-${period.id}-${hour}`}
                                className='calendar-unavailable week-entry'
                                onClick={() => openEditUnavailable(period)}
                              >
                                {period.reason?.trim() ? period.reason : 'Unavailable'}
                              </button>
                            ))}
                            {daySessions.map((session) => (
                              <button
                                type='button'
                                key={`session-${session.id}-${hour}`}
                                className='calendar-event week-entry'
                                onClick={() => openEditSession(session)}
                                title={`Edit ${session.title}`}
                              >
                                <strong>{session.coacheeName || 'Coachee'}</strong>
                                <span>{new Date(session.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              </button>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className='calendar-year-grid'>
                {yearMonthSummary.map((monthData) => (
                  <button
                    key={monthData.month}
                    type='button'
                    className='calendar-year-card'
                    onClick={() => {
                      setMonthCursor(new Date(monthCursor.getFullYear(), monthData.month, 1));
                      setViewMode('month');
                    }}
                  >
                    <strong>{monthData.label}</strong>
                    <span>{monthData.sessionCount} sessions</span>
                    <span>{monthData.unavailableCount} unavailable</span>
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <aside className='calendar-sidebar'>
        <div className='card'>
          <h3 style={{ marginTop: 0 }}>Weekly Availability</h3>
          <form onSubmit={(event) => { void handleAddAvailability(event); }}>
            <label>
              Days of week
              <div className='availability-day-grid'>
                {WEEKDAY_LABELS.map((label, index) => {
                  const selected = availabilityForm.weekdays.includes(index);
                  return (
                    <button
                      key={label}
                      type='button'
                      className={selected ? 'availability-day active' : 'availability-day'}
                      onClick={() => toggleAvailabilityDay(index)}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </label>
            <label>
              Start time
              <input
                type='time'
                value={availabilityForm.startTime}
                onChange={(event) => setAvailabilityForm((prev) => ({ ...prev, startTime: event.target.value }))}
              />
            </label>
            <label>
              End time
              <input
                type='time'
                value={availabilityForm.endTime}
                onChange={(event) => setAvailabilityForm((prev) => ({ ...prev, endTime: event.target.value }))}
              />
            </label>
            <button type='submit' className='primary'>Add availability</button>
          </form>
          <ul className='list'>
            {availability.map((window) => (
              <li key={window.id}>
                {WEEKDAY_LABELS[window.weekday]} {window.startTime.slice(0, 5)}-{window.endTime.slice(0, 5)}{' '}
                <button type='button' onClick={() => { void handleRemoveAvailability(window.id); }}>Remove</button>
              </li>
            ))}
          </ul>
        </div>

        <div className='card'>
          <h3 style={{ marginTop: 0 }}>Unavailable Periods</h3>
          <button type='button' className='primary' onClick={openCreateUnavailable}>Add unavailable period</button>
          <ul className='list'>
            {unavailablePeriods.map((period) => (
              <li key={period.id}>
                {new Date(period.startAt).toLocaleString()} to {new Date(period.endAt).toLocaleString()}
                {period.reason ? ` (${period.reason})` : ''}{' '}
                <button type='button' onClick={() => openEditUnavailable(period)}>Edit</button>{' '}
                <button type='button' onClick={() => { void handleRemoveUnavailable(period.id); }}>Remove</button>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {showUnavailableModal && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button
              type='button'
              className='admin-panel-modal-close'
              aria-label='Close unavailable editor'
              onClick={() => setShowUnavailableModal(false)}
            >
              x
            </button>
            <h3>{unavailableEditForm.id ? 'Edit unavailable period' : 'Add unavailable period'}</h3>
            <form onSubmit={(event) => { void handleSaveUnavailableEdit(event); }}>
              <label>
                Start
                <input
                  type='datetime-local'
                  value={unavailableEditForm.startAt}
                  onChange={(event) => setUnavailableEditForm((prev) => ({ ...prev, startAt: event.target.value }))}
                />
              </label>
              <label>
                End
                <input
                  type='datetime-local'
                  value={unavailableEditForm.endAt}
                  onChange={(event) => setUnavailableEditForm((prev) => ({ ...prev, endAt: event.target.value }))}
                />
              </label>
              <label>
                Reason
                <input
                  value={unavailableEditForm.reason}
                  onChange={(event) => setUnavailableEditForm((prev) => ({ ...prev, reason: event.target.value }))}
                />
              </label>
              <button type='submit' className='primary'>{unavailableEditForm.id ? 'Save changes' : 'Create period'}</button>
              {unavailableEditForm.id && (
                <button type='button' onClick={() => { void handleDeleteUnavailableFromModal(); }} style={{ marginLeft: 8 }}>Delete</button>
              )}
            </form>
          </div>
        </div>
      )}

      {showSessionModal && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button
              type='button'
              className='admin-panel-modal-close'
              aria-label='Close session dialog'
              onClick={() => setShowSessionModal(false)}
            >
              x
            </button>
            <h3>{sessionForm.id ? 'Edit session' : 'New session'}</h3>
            <form onSubmit={(event) => { void handleSaveSession(event); }}>
              <label>
                Session title
                <input value={sessionForm.title} onChange={(event) => setSessionForm((prev) => ({ ...prev, title: event.target.value }))} />
              </label>
              <label>
                Date and time
                <input
                  type='datetime-local'
                  value={sessionForm.date}
                  onChange={(event) => setSessionForm((prev) => ({ ...prev, date: event.target.value }))}
                />
              </label>
              <label>
                Duration (minutes)
                <input
                  type='number'
                  min={15}
                  step={15}
                  value={sessionForm.durationMinutes}
                  onChange={(event) => setSessionForm((prev) => ({ ...prev, durationMinutes: Number(event.target.value) || 60 }))}
                />
              </label>
              <label>
                Coachee
                <select value={sessionForm.coacheeId} onChange={(event) => setSessionForm((prev) => ({ ...prev, coacheeId: event.target.value }))}>
                  <option value=''>Select coachee</option>
                  {coachees.map((coachee) => (
                    <option key={coachee.id} value={coachee.id}>{coachee.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Notes
                <textarea
                  rows={4}
                  value={sessionForm.notes}
                  onChange={(event) => setSessionForm((prev) => ({ ...prev, notes: event.target.value }))}
                />
              </label>
              <button type='submit' className='primary'>{sessionForm.id ? 'Save changes' : 'Create session'}</button>
              {sessionForm.id && (
                <button type='button' onClick={() => { void handleDeleteSession(); }} style={{ marginLeft: 8 }}>Delete</button>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
