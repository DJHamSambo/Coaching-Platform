import { useState } from 'react';
import type { DiscussionItem, PlanTask } from '../types';

interface DiscussionPanelProps {
  discussions: DiscussionItem[];
  tasks: PlanTask[];
  onAddDiscussion: (discussion: DiscussionItem) => void;
}

export function DiscussionPanel({ discussions, tasks, onAddDiscussion }: DiscussionPanelProps) {
  const [taskId, setTaskId] = useState(tasks[0]?.id ?? '');
  const [author, setAuthor] = useState('Coachee');
  const [message, setMessage] = useState('');

  return (
    <div>
      <h2>Task Discussions</h2>
      <p className='muted'>Discuss task progress, ask for help, and trigger @mention notifications.</p>
      <div className='card'>
        <h3>Add discussion entry</h3>
        <label>
          Task
          <select value={taskId} onChange={(event) => setTaskId(event.target.value)}>
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>{task.title}</option>
            ))}
          </select>
        </label>
        <label>
          Author
          <select value={author} onChange={(event) => setAuthor(event.target.value)}>
            <option>Coach</option>
            <option>Coachee</option>
          </select>
        </label>
        <label>Message<textarea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} /></label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = message.trim();
            if (!trimmed || !taskId) return;
            const mentions = Array.from(new Set((trimmed.match(/@\w+/g) ?? []).map((token) => token.slice(1))));
            onAddDiscussion({
              id: `discussion-${Date.now()}`,
              taskId,
              planId: '',
              author,
              message: trimmed,
              mentions,
              createdAt: new Date().toISOString().slice(0, 10),
            });
            setMessage('');
          }}
        >
          Post discussion
        </button>
      </div>

      <div className='card'>
        <h3>Thread</h3>
        <ul className='list'>
          {discussions.map((discussion) => (
            <li key={discussion.id}>
              <strong>{discussion.author}</strong> on {discussion.createdAt}
              <div>{discussion.message}</div>
              <div className='muted'>Mentions: {discussion.mentions.length ? discussion.mentions.join(', ') : 'None'}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
