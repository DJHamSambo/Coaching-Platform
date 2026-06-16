export const WEEKDAY_LABELS = Array.from({ length: 7 }, (_, dayOffset) => {
  const mondayFirstDate = new Date(Date.UTC(2024, 0, dayOffset + 1));
  return new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(mondayFirstDate);
});

const ISO_DATE_TIME_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,3})?)?(Z|[+-]\d{2}:\d{2})?$/;

export function toDateInputValue(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  const hours = String(value.getHours()).padStart(2, '0');
  const minutes = String(value.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function toLocalDateTimeInputValue(dateText: string): string {
  if (!ISO_DATE_TIME_PATTERN.test(dateText)) {
    return dateText.slice(0, 16);
  }

  const parsed = new Date(dateText);
  if (Number.isNaN(parsed.getTime())) {
    return dateText.slice(0, 16);
  }
  return toDateInputValue(parsed);
}

export function toDateKey(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

export function formatHourLabel(hour: number): string {
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const normalized = hour % 12 === 0 ? 12 : hour % 12;
  return `${normalized}:00 ${suffix}`;
}
