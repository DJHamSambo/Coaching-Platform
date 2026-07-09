import { useRef, useState } from 'react';

export interface MentionCandidate {
  /** Text shown after the `@` in both the menu and the message. */
  label: string;
  /** Canonical value sent to the backend (username or coachee name). */
  value: string;
}

interface MentionInputProps {
  value: string;
  onChange: (value: string) => void;
  candidates: MentionCandidate[];
  rows?: number;
  placeholder?: string;
}

// Matches an in-progress "@query" at the caret: preceded by start-of-text or
// whitespace, with no spaces/@ in the query itself.
const MENTION_QUERY_RE = /(^|\s)@([^\s@]*)$/;

/** Collect the canonical values of every candidate mentioned in `text`. */
export function collectMentions(text: string, candidates: MentionCandidate[]): string[] {
  const seen: string[] = [];
  for (const candidate of candidates) {
    if (text.includes(`@${candidate.label}`) && !seen.includes(candidate.value)) {
      seen.push(candidate.value);
    }
  }
  return seen;
}

export function MentionInput({ value, onChange, candidates, rows = 2, placeholder }: MentionInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const suggestions = open
    ? candidates.filter((candidate) => candidate.label.toLowerCase().includes(query.toLowerCase()))
    : [];

  function syncQueryFromCaret(text: string, caret: number): void {
    const match = text.slice(0, caret).match(MENTION_QUERY_RE);
    if (match) {
      setQuery(match[2]);
      setActiveIndex(0);
      setOpen(true);
    } else {
      setOpen(false);
    }
  }

  function handleChange(event: React.ChangeEvent<HTMLTextAreaElement>): void {
    const text = event.target.value;
    onChange(text);
    syncQueryFromCaret(text, event.target.selectionStart ?? text.length);
  }

  function applyMention(candidate: MentionCandidate): void {
    const el = textareaRef.current;
    const caret = el?.selectionStart ?? value.length;
    const upto = value.slice(0, caret);
    const after = value.slice(caret);
    const newUpto = upto.replace(MENTION_QUERY_RE, (_full, prefix: string) => `${prefix}@${candidate.label} `);
    onChange(newUpto + after);
    setOpen(false);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(newUpto.length, newUpto.length);
    });
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (!open || suggestions.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => (index - 1 + suggestions.length) % suggestions.length);
    } else if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault();
      applyMention(suggestions[Math.min(activeIndex, suggestions.length - 1)]);
    } else if (event.key === 'Escape') {
      setOpen(false);
    }
  }

  return (
    <div style={{ position: 'relative' }}>
      <textarea
        ref={textareaRef}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onKeyUp={(event) => syncQueryFromCaret(event.currentTarget.value, event.currentTarget.selectionStart ?? 0)}
        onClick={(event) => syncQueryFromCaret(event.currentTarget.value, event.currentTarget.selectionStart ?? 0)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
      />
      {open && suggestions.length > 0 && (
        <ul
          role='listbox'
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            margin: 0,
            padding: 4,
            listStyle: 'none',
            background: '#fff',
            border: '1px solid #cbd5e1',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(15,23,42,0.18)',
            zIndex: 80,
            maxHeight: 200,
            overflowY: 'auto',
          }}
        >
          {suggestions.map((candidate, index) => (
            <li key={candidate.value}>
              <button
                type='button'
                role='option'
                aria-selected={index === activeIndex}
                // onMouseDown (not onClick) so selection happens before the textarea blur closes the menu.
                onMouseDown={(event) => {
                  event.preventDefault();
                  applyMention(candidate);
                }}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  padding: '6px 8px',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                  background: index === activeIndex ? 'rgba(11,118,110,0.12)' : 'transparent',
                }}
              >
                @{candidate.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
