import { useEffect, useMemo, useRef, useState } from 'react';
import { createResource, deleteResource, listAdminCoachees, listCoachDirectory, listMyCalendarCoaches, listResources } from '../api';
import type { CoachingPlan, CurrentUser, ResourceItem } from '../types';

interface ResourceLibraryProps {
  plans: CoachingPlan[];
  currentUser: CurrentUser;
  focusResourceId?: string | null;
  onFocusHandled?: () => void;
}

interface ShareOption {
  username: string;
  label: string;
}

export function ResourceLibrary({ plans, currentUser, focusResourceId, onFocusHandled }: ResourceLibraryProps) {
  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [planId, setPlanId] = useState('');
  const [shareOptions, setShareOptions] = useState<ShareOption[]>([]);
  const [selectedShare, setSelectedShare] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resourceRefs = useRef<Record<string, HTMLLIElement | null>>({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listResources()
      .then((data) => {
        if (!cancelled) {
          setResources(data);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError('Could not load resources from backend.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadShareOptions(): Promise<void> {
      try {
        if (currentUser.role === 'coachee') {
          const coaches = await listMyCalendarCoaches();
          if (!cancelled) {
            setShareOptions(coaches.map((c) => ({ username: c.username, label: `${c.username} (coach)` })));
          }
          return;
        }
        const [coachees, coaches] = await Promise.all([listAdminCoachees(), listCoachDirectory()]);
        if (cancelled) return;
        const options: ShareOption[] = [];
        coachees.forEach((c) => {
          if (c.userUsername) options.push({ username: c.userUsername, label: `${c.name} (coachee)` });
        });
        coaches.forEach((c) => {
          if (c.username !== currentUser.username) options.push({ username: c.username, label: `${c.username} (coach)` });
        });
        setShareOptions(options);
      } catch {
        // Non-fatal: sharing options simply won't be offered.
      }
    }
    void loadShareOptions();
    return () => {
      cancelled = true;
    };
  }, [currentUser.role, currentUser.username]);

  const handledFocusRef = useRef<string | null>(null);
  useEffect(() => {
    if (!focusResourceId) {
      handledFocusRef.current = null;
      return;
    }
    if (handledFocusRef.current === focusResourceId) return;
    if (!resources.some((r) => r.id === focusResourceId)) return;
    handledFocusRef.current = focusResourceId;
    setQuery('');
    setHighlightedId(focusResourceId);
    requestAnimationFrame(() => {
      resourceRefs.current[focusResourceId]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    window.setTimeout(() => setHighlightedId(null), 2500);
    onFocusHandled?.();
  }, [focusResourceId, resources, onFocusHandled]);

  function toggleShare(username: string): void {
    setSelectedShare((prev) =>
      prev.includes(username) ? prev.filter((u) => u !== username) : [...prev, username],
    );
  }

  function resetForm(): void {
    setTitle('');
    setDescription('');
    setPlanId('');
    setSelectedShare([]);
    setFile(null);
    setFormError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function closeModal(): void {
    setModalOpen(false);
    resetForm();
  }

  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();
    if (!lowered) return resources;
    return resources.filter(
      (resource) =>
        resource.title.toLowerCase().includes(lowered) ||
        (resource.planTitle ?? '').toLowerCase().includes(lowered) ||
        (resource.fileName ?? '').toLowerCase().includes(lowered),
    );
  }, [query, resources]);

  async function handleUpload(): Promise<void> {
    const trimmed = title.trim();
    if (!trimmed) {
      setFormError('Please enter a title.');
      return;
    }
    if (!file) {
      setFormError('Please choose a document to upload.');
      return;
    }
    setUploading(true);
    setFormError(null);
    try {
      const created = await createResource({
        title: trimmed,
        description: description.trim(),
        planId: planId || null,
        sharedWith: selectedShare,
        file,
      });
      setResources((prev) => [created, ...prev]);
      setModalOpen(false);
      resetForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(resource: ResourceItem): Promise<void> {
    try {
      await deleteResource(resource.id);
      setResources((prev) => prev.filter((item) => item.id !== resource.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete resource.');
    }
  }

  return (
    <div>
      <h2>Resources</h2>
      <p className='muted'>
        Upload documents and optionally link them to a coaching plan so coaches and coachees can share materials that help
        plans get completed.
      </p>

      <div style={{ marginBottom: 12 }}>
        <button type='button' className='primary' onClick={() => setModalOpen(true)}>
          Add resource
        </button>
      </div>

      {modalOpen && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card'>
            <button
              type='button'
              aria-label='Close add resource dialog'
              onClick={closeModal}
              className='admin-panel-modal-close'
            >
              x
            </button>
            <h3>Add a resource</h3>
            {formError && (
              <p className='muted' role='alert' style={{ color: '#b91c1c' }}>
                {formError}
              </p>
            )}
            <label>
              Title
              <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder='e.g. Week 1 worksheet' />
            </label>
            <label>
              Description (optional)
              <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={2} />
            </label>
            <label>
              Link to coaching plan (optional)
              <select value={planId} onChange={(event) => setPlanId(event.target.value)}>
                <option value=''>No plan — shared resource</option>
                {plans.map((plan) => (
                  <option key={plan.id} value={plan.id}>
                    {plan.title}
                    {plan.coacheeName ? ` · ${plan.coacheeName}` : ''}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ marginTop: 8 }}>
              <span>
                Share with {currentUser.role === 'coachee' ? 'your coaches' : 'your coachees or other coaches'} (optional)
              </span>
              {shareOptions.length === 0 ? (
                <p className='muted' style={{ fontSize: 13, marginTop: 4 }}>
                  No people available to share with yet.
                </p>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                    marginTop: 6,
                    maxHeight: 160,
                    overflowY: 'auto',
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    padding: 8,
                  }}
                >
                  {shareOptions.map((option) => (
                    <label
                      key={option.username}
                      style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}
                    >
                      <input
                        type='checkbox'
                        checked={selectedShare.includes(option.username)}
                        onChange={() => toggleShare(option.username)}
                        style={{ width: 'auto', marginTop: 0 }}
                      />
                      {option.label}
                    </label>
                  ))}
                </div>
              )}
            </div>
            <label>
              Document
              <input
                ref={fileInputRef}
                type='file'
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <button type='button' className='primary' onClick={() => void handleUpload()} disabled={uploading}>
              {uploading ? 'Uploading…' : 'Upload document'}
            </button>
          </div>
        </div>
      )}

      <div className='card'>
        <h3>Available resources</h3>
        <label>
          Search
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder='Search by title, plan or file' />
        </label>
        {loading && <p className='muted'>Loading resources…</p>}
        {error && (
          <p className='muted' role='alert'>
            {error}
          </p>
        )}
        {!loading && filtered.length === 0 && <p className='muted'>No resources yet. Upload a document to get started.</p>}
        <ul className='resource-list'>
          {filtered.map((resource) => (
            <li
              key={resource.id}
              ref={(el) => {
                resourceRefs.current[resource.id] = el;
              }}
              className={highlightedId === resource.id ? 'resource-highlight' : undefined}
            >
              <div className='resource-item'>
                <div className='resource-item-main'>
                  <strong>{resource.title}</strong>
                  {resource.fileName && (
                    <div className='resource-filename' title={resource.fileName}>
                      {resource.fileName}
                    </div>
                  )}
                  {resource.description && <div className='muted'>{resource.description}</div>}
                  <div className='muted' style={{ fontSize: 13 }}>
                    {resource.planTitle ? `Linked to ${resource.planTitle}` : 'Shared resource'} · Uploaded by{' '}
                    {resource.ownerUsername}
                    {resource.createdAt ? ` · ${resource.createdAt}` : ''}
                  </div>
                  {resource.sharedWith.length > 0 && (
                    <div className='muted' style={{ fontSize: 13 }}>
                      Shared with: {resource.sharedWith.join(', ')}
                    </div>
                  )}
                </div>
                <div className='resource-actions'>
                  {resource.fileUrl && (
                    <a className='resource-download' href={resource.fileUrl} target='_blank' rel='noreferrer' download>
                      Download
                    </a>
                  )}
                  {resource.ownerUsername === currentUser.username && (
                    <button type='button' onClick={() => void handleDelete(resource)}>
                      Remove
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
