# Coaching Plan and Kanban Requirements

> Aligned with the current codebase (`api.models.CoachingPlan`, `api.models.Task`,
> `api.models.Message`). Plan status values are `todo` / `in_progress` / `done`;
> action (task) status values are `backlog` / `in_progress` / `done`.

## Summary
- Coaches can create one or more coaching plans for a coachee.
- Coaching plans are listed in target-date order.
- Each plan has a title, description, overall goal, status (to do / in progress / done), target date, and one or more sequenced actions, and is assigned to a coachee the coach (or an administrator) has added to the system.

## User stories
- As a coach, I want to create one or more coaching plans for a coachee.
- As a coach, I want coaching plans shown as a list in target-date order.
- As a coach, I want each coaching plan to have a title, description, overall goal, status (to do / in progress / done), target date, and one or more actions, assigned to a coachee that I or an administrator have added to the system.
- As a coach, I want each action to have a title, description, kanban status (backlog / in progress / done), assignee, and sequence order, plus discussion where participants can @mention a coach (a person an administrator has added), so that everyone stays aligned on next steps.
- As a coach, I want coaching plans and actions to include discussion threads with @mentions.
- As a coach, I want to attach resources/documents to a coaching plan, so that plan-specific materials stay together.

## Functional requirements
- The system shall allow coaches to create one or more coaching plans for a coachee.
- The system shall return coaching plans ordered by target date.
- The system shall allow each coaching plan to have a title, description, overall goal, status (to do / in progress / done), and target date, assigned to a coachee.
- The system shall allow each plan to contain sequenced actions (`/api/plans/<id>/actions`), each with a title, description, kanban status (backlog / in progress / done), assignee, order, and due date.
- The system shall support discussion messages on plans and actions, with comma-separated @mentions stored against each message.
- The system shall allow resources/documents to be optionally linked to a coaching plan.

## Non-functional requirements
- Plan and action endpoints shall require JWT authentication and be scoped to the owning coach.

## Constraints and assumptions
- Backend: Django REST Framework; plans, actions (tasks), and messages are persisted in SQLite (development).
- Coachees must be created by a coach or administrator before a plan can be assigned to them.

## Open questions / not yet implemented
- Real-time notifications for @mentions are not yet implemented; mentions are stored and displayed only.

## Sources
- Codebase: `api.models.CoachingPlan`, `api.models.Task`, `api.models.Message`
- Original intake: `generated/coaching-plan-input.txt`
