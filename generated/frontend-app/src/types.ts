export type TaskStatus = 'backlog' | 'inProgress' | 'done';
export type PlanStatus = 'todo' | 'inProgress' | 'done';

export interface Coachee {
  id: string;
  name: string;
  email: string;
  notes: string;
}

export interface QuestionnaireAnswer {
  question: string;
  answer: string;
}

export interface QuestionnaireItem {
  id: string;
  name: string;
  answers: QuestionnaireAnswer[];
  submittedAt: string;
}

export interface ContractParty {
  name: string;
  address: string;
  phone: string;
  email: string;
}

export interface ContractData {
  agreementDate: string;
  coach: ContractParty;
  coachee: ContractParty & { dateOfBirth: string };
  periodSessions: string;
  sessionCycle: string;
  commencementDate: string;
  totalFee: string;
  paymentArrangement: 'advance' | 'instalments';
  coachSignatureName: string;
  coachSignature: string;
  coachSignedAt: string;
  coacheeSignatureName: string;
  coacheeSignature: string;
  coacheeSignedAt: string;
}

export interface ContractItem {
  id: string;
  title: string;
  data: ContractData;
  createdAt: string;
}

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'coach' | 'coachee';
  isAdmin: boolean;
  mustResetPassword: boolean;
  avatarUrl: string | null;
  phone: string;
}

export interface AdminCoach {
  id: string;
  username: string;
  email: string;
  isAdmin: boolean;
  isActive: boolean;
}

export interface AdminCoachee extends Coachee {
  addedById: string;
  addedByUsername: string;
  user?: string | null;
  userUsername?: string;
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
  coachUsername: string | null;
  createdAt: string;
  documents?: ResourceItem[];
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
  updatedAt?: string;
  coacheeId?: string | null;
  coacheeName?: string | null;
}

export interface ResourceItem {
  id: string;
  title: string;
  description: string;
  category: string;
  scope: string;
  planId: string | null;
  planTitle: string | null;
  sharedWith: string[];
  fileUrl: string | null;
  fileName: string | null;
  ownerUsername: string;
  createdAt: string;
}

export type NotificationType = 'mention' | 'session_booked' | 'task_assigned' | 'action_created' | 'plan_assigned' | 'resource_added';

export interface NotificationItem {
  id: string;
  actorName: string;
  type: NotificationType;
  message: string;
  targetType: 'plan' | 'action' | 'session' | 'insight' | 'resource' | '';
  targetId: string | null;
  planId: string | null;
  actionId: string | null;
  isRead: boolean;
  createdAt: string;
}

export type { CalendarSession, WeeklyAvailabilityWindow, UnavailablePeriod } from './types/calendarTypes';
