// API client — talks to the Django backend at http://localhost:8000
// All calls attach the stored JWT token automatically.

import type { DiscussionItem, PlanTask, TaskStatus } from './types';

const BASE_URL = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'coaching_jwt';

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface RegisterPayload {
  username: string;
  password: string;
  email?: string;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function register(payload: RegisterPayload): Promise<{ id: number; username: string; email: string }> {
  return request('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function login(payload: LoginPayload): Promise<AuthTokens> {
  return request('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status} ${text}`);
  }
  if (response.status === 204) return undefined as unknown as T;
  return response.json() as Promise<T>;
}

interface ApiTask {
  id: number;
  title: string;
  description: string;
  status: 'backlog' | 'in_progress' | 'done';
  assignee: string;
  due_date: string | null;
}

function toFrontendStatus(status: ApiTask['status']): TaskStatus {
  if (status === 'in_progress') return 'inProgress';
  return status;
}

function toApiStatus(status: TaskStatus): ApiTask['status'] {
  if (status === 'inProgress') return 'in_progress';
  return status;
}

function toPlanTask(task: ApiTask): PlanTask {
  return {
    id: String(task.id),
    title: task.title,
    description: task.description,
    status: toFrontendStatus(task.status),
    assignee: task.assignee,
    dueDate: task.due_date ?? new Date().toISOString().slice(0, 10),
  };
}

export async function listTasks(): Promise<PlanTask[]> {
  const tasks = await request<ApiTask[]>('/api/tasks/');
  return tasks.map(toPlanTask);
}

export async function createTask(task: Pick<PlanTask, 'title' | 'description' | 'assignee' | 'dueDate'>): Promise<PlanTask> {
  const payload = {
    title: task.title,
    description: task.description,
    status: 'backlog',
    assignee: task.assignee,
    due_date: task.dueDate,
  };
  const created = await request<ApiTask>('/api/tasks/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return toPlanTask(created);
}

export async function updateTaskStatus(taskId: string, status: TaskStatus): Promise<PlanTask> {
  const updated = await request<ApiTask>(`/api/tasks/${taskId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ status: toApiStatus(status) }),
  });
  return toPlanTask(updated);
}

interface ApiMessage {
  id: number;
  title: string;
  task_id: number | null;
  author: string;
  created_at: string;
}

function toDiscussionItem(message: ApiMessage): DiscussionItem {
  const text = message.title ?? '';
  const mentions = Array.from(new Set((text.match(/@\w+/g) ?? []).map((token) => token.slice(1))));
  return {
    id: String(message.id),
    taskId: message.task_id ? String(message.task_id) : '',
    author: message.author,
    message: text,
    mentions,
    createdAt: message.created_at.slice(0, 10),
  };
}

export async function listDiscussions(): Promise<DiscussionItem[]> {
  const messages = await request<ApiMessage[]>('/api/messages/');
  return messages.map(toDiscussionItem);
}

export async function createDiscussion(payload: { taskId: string; author: string; message: string }): Promise<DiscussionItem> {
  const created = await request<ApiMessage>('/api/messages/', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.message,
      task_id: payload.taskId ? Number(payload.taskId) : null,
      author: payload.author,
    }),
  });
  return toDiscussionItem(created);
}
