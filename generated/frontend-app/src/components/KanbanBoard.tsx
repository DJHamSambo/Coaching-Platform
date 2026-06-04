import { useMemo, useState } from 'react';
import type { PlanTask, TaskStatus } from '../types';

interface KanbanBoardProps {
  tasks: PlanTask[];
  onMoveTask: (taskId: string, status: TaskStatus) => void;
  onAddTask: (task: PlanTask) => void;
}

const STATUS_LABEL: Record<TaskStatus, string> = {
  backlog: 'Backlog',
  inProgress: 'In Progress',
  done: 'Done',
};

export function KanbanBoard({ tasks, onMoveTask, onAddTask }: KanbanBoardProps) {
  const [title, setTitle] = useState('');
  const [assignee, setAssignee] = useState('Coachee');
  const [description, setDescription] = useState('');

  const grouped = useMemo(
    () => ({
      backlog: tasks.filter((task) => task.status === 'backlog'),
      inProgress: tasks.filter((task) => task.status === 'inProgress'),
      done: tasks.filter((task) => task.status === 'done'),
    }),
    [tasks],
  );

  return (
    <div>
      <h2>Planning Board</h2>
      <p className='muted'>Manage coaching plan actions on a kanban board with clear ownership.</p>
      <div className='card'>
        <h3>Add task</h3>
        <label>Task title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>
          Assignee
          <select value={assignee} onChange={(event) => setAssignee(event.target.value)}>
            <option>Coachee</option>
            <option>Coach</option>
          </select>
        </label>
        <label>Description<textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <button
          type='button'
          className='primary'
          onClick={() => {
            const trimmed = title.trim();
            if (!trimmed) return;
            onAddTask({
              id: `task-${Date.now()}`,
              title: trimmed,
              description: description.trim() || 'No description provided.',
              status: 'backlog',
              assignee,
              dueDate: new Date().toISOString().slice(0, 10),
            });
            setTitle('');
            setDescription('');
          }}
        >
          Add task
        </button>
      </div>

      <div className='grid-3'>
        {(Object.keys(grouped) as TaskStatus[]).map((status) => (
          <div className='card' key={status}>
            <h3>{STATUS_LABEL[status]}</h3>
            <ul className='list'>
              {grouped[status].map((task) => (
                <li key={task.id}>
                  <strong>{task.title}</strong>
                  <div className='muted'>{task.assignee} · due {task.dueDate}</div>
                  <div>{task.description}</div>
                  <label>
                    Move to
                    <select value={task.status} onChange={(event) => onMoveTask(task.id, event.target.value as TaskStatus)}>
                      <option value='backlog'>Backlog</option>
                      <option value='inProgress'>In Progress</option>
                      <option value='done'>Done</option>
                    </select>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
