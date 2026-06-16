import type { CalendarSession, UnavailablePeriod } from '../../types';
import { formatHourLabel, toDateKey, WEEKDAY_LABELS } from './calendarUtils';

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
  onCreateSession: (day: Date) => void;
  onEditSession: (session: CalendarSession) => void;
  onEditUnavailable: (period: UnavailablePeriod) => void;
}

export function MonthCalendarView({
  calendarDays,
  sessionsByDate,
  unavailableByDate,
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
          const key = date.toISOString().slice(0, 10);
          const daySessions = sessionsByDate.get(key) ?? [];
          const dayUnavailable = unavailableByDate.get(key) ?? [];
          return (
            <div key={key} className={inCurrentMonth ? 'calendar-cell' : 'calendar-cell outside-month'}>
              <div className='calendar-cell-header'>
                <span>{date.getDate()}</span>
                <button type='button' className='calendar-add' onClick={() => onCreateSession(date)}>+</button>
              </div>
              <div className='calendar-events'>
                {dayUnavailable.map((period) => (
                  <button
                    type='button'
                    key={`${key}-unavailable-${period.id}`}
                    className='calendar-unavailable'
                    title='Edit unavailable period'
                    onClick={() => onEditUnavailable(period)}
                  >
                    {period.reason?.trim() ? period.reason : 'Unavailable'}
                  </button>
                ))}
                {daySessions.map((session) => (
                  <button
                    type='button'
                    key={session.id}
                    className='calendar-event'
                    onClick={() => onEditSession(session)}
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
  );
}

interface WeekCalendarViewProps {
  weekDays: Date[];
  weekHours: number[];
  weekSessionsByHour: Map<string, CalendarSession[]>;
  weekUnavailableByHour: Map<string, UnavailablePeriod[]>;
  onCreateSession: (day: Date) => void;
  onEditSession: (session: CalendarSession) => void;
  onEditUnavailable: (period: UnavailablePeriod) => void;
}

export function WeekCalendarView({
  weekDays,
  weekHours,
  weekSessionsByHour,
  weekUnavailableByHour,
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
          return (
            <div key={dayKey} className='week-day-header'>
              <span>{WEEKDAY_LABELS[(day.getDay() + 6) % 7]}</span>
              <strong>{day.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</strong>
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
              return (
                <div key={`${dayKey}-${hour}`} className='week-slot'>
                  {dayUnavailable.map((period) => (
                    <button
                      type='button'
                      key={`unavailable-${period.id}-${hour}`}
                      className='calendar-unavailable week-entry'
                      onClick={() => onEditUnavailable(period)}
                    >
                      {period.reason?.trim() ? period.reason : 'Unavailable'}
                    </button>
                  ))}
                  {daySessions.map((session) => (
                    <button
                      type='button'
                      key={`session-${session.id}-${hour}`}
                      className='calendar-event week-entry'
                      onClick={() => onEditSession(session)}
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
