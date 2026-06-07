// API client — talks to the Django backend at http://localhost:8000
// All calls attach the stored JWT token automatically.

const BASE_URL = 'http://127.0.0.1:8000';
const TOKEN_KEY = 'coaching_jwt';

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
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

  // 204 No Content
  if (response.status === 204) return undefined as unknown as T;
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface LoginPayload { username: string; password: string }
export interface LoginResponse { access: string; refresh: string }
export interface RegisterPayload { username: string; password: string; email?: string }
export interface RegisterResponse { id: number; username: string }
export interface MeResponse { id: number; username: string; email: string }

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  return request<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getMe(): Promise<MeResponse> {
  return request<MeResponse>('/api/users/me');
}

// ---------------------------------------------------------------------------
// Generic CRUD helpers
// ---------------------------------------------------------------------------

export interface ApiItem {
  id: number;
  title: string;
  description?: string;
  owner_id?: number;
  created_at?: string;
  updated_at?: string;
}

export async function listItems(resource: string): Promise<ApiItem[]> {
  return request<ApiItem[]>(`/api/${resource}/`);
}

export async function createItem(resource: string, payload: { title: string; description?: string }): Promise<ApiItem> {
  return request<ApiItem>(`/api/${resource}/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateItem(resource: string, id: number, payload: Partial<{ title: string; description: string }>): Promise<ApiItem> {
  return request<ApiItem>(`/api/${resource}/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteItem(resource: string, id: number): Promise<void> {
  return request<void>(`/api/${resource}/${id}/`, { method: 'DELETE' });
}
