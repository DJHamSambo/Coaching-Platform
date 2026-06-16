import { describe, expect, it } from 'vitest';
import { formatHourLabel, toDateInputValue, toDateKey, toLocalDateTimeInputValue, WEEKDAY_LABELS } from './calendarUtils';

describe('calendarUtils', () => {
  it('returns seven localized weekday labels', () => {
    expect(WEEKDAY_LABELS).toHaveLength(7);
    expect(WEEKDAY_LABELS.every((label) => label.trim().length > 0)).toBe(true);
  });

  it('formats date as local datetime input value', () => {
    const value = new Date(2026, 5, 10, 9, 30);
    expect(toDateInputValue(value)).toBe('2026-06-10T09:30');
  });

  it('returns fallback slice for invalid datetime text', () => {
    expect(toLocalDateTimeInputValue('not-a-date')).toBe('not-a-date');
  });

  it('returns normalized local input value for ISO datetime text', () => {
    expect(toLocalDateTimeInputValue('2026-06-01T12:45:00Z')).toMatch(/^2026-06-01T\d{2}:45$/);
  });

  it('builds date keys in yyyy-mm-dd format', () => {
    const value = new Date(2026, 0, 5);
    expect(toDateKey(value)).toBe('2026-01-05');
  });

  it('formats hour labels in 12-hour time', () => {
    expect(formatHourLabel(0)).toBe('12:00 AM');
    expect(formatHourLabel(12)).toBe('12:00 PM');
    expect(formatHourLabel(15)).toBe('3:00 PM');
  });
});
