# Calendar API

Calendar and coach-availability endpoints require JWT authentication.

## Sessions

- `GET /api/sessions/` (paginated)
- `POST /api/sessions/`
- `GET /api/sessions/{id}/`
- `PATCH /api/sessions/{id}/`
- `DELETE /api/sessions/{id}/`

Session payload fields:
- `title`
- `date`
- `duration_minutes`
- `coachee`
- `notes`
- `mode`
- `requested_by`

## Weekly availability windows

- `GET /api/availability/windows/` (paginated)
- `POST /api/availability/windows/`
- `GET /api/availability/windows/{id}/`
- `PATCH /api/availability/windows/{id}/`
- `DELETE /api/availability/windows/{id}/`

Window fields:
- `weekday`
- `start_time`
- `end_time`

Rules:
- `start_time < end_time`
- no overlap on same coach + weekday

## Unavailable periods

- `GET /api/availability/unavailable/` (paginated)
- `POST /api/availability/unavailable/`
- `GET /api/availability/unavailable/{id}/`
- `PATCH /api/availability/unavailable/{id}/`
- `DELETE /api/availability/unavailable/{id}/`

Period fields:
- `start_at`
- `end_at`
- `reason`

Rules:
- `start_at < end_at`
- no overlap on same coach
