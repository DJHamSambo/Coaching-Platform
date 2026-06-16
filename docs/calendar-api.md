# Calendar API

All endpoints require `Authorization: Bearer <access_token>`.

## Conventions

- Content type: `application/json`
- Date-time format: ISO 8601 (`YYYY-MM-DDTHH:mm:ssZ`)
- List endpoints are paginated: `{ count, next, previous, results }`
- Ownership: coaches can only read/write their own sessions and availability

## Session model compatibility

The `Session` resource now includes:

- `duration_minutes` (`integer`, default: `60`, minimum: `1`)
- `coachee` (`integer | null`, FK to coachee)
- `notes` (`string`, optional)

Backward compatibility notes:

- Existing clients can continue sending prior required fields.
- New fields are optional on create and patch.
- Responses include `coachee_name` for display compatibility.

## Sessions

### GET /api/sessions/

Returns paginated sessions owned by the authenticated user.

Response item shape:

- `id`: `integer`
- `title`: `string`
- `date`: `string | null`
- `duration_minutes`: `integer`
- `coachee`: `integer | null`
- `coachee_name`: `string`
- `notes`: `string`
- `mode`: `"video" | "in-person" | "phone"`
- `requested_by`: `string`
- `owner`: `integer`
- `created_at`: `string`
- `updated_at`: `string`

### POST /api/sessions/

Example request:

```json
{
  "title": "Quarterly check-in",
  "date": "2026-06-10T10:00:00Z",
  "duration_minutes": 60,
  "coachee": 4,
  "notes": "Review progress and blockers",
  "mode": "video",
  "requested_by": "coach"
}
```

### PATCH /api/sessions/{id}/

Partial updates are supported for all writable fields.

### DELETE /api/sessions/{id}/

Returns `204 No Content` on success.

## Weekly availability windows

### GET /api/availability/windows/

Returns paginated weekly windows for the authenticated coach.

### POST /api/availability/windows/

Example request:

```json
{
  "weekday": 1,
  "start_time": "09:00:00",
  "end_time": "17:00:00"
}
```

Validation rules:

- `start_time < end_time`
- No overlap with existing window on same `weekday` for same coach

## Unavailable periods

### GET /api/availability/unavailable/

Returns paginated unavailable periods for the authenticated coach.

### POST /api/availability/unavailable/

Example request:

```json
{
  "start_at": "2026-06-10T13:00:00Z",
  "end_at": "2026-06-10T15:00:00Z",
  "reason": "Client workshop"
}
```

Validation rules:

- `start_at < end_at`
- No overlap with existing unavailable period for same coach

## Error responses

Validation failures return `400 Bad Request`.

Example overlap error:

```json
{
  "non_field_errors": [
    "Availability window overlaps an existing entry."
  ]
}
```

Authentication failure returns `401 Unauthorized`.

Authorization/ownership failure returns `403 Forbidden`.
