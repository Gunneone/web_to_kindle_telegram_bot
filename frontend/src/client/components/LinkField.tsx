import { IconAlertCircle } from '@tabler/icons-react';
import type { Ref } from 'react';
import { useI18n } from '../i18n';
import { extractLinks, looksLikeLink } from '../lib/links';
import { PasteButton } from './PasteButton';

/** The links in a field, or `INVALID_URL` when one of them can't be a web address. */
export function checkLinks(text: string): { links: string[]; error: string | null } {
  const links = extractLinks(text);
  return { links, error: links.every(looksLikeLink) ? null : 'INVALID_URL' };
}

/**
 * The field a link is pasted into, with the paste button and, under it, either a hint or what's wrong
 * with the link: the problem shows where it is, and the field is marked until it changes.
 */
export function LinkField({
  id,
  label,
  placeholder,
  value,
  onChange,
  hint,
  error,
  inputRef,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  /** An error code (`INVALID_URL`), or nothing */
  error: string | null;
  inputRef?: Ref<HTMLInputElement>;
}) {
  const { error: say } = useI18n();
  const noteId = `${id}-note`;
  const note = error ? say(error) : hint;
  return (
    <div>
      <label className="g1-label" htmlFor={id}>
        {label}
      </label>
      <div className="flex gap-2">
        <input
          id={id}
          ref={inputRef}
          className="g1-input min-w-0 flex-1"
          type="text"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={error ? true : undefined}
          aria-describedby={note ? noteId : undefined}
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required
        />
        <PasteButton onPaste={onChange} />
      </div>
      {note && (
        <span id={noteId} className={`mt-1 flex items-start gap-1 text-sm ${error ? 'text-danger' : 'text-muted'}`} role={error ? 'alert' : undefined}>
          {error && <IconAlertCircle className="g1-icon mt-0.5 shrink-0" aria-hidden />}
          {note}
        </span>
      )}
    </div>
  );
}
