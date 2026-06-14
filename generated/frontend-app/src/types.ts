export type TaskStatus = 'backlog' | 'inProgress' | 'done';
export type PlanStatus = 'todo' | 'inProgress' | 'done';

export interface Coachee {
  id: string;
  name: string;
  email: string;
  notes: string;
}

export interface CoachingPlan {
  id: string;
  title: string;
  description: string;
  goal: string;
  status: PlanStatus;
  targetDate: string;
  coacheeId: string | null;
  coacheeName: string | null;
  createdAt: string;
}

export interface PlanAction {
  id: string;
  planId: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignee: string;
  order: number;
  dueDate: string;
}

export interface PlanTask {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignee: string;
  dueDate: string;
}

export interface SessionItem {
  id: string;
  title: string;
  date: string;
  mode: 'video' | 'in-person';
  requestedBy: 'coach' | 'coachee';
}

export interface DiscussionItem {
  id: string;
  taskId: string;
  planId: string;
  author: string;
  message: string;
  mentions: string[];
  createdAt: string;
}

export interface InsightItem {
  id: string;
  author: string;
  note: string;
  createdAt: string;
}

export interface ResourceItem {
  id: string;
  title: string;
  category: 'guide' | 'worksheet' | 'link';
  scope: 'plan' | 'shared';
}
