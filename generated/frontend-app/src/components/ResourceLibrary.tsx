import { useEffect, useMemo, useRef, useState } from 'react';
import { createResource, deleteResource, listResources } from '../api';
import type { CoachingPlan, CurrentUser, ResourceItem } from '../types';

interface ResourceLibraryProps {
  plans: CoachingPlan[];
  currentUser: CurrentUser;
}

export function ResourceLibrary({ plans, currentUser }: ResourceLibraryProps) {
  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [planId, setPlanId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        file,
      });
      setResources((prev) => [created, ...prev]);
      setTitle('');
      setDescription('');
      setPlanId('');
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
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

      <div className='card'>
        <h3>Upload a document</h3>
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
        <ul className='list'>
          {filtered.map((resource) => (
            <li key={resource.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ minWidth: 0 }}>
                  <strong>{resource.title}</strong>
                  {resource.description && <div className='muted'>{resource.description}</div>}
                  <div className='muted' style={{ fontSize: 13 }}>
                    {resource.planTitle ? `Linked to ${resource.planTitle}` : 'Shared resource'} · Uploaded by{' '}
                    {resource.ownerUsername}
                    {resource.createdAt ? ` · ${resource.createdAt}` : ''}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  {resource.fileUrl && (
                    <a href={resource.fileUrl} target='_blank' rel='noreferrer' download>
                      {resource.fileName ?? 'Download'}
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
