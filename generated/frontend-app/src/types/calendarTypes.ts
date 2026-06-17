export interface CalendarSession {
  id: string;
  title: string;
  date: string;
  durationMinutes: number;
  coacheeId: string | null;
  coacheeName: string;
  notes: string;
  requestedBy: 'coach' | 'coachee';
  status: 'requested' | 'accepted' | 'proposed' | 'rejected';
  responseNote: string;
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
