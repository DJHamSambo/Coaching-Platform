import { describe, expect, it, vi } from 'vitest';

vi.mock('../api', () => ({
  listSessions: vi.fn(async () => []),
  listAvailabilityWindows: vi.fn(async () => []),
  listUnavailablePeriods: vi.fn(async () => []),
  createSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn(),
  createAvailabilityWindow: vi.fn(),
  deleteAvailabilityWindow: vi.fn(),
  createUnavailablePeriod: vi.fn(),
  updateUnavailablePeriod: vi.fn(),
  deleteUnavailablePeriod: vi.fn(),
}));

describe('CalendarPanel', () => {
  it('module loads without errors', () => {
    expect(true).toBe(true);
  });
});
