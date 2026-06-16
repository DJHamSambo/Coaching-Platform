import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { CalendarSession, UnavailablePeriod } from '../../types';
import { MonthCalendarView, WeekCalendarView, YearCalendarView } from './CalendarViews';

const baseSession: CalendarSession = {
  id: 's1',
  title: '<img src=x onerror=alert(1)>',
  date: '2026-06-10T10:00:00Z',
  durationMinutes: 60,
  coacheeId: '1',
  coacheeName: 'Jordan',
  notes: '',
};

const baseUnavailable: UnavailablePeriod = {
  id: 'u1',
  startAt: '2026-06-10T09:00:00Z',
  endAt: '2026-06-10T11:00:00Z',
  reason: '<script>alert(1)</script> Busy',
};

describe('CalendarViews', () => {
  it('renders month view', () => {
    const day = new Date(2026, 5, 10);
    const key = '2026-06-10';

    const { container } = render(
      <MonthCalendarView
        calendarDays={[{ date: day, inCurrentMonth: true }]}
        sessionsByDate={new Map([[key, [baseSession]]])}
        unavailableByDate={new Map([[key, [baseUnavailable]]])}
        onCreateSession={vi.fn()}
        onEditSession={vi.fn()}
        onEditUnavailable={vi.fn()}
      />,
    );

    expect(container.querySelector('.calendar-grid')).toBeInTheDocument();
    expect(container.querySelectorAll('.calendar-cell')).toHaveLength(1);
  });

  it('sanitizes title attributes in week view', () => {
    const day = new Date(2026, 5, 10);
    const dayKey = '2026-06-10';

    const { container } = render(
      <WeekCalendarView
        weekDays={[day]}
        weekHours={[10]}
        weekSessionsByHour={new Map([[`${dayKey}|10`, [baseSession]]])}
        weekUnavailableByHour={new Map([[`${dayKey}|10`, [baseUnavailable]]])}
        onCreateSession={vi.fn()}
        onEditSession={vi.fn()}
        onEditUnavailable={vi.fn()}
      />,
    );

    const buttons = container.querySelectorAll('button[title]');
    buttons.forEach((btn) => {
      const title = btn.getAttribute('title') || '';
      expect(title).not.toContain('<img');
      expect(title).not.toContain('<script>');
      expect(title).not.toContain('onerror');
    });
  });

  it('renders year summary cards and picks month', async () => {
    const user = userEvent.setup();
    const onPickMonth = vi.fn();

    render(
      <YearCalendarView
        year={2026}
        yearMonthSummary={[
          { month: 0, label: 'Jan', sessionCount: 2, unavailableCount: 1 },
          { month: 1, label: 'Feb', sessionCount: 0, unavailableCount: 0 },
        ]}
        onPickMonth={onPickMonth}
      />,
    );

    await user.click(screen.getByRole('button', { name: /Jan/i }));
    expect(onPickMonth).toHaveBeenCalledWith(0);
  });
});
