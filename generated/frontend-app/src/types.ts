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

export type ContractStatus = 'awaiting_coachee' | 'executed';

export interface ContractItem {
  id: string;
  title: string;
  data: ContractData;
  status: ContractStatus;
  coacheeAcceptedTerms: boolean;
  coachUsername: string | null;
  coacheeId: string | null;
  coacheeName: string | null;
  coacheeUsername: string | null;
  createdAt: string;
  updatedAt: string;
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
  userEmail?: string;
  userPhone?: string;
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

export type NotificationType = 'mention' | 'session_booked' | 'task_assigned' | 'action_created' | 'plan_assigned' | 'resource_added' | 'contract_awaiting_signature' | 'contract_executed';

// Single source of truth for valid notification target types: the runtime array
// drives the TS union below, so adding a new target type here automatically
// updates NotificationItem['targetType'] everywhere (see api.ts toNotificationItem).
export const NOTIFICATION_TARGET_TYPES = ['plan', 'action', 'session', 'insight', 'resource', 'contract'] as const;
export type NotificationTargetType = (typeof NOTIFICATION_TARGET_TYPES)[number] | '';

export interface NotificationItem {
  id: string;
  actorName: string;
  type: NotificationType;
  message: string;
  targetType: NotificationTargetType;
  targetId: string | null;
  planId: string | null;
  actionId: string | null;
  isRead: boolean;
  createdAt: string;
}

export type { CalendarSession, WeeklyAvailabilityWindow, UnavailablePeriod } from './types/calendarTypes';
