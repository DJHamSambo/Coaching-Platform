// API client — talks to the Django backend at http://localhost:8000
// All calls attach the stored JWT token automatically.

import type { Coachee, CoachingPlan, DiscussionItem, PlanAction, PlanStatus, PlanTask, TaskStatus } from './types';

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
    planId: '',
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

// ---------------------------------------------------------------------------
// Coachees
// ---------------------------------------------------------------------------

interface ApiCoachee {
  id: number;
  name: string;
  email: string;
  notes: string;
}

function toCoachee(c: ApiCoachee): Coachee {
  return { id: String(c.id), name: c.name, email: c.email, notes: c.notes };
}

export async function listCoachees(): Promise<Coachee[]> {
  const items = await request<ApiCoachee[]>('/api/coachees/');
  return items.map(toCoachee);
}

export async function createCoachee(payload: { name: string; email?: string; notes?: string }): Promise<Coachee> {
  const created = await request<ApiCoachee>('/api/coachees/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return toCoachee(created);
}

// ---------------------------------------------------------------------------
// Coaching plans
// ---------------------------------------------------------------------------

interface ApiPlan {
  id: number;
  title: string;
  description: string;
  goal: string;
  status: 'todo' | 'in_progress' | 'done';
  target_date: string | null;
  coachee: number | null;
  coachee_name: string | null;
  created_at: string;
}

function toPlanStatus(status: ApiPlan['status']): PlanStatus {
  if (status === 'in_progress') return 'inProgress';
  return status;
}

function toApiPlanStatus(status: PlanStatus): ApiPlan['status'] {
  if (status === 'inProgress') return 'in_progress';
  return status;
}

function toCoachingPlan(p: ApiPlan): CoachingPlan {
  return {
    id: String(p.id),
    title: p.title,
    description: p.description,
    goal: p.goal,
    status: toPlanStatus(p.status),
    targetDate: p.target_date ?? '',
    coacheeId: p.coachee ? String(p.coachee) : null,
    coacheeName: p.coachee_name ?? null,
    createdAt: p.created_at.slice(0, 10),
  };
}

export async function listPlans(): Promise<CoachingPlan[]> {
  const plans = await request<ApiPlan[]>('/api/plans/');
  return plans.map(toCoachingPlan);
}

export async function createPlan(payload: {
  title: string;
  description: string;
  goal: string;
  status: PlanStatus;
  targetDate: string;
  coacheeId: string | null;
}): Promise<CoachingPlan> {
  const created = await request<ApiPlan>('/api/plans/', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.title,
      description: payload.description,
      goal: payload.goal,
      status: toApiPlanStatus(payload.status),
      target_date: payload.targetDate || null,
      coachee: payload.coacheeId ? Number(payload.coacheeId) : null,
    }),
  });
  return toCoachingPlan(created);
}

export async function updatePlan(planId: string, patch: Partial<{ status: PlanStatus; targetDate: string }>): Promise<CoachingPlan> {
  const body: Record<string, unknown> = {};
  if (patch.status !== undefined) body.status = toApiPlanStatus(patch.status);
  if (patch.targetDate !== undefined) body.target_date = patch.targetDate || null;
  const updated = await request<ApiPlan>(`/api/plans/${planId}/`, { method: 'PATCH', body: JSON.stringify(body) });
  return toCoachingPlan(updated);
}

// ---------------------------------------------------------------------------
// Plan actions (scoped to a plan)
// ---------------------------------------------------------------------------

interface ApiAction {
  id: number;
  title: string;
  description: string;
  status: 'backlog' | 'in_progress' | 'done';
  assignee: string;
  order: number;
  due_date: string | null;
}

function toPlanAction(a: ApiAction, planId: string): PlanAction {
  return {
    id: String(a.id),
    planId,
    title: a.title,
    description: a.description,
    status: toFrontendStatus(a.status),
    assignee: a.assignee,
    order: a.order,
    dueDate: a.due_date ?? new Date().toISOString().slice(0, 10),
  };
}

export async function listActions(planId: string): Promise<PlanAction[]> {
  const actions = await request<ApiAction[]>(`/api/plans/${planId}/actions/`);
  return actions.map((a) => toPlanAction(a, planId));
}

export async function createAction(
  planId: string,
  payload: Pick<PlanAction, 'title' | 'description' | 'assignee' | 'dueDate'>,
): Promise<PlanAction> {
  const created = await request<ApiAction>(`/api/plans/${planId}/actions/`, {
    method: 'POST',
    body: JSON.stringify({
      title: payload.title,
      description: payload.description,
      status: 'backlog',
      assignee: payload.assignee,
      due_date: payload.dueDate,
    }),
  });
  return toPlanAction(created, planId);
}

export async function updateActionStatus(planId: string, actionId: string, status: TaskStatus): Promise<PlanAction> {
  const updated = await request<ApiAction>(`/api/plans/${planId}/actions/${actionId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ status: toApiStatus(status) }),
  });
  return toPlanAction(updated, planId);
}
