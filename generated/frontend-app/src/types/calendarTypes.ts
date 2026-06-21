export interface CalendarSession {
  id: string;
  title: string;
  date: string;
  durationMinutes: number;
  coacheeId: string | null;
  coacheeName: string;
  coachingPlanId: string | null;
  coachingPlanTitle: string | null;
  notes: string;
  requestedBy: 'coach' | 'coachee';
}

export interface WeeklyAvailabilityWindow {
  id: string;
  weekday: number;
  startTime: string;
  endTime: string;
}

export interface UnavailablePeriod {
  id: string;
  startAt: string;
  endAt: string;
  reason: string;
}
