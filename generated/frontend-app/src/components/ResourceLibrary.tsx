import { useMemo, useState } from 'react';
import type { ResourceItem } from '../types';

interface ResourceLibraryProps {
  resources: ResourceItem[];
  onAddResource: (resource: ResourceItem) => void;
}

export function ResourceLibrary({ resources, onAddResource }: ResourceLibraryProps) {
  const [query, setQuery] = useState('');
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<'guide' | 'worksheet' | 'link'>('guide');
  const [scope, setScope] = useState<'plan' | 'shared'>('shared');

  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();
    if (!lowered) return resources;
    return resources.filter((resource) => resource.title.toLowerCase().includes(lowered));
  }, [query, resources]);

  return (
    <div>
      <h2>Resource Library</h2>
      <p className='muted'>Manage shared and plan-specific resources exchanged between coach and coachee.</p>
      <div className='card'>
        <h3>Add resource</h3>
        <label>Title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>
          Category
          <select value={category} onChange={(event) => setCategory(event.target.value as 'guide' | 'worksheet' | 'link')}>
            <option value='guide'>Guide</option>
            <option value='worksheet'>Worksheet</option>
            <option value='link'>Link</option>
          </select>
        </label>
        <label>
          Scope
          <select value={scope} onChange={(event) => setScope(event.target.value as 'plan' | 'shared')}>
            <option value='shared'>Shared</option>
            <option value='plan'>Plan specific</option>
          </select>
        </label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = title.trim();
            if (!trimmed) return;
            onAddResource({ id: `resource-${Date.now()}`, title: trimmed, category, scope });
            setTitle('');
          }}
        >
          Add resource
        </button>
      </div>

      <div className='card'>
        <h3>Available resources</h3>
        <label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <ul className='list'>
          {filtered.map((resource) => (
            <li key={resource.id}>
              <strong>{resource.title}</strong>
              <div className='muted'>{resource.category} · {resource.scope}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
