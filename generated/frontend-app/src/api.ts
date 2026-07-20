// API client — talks to the Django backend at http://localhost:8000
// All calls attach the stored JWT token automatically.

import type {
  AdminCoachee,
  AdminCoach,
  CalendarSession,
  Coachee,
  CoachingPlan,
  CurrentUser,
  DiscussionItem,
  InsightItem,
  NotificationItem,
  PlanAction,
  PlanStatus,
  PlanTask,
  QuestionnaireAnswer,
  QuestionnaireItem,
  ContractData,
  ContractItem,
  ResourceItem,
  TaskStatus,
  UnavailablePeriod,
  WeeklyAvailabilityWindow,
} from './types';
import { NOTIFICATION_TARGET_TYPES } from './types';
import { GENERIC_API_ERROR_MESSAGE, SESSION_EXPIRED_MESSAGE } from './constants/messages';

const BASE_URL = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'coaching_jwt';
const USERNAME_KEY = 'coaching_username';

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

export function setAuthTokens(tokens: AuthTokens): void {
  localStorage.setItem(TOKEN_KEY, tokens.access);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const normalized = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
    const decoded = atob(padded);
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function setCurrentUsername(username: string): void {
  localStorage.setItem(USERNAME_KEY, username);
}

export function getCurrentUsername(): string {
  const stored = localStorage.getItem(USERNAME_KEY);
  if (stored?.trim()) return stored;

  const token = getToken();
  if (!token) return 'Coach';

  const payload = decodeJwtPayload(token);
  const candidate = payload?.username ?? payload?.preferred_username ?? payload?.name ?? payload?.sub;
  return typeof candidate === 'string' && candidate.trim() ? candidate : 'Coach';
}

export async function register(payload: RegisterPayload): Promise<{ id: number; username: string; email: string }> {
  return request('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, { skipAuth: true });
}

export async function login(payload: LoginPayload): Promise<AuthTokens> {
  return request('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, { skipAuth: true });
}

interface ApiMe {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  role: 'admin' | 'coach' | 'coachee';
  must_reset_password?: boolean;
  avatar_url?: string | null;
  phone?: string;
}

interface ApiListResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

function toListResults<T>(payload: T[] | ApiListResponse<T>): T[] {
  return Array.isArray(payload) ? payload : payload.results;
}

export async function getMe(): Promise<CurrentUser> {
  const me = await request<ApiMe>('/api/auth/me/');
  return {
    id: String(me.id),
    username: me.username,
    email: me.email,
    role: me.role,
    isAdmin: me.is_admin,
    mustResetPassword: Boolean(me.must_reset_password),
    avatarUrl: me.avatar_url ?? null,
    phone: me.phone ?? '',
  };
}

export async function updateProfile(payload: {
  username?: string;
  avatarFile?: File | null;
  phone?: string;
  email?: string;
}): Promise<CurrentUser> {
  const form = new FormData();
  if (typeof payload.username === 'string') {
    form.append('username', payload.username);
  }
  if (payload.avatarFile) {
    form.append('avatar', payload.avatarFile);
  }
  if (typeof payload.phone === 'string') {
    form.append('phone', payload.phone);
  }
  if (typeof payload.email === 'string') {
    form.append('email', payload.email);
  }
  const me = await request<ApiMe>('/api/auth/profile/', {
    method: 'PATCH',
    body: form,
  });
  return {
    id: String(me.id),
    username: me.username,
    email: me.email,
    role: me.role,
    isAdmin: me.is_admin,
    mustResetPassword: Boolean(me.must_reset_password),
    avatarUrl: me.avatar_url ?? null,
    phone: me.phone ?? '',
  };
}

interface ApiQuestionnaire {
  id: number;
  name: string;
  answers: QuestionnaireAnswer[];
  submitted_at: string;
}

function toQuestionnaire(item: ApiQuestionnaire): QuestionnaireItem {
  return {
    id: String(item.id),
    name: item.name,
    answers: Array.isArray(item.answers) ? item.answers : [],
    submittedAt: item.submitted_at,
  };
}

export async function listQuestionnaires(): Promise<QuestionnaireItem[]> {
  const payload = await request<ApiQuestionnaire[] | ApiListResponse<ApiQuestionnaire>>(
    '/api/questionnaires/',
  );
  return toListResults(payload).map(toQuestionnaire);
}

export async function createQuestionnaire(payload: {
  name: string;
  answers: QuestionnaireAnswer[];
}): Promise<QuestionnaireItem> {
  const created = await request<ApiQuestionnaire>('/api/questionnaires/', {
    method: 'POST',
    body: JSON.stringify({ name: payload.name, answers: payload.answers }),
  });
  return toQuestionnaire(created);
}

interface ApiContract {
  id: number;
  title: string;
  data: ContractData;
  status: 'awaiting_coachee' | 'executed';
  coachee_accepted_terms: boolean;
  coach_username: string | null;
  coachee: number | null;
  coachee_name: string | null;
  coachee_username: string | null;
  created_at: string;
  updated_at: string;
}

function toContract(item: ApiContract): ContractItem {
  return {
    id: String(item.id),
    title: item.title,
    data: item.data,
    status: item.status,
    coacheeAcceptedTerms: Boolean(item.coachee_accepted_terms),
    coachUsername: item.coach_username ?? null,
    coacheeId: item.coachee != null ? String(item.coachee) : null,
    coacheeName: item.coachee_name ?? null,
    coacheeUsername: item.coachee_username ?? null,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export async function listContracts(): Promise<ContractItem[]> {
  const payload = await request<ApiContract[] | ApiListResponse<ApiContract>>(
    '/api/contracts/',
  );
  return toListResults(payload).map(toContract);
}

export async function createContract(payload: {
  title: string;
  data: ContractData;
  coacheeId: string;
}): Promise<ContractItem> {
  const created = await request<ApiContract>('/api/contracts/', {
    method: 'POST',
    body: JSON.stringify({ title: payload.title, data: payload.data, coachee: Number(payload.coacheeId) }),
  });
  return toContract(created);
}

export async function updateContract(
  id: string,
  payload: { data: ContractData; coacheeAcceptedTerms?: boolean },
): Promise<ContractItem> {
  const body: Record<string, unknown> = { data: payload.data };
  if (payload.coacheeAcceptedTerms !== undefined) {
    body.coachee_accepted_terms = payload.coacheeAcceptedTerms;
  }
  const updated = await request<ApiContract>(`/api/contracts/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return toContract(updated);
}

export async function deleteContract(id: string): Promise<void> {
  await request<void>(`/api/contracts/${id}/`, { method: 'DELETE' });
}

export async function changePassword(payload: {
  currentPassword: string;
  newPassword: string;
}): Promise<void> {
  await request<void>('/api/auth/change-password/', {
    method: 'POST',
    body: JSON.stringify({
      current_password: payload.currentPassword,
      new_password: payload.newPassword,
    }),
  });
}

export async function validateActivationToken(
  token: string,
): Promise<{ valid: boolean; username: string; email: string }> {
  return request(
    '/api/auth/activate/validate/',
    { method: 'POST', body: JSON.stringify({ token }) },
    { skipAuth: true },
  );
}

export async function activateAccount(payload: {
  token: string;
  newPassword: string;
}): Promise<{ detail: string; username: string }> {
  return request(
    '/api/auth/activate/',
    {
      method: 'POST',
      body: JSON.stringify({ token: payload.token, new_password: payload.newPassword }),
    },
    { skipAuth: true },
  );
}

function getTokenExpEpochSeconds(token: string): number | null {
  const payload = decodeJwtPayload(token);
  const expValue = payload?.exp;
  return typeof expValue === 'number' ? expValue : null;
}

function isTokenExpiredOrNearExpiry(token: string, skewSeconds = 30): boolean {
  const exp = getTokenExpEpochSeconds(token);
  if (!exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return exp <= now + skewSeconds;
}

function notifyAuthExpired(): never {
  clearToken();
  window.dispatchEvent(new Event('auth:expired'));
  throw new Error(SESSION_EXPIRED_MESSAGE);
}

async function ensureValidAccessToken(): Promise<string | null> {
  const token = getToken();
  if (!token) return null;
  if (!isTokenExpiredOrNearExpiry(token)) return token;

  notifyAuthExpired();
}

async function parseClientSafeError(response: Response): Promise<string> {

  let parsedMessage = '';
  try {
    const data = (await response.clone().json()) as unknown;
    if (data && typeof data === 'object') {
      const record = data as Record<string, unknown>;
      const candidate = record.detail ?? record.message ?? record.error;
      if (typeof candidate === 'string') {
        parsedMessage = candidate;
      } else {
        // DRF field validation errors arrive as { field: ["message", ...] }
        // or { field: "message" }. Surface the first concrete message.
        for (const value of Object.values(record)) {
          if (typeof value === 'string' && value) {
            parsedMessage = value;
            break;
          }
          if (Array.isArray(value)) {
            const first = value.find((item) => typeof item === 'string' && item);
            if (typeof first === 'string') {
              parsedMessage = first;
              break;
            }
          }
        }
      }
    } else if (typeof data === 'string') {
      parsedMessage = data;
    }
  } catch {
    parsedMessage = '';
  }

  if (!parsedMessage) {
    if (response.status >= 500) return 'Server error. Please try again later.';
    if (response.status === 400) return 'Invalid request. Please review your input.';
    if (response.status === 401) return 'Authentication failed. Please check your credentials.';
    if (response.status === 403) return 'You do not have permission to perform this action.';
    if (response.status === 404) return 'Requested resource was not found.';
    return GENERIC_API_ERROR_MESSAGE;
  }

  return `${response.status} ${parsedMessage}`;
}

interface RequestBehavior {
  skipAuth?: boolean;
}

async function request<T>(path: string, options: RequestInit = {}, behavior: RequestBehavior = {}): Promise<T> {
  const token = behavior.skipAuth ? null : await ensureValidAccessToken();
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers: Record<string, string> = {
    // Let the browser set the multipart boundary for FormData uploads.
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401 && token) {
      notifyAuthExpired();
    }
    const safeMessage = await parseClientSafeError(response);
    throw new Error(safeMessage);
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
  plan: number | null;
  task_id: number | null;
  author: string;
  mentions: string;
  created_at: string;
}

function toDiscussionItem(message: ApiMessage): DiscussionItem {
  const text = message.title ?? '';
  const mentionsFromField = (message.mentions ?? '')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean);
  const mentionsFromText = Array.from(new Set((text.match(/@\w+/g) ?? []).map((token) => token.slice(1))));
  const mentions = mentionsFromField.length ? mentionsFromField : mentionsFromText;
  return {
    id: String(message.id),
    taskId: message.task_id ? String(message.task_id) : '',
    planId: message.plan ? String(message.plan) : '',
    author: message.author,
    message: text,
    mentions,
    createdAt: message.created_at.slice(0, 10),
  };
}

export async function listDiscussions(filters?: { planId?: string; taskId?: string }): Promise<DiscussionItem[]> {
  const params = new URLSearchParams();
  if (filters?.planId) params.set('plan_id', filters.planId);
  if (filters?.taskId) params.set('task_id', filters.taskId);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const messages = await request<ApiMessage[]>(`/api/messages/${suffix}`);
  return messages.map(toDiscussionItem);
}

export async function createDiscussion(payload: { planId: string; taskId?: string; author: string; message: string; mentions?: string[] }): Promise<DiscussionItem> {
  const mentions = payload.mentions && payload.mentions.length
    ? payload.mentions
    : Array.from(new Set((payload.message.match(/@\w+/g) ?? []).map((token) => token.slice(1))));
  const created = await request<ApiMessage>('/api/messages/', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.message,
      plan: Number(payload.planId),
      task_id: payload.taskId ? Number(payload.taskId) : null,
      author: payload.author,
      mentions: mentions.join(','),
    }),
  });
  return toDiscussionItem(created);
}

interface ApiInsight {
  id: number;
  title: string;
  author: string;
  created_at: string;
  updated_at: string;
  coachee: number | null;
  coachee_name: string | null;
}

function toInsightItem(insight: ApiInsight): InsightItem {
  return {
    id: String(insight.id),
    author: insight.author,
    note: insight.title,
    createdAt: insight.created_at,
    updatedAt: insight.updated_at,
    coacheeId: insight.coachee ? String(insight.coachee) : null,
    coacheeName: insight.coachee_name,
  };
}

export async function listInsights(coacheeId?: string | null): Promise<InsightItem[]> {
  let url = '/api/insights/';
  if (coacheeId) {
    url += `?coachee_id=${coacheeId}`;
  }
  const insights = await request<ApiInsight[] | ApiListResponse<ApiInsight>>(url);
  return toListResults(insights)
    .map(toInsightItem)
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export async function createInsight(payload: { author: string; note: string; coacheeId?: string | null }): Promise<InsightItem> {
  const created = await request<ApiInsight>('/api/insights/', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.note,
      author: payload.author,
      coachee: payload.coacheeId ? Number(payload.coacheeId) : null,
    }),
  });
  return toInsightItem(created);
}

export async function updateInsight(insightId: string, payload: { author?: string; note?: string; coacheeId?: string | null }): Promise<InsightItem> {
  const body: Record<string, unknown> = {};
  if (payload.author !== undefined) body.author = payload.author;
  if (payload.note !== undefined) body.title = payload.note;
  if (payload.coacheeId !== undefined) body.coachee = payload.coacheeId ? Number(payload.coacheeId) : null;
  const updated = await request<ApiInsight>(`/api/insights/${insightId}/`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return toInsightItem(updated);
}

export async function deleteInsight(insightId: string): Promise<void> {
  await request<void>(`/api/insights/${insightId}/`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Activity notifications
// ---------------------------------------------------------------------------

interface ApiNotification {
  id: number;
  actor_name: string;
  notification_type: NotificationItem['type'];
  message: string;
  target_type: string;
  target_id: number | null;
  plan_id: number | null;
  action_id: number | null;
  is_read: boolean;
  created_at: string;
}

function toNotificationItem(n: ApiNotification): NotificationItem {
  const targetType = ((NOTIFICATION_TARGET_TYPES as readonly string[]).includes(n.target_type)
    ? n.target_type
    : '') as NotificationItem['targetType'];
  return {
    id: String(n.id),
    actorName: n.actor_name,
    type: n.notification_type,
    message: n.message,
    targetType,
    targetId: n.target_id != null ? String(n.target_id) : null,
    planId: n.plan_id != null ? String(n.plan_id) : null,
    actionId: n.action_id != null ? String(n.action_id) : null,
    isRead: Boolean(n.is_read),
    createdAt: n.created_at,
  };
}

export async function listNotifications(): Promise<NotificationItem[]> {
  const items = await request<ApiNotification[] | ApiListResponse<ApiNotification>>('/api/notifications/');
  return toListResults(items).map(toNotificationItem);
}

export async function markNotificationRead(notificationId: string): Promise<NotificationItem> {
  const updated = await request<ApiNotification>(`/api/notifications/${notificationId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ is_read: true }),
  });
  return toNotificationItem(updated);
}

export async function markAllNotificationsRead(): Promise<void> {
  await request<{ updated: number }>('/api/notifications/mark-all-read/', { method: 'POST' });
}

// ---------------------------------------------------------------------------
// Coachees
// ---------------------------------------------------------------------------

interface ApiCoachee {
  id: number;
  name: string;
  email: string;
  notes: string;
  user?: number | null;
  user_username?: string;
  user_email?: string;
  user_phone?: string;
  added_by?: number;
  added_by_username?: string;
}

function toCoachee(c: ApiCoachee): Coachee {
  return { id: String(c.id), name: c.name, email: c.email, notes: c.notes };
}

function toAdminCoachee(c: ApiCoachee): AdminCoachee {
  return {
    id: String(c.id),
    name: c.name,
    email: c.email,
    notes: c.notes,
    user: c.user ? String(c.user) : null,
    userUsername: c.user_username ?? '',
    userEmail: c.user_email ?? '',
    userPhone: c.user_phone ?? '',
    addedById: c.added_by ? String(c.added_by) : '',
    addedByUsername: c.added_by_username ?? '',
  };
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
// Administration
// ---------------------------------------------------------------------------

interface ApiCoach {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  is_active: boolean;
}

function toAdminCoach(coach: ApiCoach): AdminCoach {
  return {
    id: String(coach.id),
    username: coach.username,
    email: coach.email,
    isAdmin: coach.is_staff,
    isActive: coach.is_active,
  };
}

export async function listAdminCoaches(): Promise<AdminCoach[]> {
  const items = await request<ApiCoach[]>('/api/admin/coaches/');
  return items.map(toAdminCoach);
}

export async function listCoachDirectory(): Promise<AdminCoach[]> {
  const items = await request<ApiCoach[]>('/api/admin/coach-directory/');
  return items.map(toAdminCoach);
}

export async function listMyCalendarCoaches(): Promise<AdminCoach[]> {
  const items = await request<ApiCoach[]>('/api/calendar/my-coaches/');
  return items.map(toAdminCoach);
}

export async function createAdminCoach(payload: {
  username: string;
  email?: string;
  password?: string;
  isAdmin: boolean;
  isActive: boolean;
}): Promise<AdminCoach> {
  const created = await request<ApiCoach>('/api/admin/coaches/', {
    method: 'POST',
    body: JSON.stringify({
      username: payload.username,
      email: payload.email ?? '',
      password: payload.password ?? '',
      is_staff: payload.isAdmin,
      is_active: payload.isActive,
    }),
  });
  return toAdminCoach(created);
}

export async function updateAdminCoach(
  coachId: string,
  patch: Partial<{ username: string; email: string; password: string; isAdmin: boolean; isActive: boolean }>,
): Promise<AdminCoach> {
  const body: Record<string, unknown> = {};
  if (patch.username !== undefined) body.username = patch.username;
  if (patch.email !== undefined) body.email = patch.email;
  if (patch.password !== undefined) body.password = patch.password;
  if (patch.isAdmin !== undefined) body.is_staff = patch.isAdmin;
  if (patch.isActive !== undefined) body.is_active = patch.isActive;
  const updated = await request<ApiCoach>(`/api/admin/coaches/${coachId}/`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return toAdminCoach(updated);
}

export async function deleteAdminCoach(coachId: string): Promise<void> {
  await request<void>(`/api/admin/coaches/${coachId}/`, { method: 'DELETE' });
}

export async function listAdminCoachees(): Promise<AdminCoachee[]> {
  const items = await request<ApiCoachee[]>('/api/admin/coachees/');
  return items.map(toAdminCoachee);
}

export async function createAdminCoachee(payload: { name: string; email?: string; notes?: string }): Promise<AdminCoachee> {
  const created = await request<ApiCoachee>('/api/admin/coachees/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return toAdminCoachee(created);
}

export async function updateAdminCoachee(
  coacheeId: string,
  patch: Partial<{ name: string; email: string; notes: string }>,
): Promise<AdminCoachee> {
  const updated = await request<ApiCoachee>(`/api/admin/coachees/${coacheeId}/`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
  return toAdminCoachee(updated);
}

export async function deleteAdminCoachee(coacheeId: string): Promise<void> {
  await request<void>(`/api/admin/coachees/${coacheeId}/`, { method: 'DELETE' });
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
  coach_username: string | null;
  created_at: string;
  documents?: ApiResource[];
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
    coachUsername: p.coach_username ?? null,
    createdAt: p.created_at.slice(0, 10),
    documents: p.documents ? p.documents.map(toResourceItem) : undefined,
  };
}

export async function listPlans(): Promise<CoachingPlan[]> {
  const plans = await request<ApiPlan[]>('/api/plans/');
  return plans.map(toCoachingPlan);
}

export async function getPlan(planId: string): Promise<CoachingPlan> {
  const plan = await request<ApiPlan>(`/api/plans/${planId}/`);
  return toCoachingPlan(plan);
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

export async function updatePlan(
  planId: string,
  patch: Partial<{ title: string; description: string; goal: string; status: PlanStatus; targetDate: string; coacheeId: string | null }>,
): Promise<CoachingPlan> {
  const body: Record<string, unknown> = {};
  if (patch.title !== undefined) body.title = patch.title;
  if (patch.description !== undefined) body.description = patch.description;
  if (patch.goal !== undefined) body.goal = patch.goal;
  if (patch.status !== undefined) body.status = toApiPlanStatus(patch.status);
  if (patch.targetDate !== undefined) body.target_date = patch.targetDate || null;
  if (patch.coacheeId !== undefined) body.coachee = patch.coacheeId ? Number(patch.coacheeId) : null;
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
  return updateAction(planId, actionId, { status });
}

export async function updateAction(
  planId: string,
  actionId: string,
  patch: Partial<{ title: string; description: string; assignee: string; dueDate: string; order: number; status: TaskStatus }>,
): Promise<PlanAction> {
  const body: Record<string, unknown> = {};
  if (patch.title !== undefined) body.title = patch.title;
  if (patch.description !== undefined) body.description = patch.description;
  if (patch.assignee !== undefined) body.assignee = patch.assignee;
  if (patch.dueDate !== undefined) body.due_date = patch.dueDate;
  if (patch.order !== undefined) body.order = patch.order;
  if (patch.status !== undefined) body.status = toApiStatus(patch.status);
  const updated = await request<ApiAction>(`/api/plans/${planId}/actions/${actionId}/`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return toPlanAction(updated, planId);
}

// ---------------------------------------------------------------------------
// Calendar sessions + coach availability
// ---------------------------------------------------------------------------

interface ApiSession {
  id: number;
  title: string;
  date: string;
  duration_minutes: number;
  coachee: number | null;
  coachee_name: string;
  coaching_plan: number | null;
  coaching_plan_title: string | null;
  notes: string;
  requested_by: 'coach' | 'coachee';
}

function toUiWallTimeDate(dateText: string): string {
  const match = dateText.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  if (!match) return dateText;
  return `${match[1]}T${match[2]}`;
}

function toCalendarSession(session: ApiSession): CalendarSession {
  return {
    id: String(session.id),
    title: session.title,
    date: toUiWallTimeDate(session.date),
    durationMinutes: session.duration_minutes,
    coacheeId: session.coachee ? String(session.coachee) : null,
    coacheeName: session.coachee_name ?? '',
    coachingPlanId: session.coaching_plan ? String(session.coaching_plan) : null,
    coachingPlanTitle: session.coaching_plan_title ?? null,
    notes: session.notes ?? '',
    requestedBy: session.requested_by ?? 'coach',
  };
}

export async function listSessions(): Promise<CalendarSession[]> {
  const sessions = await request<ApiSession[] | ApiListResponse<ApiSession>>('/api/sessions/');
  return toListResults(sessions).map(toCalendarSession);
}

export async function listSessionsForPlan(planId: string): Promise<CalendarSession[]> {
  const sessions = await request<ApiSession[] | ApiListResponse<ApiSession>>(`/api/sessions/?coaching_plan_id=${planId}`);
  return toListResults(sessions).map(toCalendarSession);
}

function toApiSessionPayload(payload: {
  title?: string;
  date?: string;
  durationMinutes?: number;
  coacheeId?: string;
  coachingPlanId?: string | null;
  notes?: string;
}): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.date !== undefined) body.date = payload.date;
  if (payload.durationMinutes !== undefined) body.duration_minutes = payload.durationMinutes;
  if (payload.coacheeId !== undefined) body.coachee = payload.coacheeId ? Number(payload.coacheeId) : null;
  if (payload.coachingPlanId !== undefined) body.coaching_plan_id = payload.coachingPlanId ? Number(payload.coachingPlanId) : null;
  if (payload.notes !== undefined) body.notes = payload.notes;
  return body;
}

export async function createSession(payload: {
  title: string;
  date: string;
  durationMinutes: number;
  coacheeId?: string;
  coachId?: string;
  coachingPlanId?: string | null;
  notes?: string;
  requestedBy?: 'coach' | 'coachee';
}): Promise<CalendarSession> {
  const created = await request<ApiSession>('/api/sessions/', {
    method: 'POST',
    body: JSON.stringify({
      ...toApiSessionPayload(payload),
      coach_id: payload.coachId,
      requested_by: payload.requestedBy ?? 'coach',
      mode: 'video',
    }),
  });
  return toCalendarSession(created);
}

export async function updateSession(
  sessionId: string,
  patch: Partial<{
    title: string;
    date: string;
    durationMinutes: number;
    coacheeId: string;
    notes: string;
  }>,
): Promise<CalendarSession> {
  const body = toApiSessionPayload(patch);
  const updated = await request<ApiSession>(`/api/sessions/${sessionId}/`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return toCalendarSession(updated);
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request<void>(`/api/sessions/${sessionId}/`, { method: 'DELETE' });
}

interface ApiWeeklyAvailabilityWindow {
  id: number;
  weekday: number;
  start_time: string;
  end_time: string;
}

function toAvailabilityWindow(window: ApiWeeklyAvailabilityWindow): WeeklyAvailabilityWindow {
  return {
    id: String(window.id),
    weekday: window.weekday,
    startTime: window.start_time,
    endTime: window.end_time,
  };
}

export async function listAvailabilityWindows(coachId?: string): Promise<WeeklyAvailabilityWindow[]> {
  const suffix = coachId ? `?coach_id=${encodeURIComponent(coachId)}` : '';
  const windows = await request<ApiWeeklyAvailabilityWindow[] | ApiListResponse<ApiWeeklyAvailabilityWindow>>(`/api/availability/windows/${suffix}`);
  return toListResults(windows).map(toAvailabilityWindow);
}

export async function createAvailabilityWindow(payload: { weekday: number; startTime: string; endTime: string }): Promise<WeeklyAvailabilityWindow> {
  const created = await request<ApiWeeklyAvailabilityWindow>('/api/availability/windows/', {
    method: 'POST',
    body: JSON.stringify({
      weekday: payload.weekday,
      start_time: payload.startTime,
      end_time: payload.endTime,
    }),
  });
  return toAvailabilityWindow(created);
}

export async function deleteAvailabilityWindow(windowId: string): Promise<void> {
  await request<void>(`/api/availability/windows/${windowId}/`, { method: 'DELETE' });
}

interface ApiUnavailablePeriod {
  id: number;
  start_at: string;
  end_at: string;
  reason: string;
}

function toUnavailablePeriod(period: ApiUnavailablePeriod): UnavailablePeriod {
  return {
    id: String(period.id),
    startAt: period.start_at,
    endAt: period.end_at,
    reason: period.reason,
  };
}

export async function listUnavailablePeriods(coachId?: string): Promise<UnavailablePeriod[]> {
  const suffix = coachId ? `?coach_id=${encodeURIComponent(coachId)}` : '';
  const periods = await request<ApiUnavailablePeriod[] | ApiListResponse<ApiUnavailablePeriod>>(`/api/availability/unavailable/${suffix}`);
  return toListResults(periods).map(toUnavailablePeriod);
}

export async function createUnavailablePeriod(payload: { startAt: string; endAt: string; reason?: string }): Promise<UnavailablePeriod> {
  const created = await request<ApiUnavailablePeriod>('/api/availability/unavailable/', {
    method: 'POST',
    body: JSON.stringify({
      start_at: payload.startAt,
      end_at: payload.endAt,
      reason: payload.reason ?? '',
    }),
  });
  return toUnavailablePeriod(created);
}

export async function updateUnavailablePeriod(
  periodId: string,
  patch: Partial<{ startAt: string; endAt: string; reason: string }>,
): Promise<UnavailablePeriod> {
  const body: Record<string, unknown> = {};
  if (patch.startAt !== undefined) body.start_at = patch.startAt;
  if (patch.endAt !== undefined) body.end_at = patch.endAt;
  if (patch.reason !== undefined) body.reason = patch.reason;
  const updated = await request<ApiUnavailablePeriod>(`/api/availability/unavailable/${periodId}/`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return toUnavailablePeriod(updated);
}

export async function deleteUnavailablePeriod(periodId: string): Promise<void> {
  await request<void>(`/api/availability/unavailable/${periodId}/`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Resources (shared documents, optionally linked to a coaching plan)
// ---------------------------------------------------------------------------

interface ApiResource {
  id: number;
  title: string;
  description: string;
  category: string;
  scope: string;
  plan: number | null;
  plan_title: string | null;
  shared_with?: string[];
  file_url: string | null;
  file_name: string | null;
  owner_username: string;
  created_at: string;
}

function toResourceItem(r: ApiResource): ResourceItem {
  return {
    id: String(r.id),
    title: r.title,
    description: r.description ?? '',
    category: r.category ?? '',
    scope: r.scope ?? '',
    planId: r.plan ? String(r.plan) : null,
    planTitle: r.plan_title ?? null,
    sharedWith: r.shared_with ?? [],
    fileUrl: r.file_url ?? null,
    fileName: r.file_name ?? null,
    ownerUsername: r.owner_username ?? '',
    createdAt: r.created_at ? r.created_at.slice(0, 10) : '',
  };
}

export async function listResources(planId?: string): Promise<ResourceItem[]> {
  const suffix = planId ? `?plan=${encodeURIComponent(planId)}` : '';
  const resources = await request<ApiResource[]>(`/api/resources/${suffix}`);
  return resources.map(toResourceItem);
}

export async function createResource(payload: {
  title: string;
  description?: string;
  planId?: string | null;
  sharedWith?: string[];
  file: File;
}): Promise<ResourceItem> {
  const form = new FormData();
  form.append('title', payload.title);
  form.append('description', payload.description ?? '');
  if (payload.planId) form.append('plan', payload.planId);
  (payload.sharedWith ?? []).forEach((username) => form.append('shared_with', username));
  form.append('file', payload.file);
  const created = await request<ApiResource>('/api/resources/', { method: 'POST', body: form });
  return toResourceItem(created);
}

export async function deleteResource(resourceId: string): Promise<void> {
  await request<void>(`/api/resources/${resourceId}/`, { method: 'DELETE' });
}
