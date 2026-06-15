import DOMPurify from 'dompurify';
import isEmail from 'validator/lib/isEmail';
import normalizeEmail from 'validator/lib/normalizeEmail';

export function sanitizeInput(value: string, maxLength: number): string {
  const cleaned = DOMPurify.sanitize(value, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
  return cleaned
    .replace(/[\u0000-\u001F\u007F]/g, '')
    .trim()
    .slice(0, maxLength);
}

export function sanitizeInputEmail(value: string): string {
  const base = sanitizeInput(value, 254).toLowerCase();
  const normalized = normalizeEmail(base, { all_lowercase: true, gmail_remove_dots: false });
  return typeof normalized === 'string' ? normalized : base;
}

export function isValidInputEmail(value: string): boolean {
  if (!value) return true;
  return isEmail(value, { allow_utf8_local_part: true });
}
