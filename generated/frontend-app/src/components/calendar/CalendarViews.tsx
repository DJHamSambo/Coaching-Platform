import type { CalendarSession, UnavailablePeriod, WeeklyAvailabilityWindow } from '../../types';
import { formatHourLabel, toDateKey, WEEKDAY_LABELS } from './calendarUtils';
import { sanitizeInput } from '../adminFormUtils';

interface DayCell {
  date: Date;
  inCurrentMonth: boolean;
}

interface YearSummaryItem {
  month: number;
  label: string;
  sessionCount: number;
  unavailableCount: number;
}

interface MonthCalendarViewProps {
  calendarDays: DayCell[];
  sessionsByDate: Map<string, CalendarSession[]>;
  unavailableByDate: Map<string, UnavailablePeriod[]>;
  availabilityByDate: Map<string, WeeklyAvailabilityWindow[]>;
  onCreateSession: (day: Date) => void;
  onEditSession: (session: CalendarSession) => void;
  onEditUnavailable: (period: UnavailablePeriod) => void;
}

function toSafeTitle(value: string): string {
  return sanitizeInput(value, 255);
}

function getDurationStyle(durationMinutes: number): React.CSSProperties {
  // Scale card height so longer sessions are visually larger in the calendar.
  const minutes = Number.isFinite(durationMinutes) ? durationMinutes : 60;
  const bounded = Math.max(30, Math.min(240, minutes));
  const height = Math.round((bounded / 30) * 14 + 18);
  return { minHeight: `${height}px` };
}

function SessionEntryButton({ session, onEditSession }: { session: CalendarSession; onEditSession: (session: CalendarSession) => void }) {
  const safeTitle = toSafeTitle(session.title || 'session');
  return (
    <button
      type='button'
      key={session.id}
      className='calendar-event'
      onClick={() => onEditSession(session)}
      title={`Edit ${safeTitle}`}
      style={getDurationStyle(session.durationMinutes)}
    >
      <span>{new Date(session.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      <strong>{safeTitle}</strong>
      <span>{session.durationMinutes} min</span>
    </button>
  );
}

function UnavailableEntryButton({
  period,
  dayKey,
  onEditUnavailable,
}: {
  period: UnavailablePeriod;
  dayKey: string;
  onEditUnavailable: (period: UnavailablePeriod) => void;
}) {
  const safeReason = toSafeTitle(period.reason || 'Unavailable');
  return (
    <button
      type='button'
      key={`${dayKey}-unavailable-${period.id}`}
      className='calendar-unavailable'
      title={`Edit ${safeReason}`}
      onClick={() => onEditUnavailable(period)}
    >
      {safeReason.trim() ? safeReason : 'Unavailable'}
    </button>
  );
}

export function MonthCalendarView({
  calendarDays,
  sessionsByDate,
  unavailableByDate,
  availabilityByDate,
  onCreateSession,
  onEditSession,
  onEditUnavailable,
}: MonthCalendarViewProps) {
  return (
    <>
      <div className='calendar-weekdays'>
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className='calendar-weekday'>{label}</div>
        ))}
      </div>

      <div className='calendar-grid'>
        {calendarDays.map(({ date, inCurrentMonth }) => {
          const key = toDateKey(date);
          const daySessions = sessionsByDate.get(key) ?? [];
          const dayUnavailable = unavailableByDate.get(key) ?? [];
          const dayAvailability = availabilityByDate.get(key) ?? [];
          const dayClassName = [
            'calendar-cell',
            !inCurrentMonth ? 'outside-month' : '',
            dayAvailability.length ? 'available-day' : '',
          ].filter(Boolean).join(' ');
          return (
            <div key={key} className={dayClassName}>
              <div className='calendar-cell-header'>
                <span>{date.getDate()}</span>
                <button type='button' className='calendar-add' onClick={() => onCreateSession(date)}>+</button>
              </div>
              {dayAvailability.length > 0 && (
                <p className='calendar-availability-hint'>
                  Available {dayAvailability.map((window) => `${window.startTime.slice(0, 5)}-${window.endTime.slice(0, 5)}`).join(', ')}
                </p>
              )}
              <div className='calendar-events'>
                {dayUnavailable.map((period) => (
                  <UnavailableEntryButton
                    key={`${key}-unavailable-${period.id}`}
                    period={period}
                    dayKey={key}
                    onEditUnavailable={onEditUnavailable}
                  />
                ))}
                {daySessions.map((session) => (
                  <SessionEntryButton key={session.id} session={session} onEditSession={onEditSession} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

interface WeekCalendarViewProps {
  weekDays: Date[];
  weekHours: number[];
  weekSessionsByHour: Map<string, CalendarSession[]>;
  weekUnavailableByHour: Map<string, UnavailablePeriod[]>;
  weekAvailabilityByHour: Map<string, WeeklyAvailabilityWindow[]>;
  onCreateSession: (day: Date) => void;
  onEditSession: (session: CalendarSession) => void;
  onEditUnavailable: (period: UnavailablePeriod) => void;
}

export function WeekCalendarView({
  weekDays,
  weekHours,
  weekSessionsByHour,
  weekUnavailableByHour,
  weekAvailabilityByHour,
  onCreateSession,
  onEditSession,
  onEditUnavailable,
}: WeekCalendarViewProps) {
  return (
    <div className='week-scheduler'>
      <div className='week-header-row'>
        <div className='week-time-header'>Time</div>
        {weekDays.map((day) => {
          const dayKey = toDateKey(day);
          const hasDayAvailability = weekHours.some((hour) => (weekAvailabilityByHour.get(`${dayKey}|${hour}`)?.length ?? 0) > 0);
          return (
            <div key={dayKey} className='week-day-header'>
              <span>{WEEKDAY_LABELS[(day.getDay() + 6) % 7]}</span>
              <strong>{day.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</strong>
              {hasDayAvailability && <small className='week-availability-pill'>Available</small>}
              <button type='button' className='calendar-add' onClick={() => onCreateSession(day)}>+</button>
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
              const dayAvailability = weekAvailabilityByHour.get(`${dayKey}|${hour}`) ?? [];
              const slotClassName = [
                'week-slot',
                dayAvailability.length ? 'available-slot' : '',
                dayUnavailable.length ? 'blocked-slot' : '',
              ].filter(Boolean).join(' ');
              return (
                <div key={`${dayKey}-${hour}`} className={slotClassName}>
                  {dayUnavailable.map((period) => {
                    const safeReason = toSafeTitle(period.reason || 'Unavailable');
                    return (
                      <button
                        type='button'
                        key={`unavailable-${period.id}-${hour}`}
                        className='calendar-unavailable week-entry'
                        onClick={() => onEditUnavailable(period)}
                        title={`Edit ${safeReason}`}
                      >
                        {safeReason.trim() ? safeReason : 'Unavailable'}
                      </button>
                    );
                  })}
                  {daySessions.map((session) => (
                    <button
                      type='button'
                      key={`session-${session.id}-${hour}`}
                      className='calendar-event week-entry'
                      onClick={() => onEditSession(session)}
                      title={`Edit ${toSafeTitle(session.title || 'session')}`}
                      style={getDurationStyle(session.durationMinutes)}
                    >
                      <strong>{toSafeTitle(session.title || 'session')}</strong>
                      <span>{new Date(session.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      <span>{session.durationMinutes} min</span>
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

interface YearCalendarViewProps {
  year: number;
  yearMonthSummary: YearSummaryItem[];
  onPickMonth: (month: number) => void;
}

export function YearCalendarView({ yearMonthSummary, onPickMonth }: YearCalendarViewProps) {
  return (
    <div className='calendar-year-grid'>
      {yearMonthSummary.map((monthData) => (
        <button
          key={monthData.month}
          type='button'
          className='calendar-year-card'
          onClick={() => onPickMonth(monthData.month)}
        >
          <strong>{monthData.label}</strong>
          <span>{monthData.sessionCount} sessions</span>
          <span>{monthData.unavailableCount} unavailable</span>
        </button>
      ))}
    </div>
  );
}
