import type { DiscussionItem, InsightItem, PlanTask, ResourceItem, SessionItem } from '../types';

export const requirementTitle = 'Development Requirements';

export const initialTasks: PlanTask[] = [
  { id: 'task-1', title: 'Define coaching goal and milestones', description: 'Break goal into sequenced actions.', status: 'backlog', assignee: 'Coachee', dueDate: '2026-07-01' },
  { id: 'task-2', title: 'Prepare coaching session agenda', description: 'Align outcomes and expectations.', status: 'inProgress', assignee: 'Coach', dueDate: '2026-06-20' },
  { id: 'task-3', title: 'Capture progress insights', description: 'Document insights and next actions.', status: 'done', assignee: 'Coach', dueDate: '2026-06-12' },
];

export const initialSessions: SessionItem[] = [
  { id: 'session-1', title: 'Weekly Coaching Session', date: '2026-06-18T14:00', mode: 'video', requestedBy: 'coachee' },
  { id: 'session-2', title: 'Plan Review', date: '2026-06-25T10:00', mode: 'in-person', requestedBy: 'coach' },
];

export const initialDiscussions: DiscussionItem[] = [
  { id: 'discussion-1', taskId: 'task-2', planId: '', author: 'Coachee', message: '@Coach can we adjust this action priority?', mentions: ['Coach'], createdAt: '2026-06-14' },
  { id: 'discussion-2', taskId: 'task-2', planId: '', author: 'Coach', message: '@Coachee yes, move outreach to this week.', mentions: ['Coachee'], createdAt: '2026-06-14' },
];

export const initialInsights: InsightItem[] = [
  { id: 'insight-1', author: 'Coach', note: 'Confidence increases when tasks are clearly scoped.', createdAt: '2026-06-10' },
  { id: 'insight-2', author: 'Coachee', note: 'Morning planning sessions improve execution.', createdAt: '2026-06-11' },
];

export const initialResources: ResourceItem[] = [
  { id: 'resource-1', title: 'Goal decomposition worksheet', category: 'worksheet', scope: 'plan' },
  { id: 'resource-2', title: 'Feedback conversation guide', category: 'guide', scope: 'shared' },
  { id: 'resource-3', title: 'Weekly reflection template', category: 'guide', scope: 'shared' },
];
