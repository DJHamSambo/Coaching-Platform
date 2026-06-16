# Code Review Report

| Field | Value |
|---|---|
| Commit | `feature/calendar-week-year-scheduling` |
| Base | `main` |
| Timestamp | 2026-06-16T20:38:21.559020+00:00 |
| Overall quality score | **5.0/10** |
| Files reviewed | 21 |
| Models used | github/gpt-4o |
| Total findings | 31 |
| Consensus issues | 0 |
| Agent patches applied | 0 |

## Files reviewed

- `docs/calendar-api.md`
- `generated/backend-app/api/migrations/0002_message_task_id.py`
- `generated/backend-app/api/migrations/0004_session_duration_coachee_notes_weeklyavailabilitywindow_and_more.py`
- `generated/backend-app/api/migrations/0005_alter_task_options_alter_coachee_id_and_more.py`
- `generated/backend-app/api/migrations/0006_session_related_name_and_availability_indexes.py`
- `generated/backend-app/api/migrations/0007_rename_api_unavail_coach_i_761992_idx_api_unavail_coach_i_6b2239_idx_and_more.py`
- `generated/backend-app/api/models.py`
- `generated/backend-app/api/sessions_serializers.py`
- `generated/backend-app/api/sessions_views.py`
- `generated/backend-app/api/tests/test_sessions_serializers.py`
- `generated/backend-app/coaching_backend/urls.py`
- `generated/frontend-app/src/App.tsx`
- `generated/frontend-app/src/api.ts`
- `generated/frontend-app/src/components/CalendarPanel.tsx`
- `generated/frontend-app/src/components/LoginScreen.tsx`
- `generated/frontend-app/src/components/calendar/CalendarViews.tsx`
- `generated/frontend-app/src/components/calendar/calendarUtils.ts`
- `generated/frontend-app/src/constants/messages.ts`
- `generated/frontend-app/src/styles.css`
- `generated/frontend-app/src/types.ts`
- `generated/frontend-app/src/types/calendarTypes.ts`

## Per-model summaries

### github/gpt-4o (score: 5/10)

The code introduces useful features like availability windows and unavailable periods but suffers from significant issues in security, maintainability, and technical debt. The authorization logic is insufficiently robust, and there is code duplication in validation functions. Additionally, the API documentation is inconsistent, and the expanded API surface area increases the risk of bugs and vulnerabilities. While the code is functional, it requires significant improvements to be production-ready. | The code introduces significant new functionality, including calendar sessions and availability management, but suffers from several issues across coding standards, security, maintainability, and technical debt. The backend code has minor style issues, while the frontend code has more severe problems, including token handling vulnerabilities, lack of modularization, and missing tests. Additionally, the new API surface area increases the complexity of the codebase, requiring careful documentation and testing. | The code introduces several new calendar components and utility functions, which are generally well-structured but suffer from inconsistent naming conventions, potential security vulnerabilities, and a lack of test coverage. The components are large and could benefit from being broken into smaller, reusable pieces. Additionally, there are concerns about hardcoded values in both the code and CSS, which could hinder maintainability and localization efforts. While the code is functional, it introduces technical debt and potential security risks that need to be addressed.

## 🔴 Critical findings (2)

### [github/gpt-4o] Breaking change in `Session` model
- **File**: `generated/backend-app/api/models.py` line 91
- **Dimension**: `codebase_impact`

The `Session` model has been modified to include new fields (`duration_minutes`, `coachee`, `notes`) and changes to the `coachee` field's `related_name`. These changes may break existing code or APIs that rely on the previous model structure.

> **Fix**: Ensure that all dependent code and APIs are updated to handle the new fields and `related_name`. Consider providing a migration guide or backward compatibility if this change affects external clients.

### [github/gpt-4o] Insufficient authorization checks in `SessionsListView`
- **File**: `generated/backend-app/api/sessions_views.py` line 52
- **Dimension**: `security`

The `SessionsListView` and `SessionsDetailView` rely on `OwnsObjectPermission` for authorization. However, the `OwnsObjectPermission` implementation does not account for cases where the `owner` or `coach` attributes are missing or manipulated, potentially allowing unauthorized access.

> **Fix**: Enhance the `OwnsObjectPermission` class to include stricter checks and ensure that all objects have the expected attributes. Additionally, consider adding unit tests to verify the behavior of the permission class.

## 🟠 High findings (7)

### [github/gpt-4o] Potential security issue with `OwnsObjectPermission`
- **File**: `generated/backend-app/api/sessions_views.py` line 10
- **Dimension**: `security`

The `OwnsObjectPermission` class assumes that objects will always have either an `owner` or `coach` attribute. If an object lacks these attributes, the method will return `False` by default, which may lead to unintended behavior or security vulnerabilities.

> **Fix**: Add explicit error handling or logging for cases where neither `owner` nor `coach` attributes are present. Consider raising an exception if the object does not have the expected attributes.

### [github/gpt-4o] Expanded API surface area
- **File**: `generated/backend-app/api/sessions_views.py` line 1
- **Dimension**: `codebase_impact`

The addition of new views for `WeeklyAvailabilityWindow` and `UnavailablePeriod` significantly expands the API surface area. This increases the potential for bugs and security vulnerabilities.

> **Fix**: Ensure that the new API endpoints are thoroughly tested and documented. Consider conducting a security review to identify potential vulnerabilities.

### [github/gpt-4o] Potential refresh token leakage
- **File**: `generated/frontend-app/src/api.ts` line 114
- **Dimension**: `security`

The refresh token is stored in `localStorage`, which is vulnerable to XSS attacks. If an attacker gains access to the browser's JavaScript execution context, they can steal the refresh token and use it to obtain new access tokens.

> **Fix**: Store the refresh token in a more secure location, such as an HTTP-only, secure cookie, to mitigate the risk of XSS attacks.

### [github/gpt-4o] Complex and repetitive token handling logic
- **File**: `generated/frontend-app/src/api.ts` line 87
- **Dimension**: `technical_debt`

The token handling logic in the `request` function is overly complex and contains repeated patterns for refreshing tokens and retrying requests. This increases the risk of bugs and makes the code harder to understand.

> **Fix**: Refactor the token handling logic into a dedicated utility function or middleware that can be reused across the application. This will reduce duplication and improve maintainability.

### [github/gpt-4o] Significant API surface area expansion
- **File**: `generated/frontend-app/src/api.ts` line 668
- **Dimension**: `codebase_impact`

The addition of calendar session and availability-related API functions significantly increases the API surface area. This introduces new dependencies and potential points of failure.

> **Fix**: Ensure that the new API endpoints are well-documented, thoroughly tested, and follow the same conventions as existing endpoints. Consider adding integration tests to verify the new functionality.

### [github/gpt-4o] Potential XSS vulnerability in button titles
- **File**: `generated/frontend-app/src/components/calendar/CalendarViews.tsx` line 64
- **Dimension**: `security`

The `title` attribute for buttons uses unescaped user-provided data (`session.title` and `period.reason`). If these values are not sanitized, they could lead to Cross-Site Scripting (XSS) attacks.

> **Fix**: Sanitize `session.title` and `period.reason` using a library like `DOMPurify` before rendering them in the `title` attribute.

### [github/gpt-4o] Lack of unit tests for components
- **File**: `generated/frontend-app/src/components/calendar/CalendarViews.tsx`
- **Dimension**: `technical_debt`

The new components (`MonthCalendarView`, `WeekCalendarView`, `YearCalendarView`) lack corresponding unit tests, which increases the risk of regressions and makes future changes more difficult.

> **Fix**: Write unit tests for each component to ensure proper functionality and prevent regressions. Focus on edge cases like empty data, invalid inputs, and user interactions.

## 🟡 Medium findings (18)

### [github/gpt-4o] Inconsistent formatting in API documentation
- **File**: `docs/calendar-api.md`
- **Dimension**: `coding_standards`

The API documentation lacks consistency in formatting. For example, the payload fields are listed as bullet points without specifying their data types or constraints. Additionally, the rules for overlapping time periods are mentioned but not clearly defined in terms of error codes or responses.

> **Fix**: Use a consistent format for documenting API endpoints, including HTTP methods, request/response examples, data types, and error codes. Consider using an API documentation tool like Swagger or OpenAPI.

### [github/gpt-4o] Code duplication in validation logic
- **File**: `generated/backend-app/api/sessions_serializers.py` line 5
- **Dimension**: `maintainability`

The `_validate_ordered_range` function is duplicated in multiple serializers (e.g., `WeeklyAvailabilityWindowSerializer` and `UnavailablePeriodSerializer`). This leads to code duplication and makes future changes more error-prone.

> **Fix**: Extract the `_validate_ordered_range` function into a shared utility module and reuse it across serializers.

### [github/gpt-4o] Hardcoded pagination settings
- **File**: `generated/backend-app/api/sessions_views.py` line 15
- **Dimension**: `maintainability`

The `CalendarPageNumberPagination` class has hardcoded values for `page_size` and `max_page_size`. This makes it difficult to adjust these settings without modifying the code.

> **Fix**: Move the pagination settings to a configuration file or environment variables to make them easier to manage and change.

### [github/gpt-4o] Incomplete `_resolve_actor` function
- **File**: `generated/backend-app/api/sessions_serializers.py` line 13
- **Dimension**: `technical_debt`

The `_resolve_actor` function attempts to determine the actor (user) for a serializer but relies on assumptions about the presence of certain attributes (`coach`, `owner`). This could lead to incorrect behavior if the assumptions are not met.

> **Fix**: Refactor `_resolve_actor` to handle cases where the expected attributes are not present. Consider raising an error or logging a warning in such cases.

### [github/gpt-4o] Insufficient test coverage for serializers
- **File**: `generated/backend-app/api/tests/test_sessions_serializers.py`
- **Dimension**: `maintainability`

The test file only includes tests for overlapping validation in `WeeklyAvailabilityWindowSerializer` and `UnavailablePeriodSerializer`. Other critical aspects, such as field-level validation and edge cases, are not tested.

> **Fix**: Add comprehensive tests for all serializers, including field-level validation, edge cases, and integration tests with views.

### [github/gpt-4o] Excessively long import line
- **File**: `generated/backend-app/coaching_backend/urls.py` line 9
- **Dimension**: `coding_standards`

The import statement for `SessionsListView`, `SessionsDetailView`, etc., is excessively long and violates PEP 8 guidelines for line length. This reduces readability and maintainability.

> **Fix**: Break the import statement into multiple lines or use a wildcard import if appropriate, e.g., `from api.sessions_views import (SessionsListView, SessionsDetailView, WeeklyAvailabilityWindowListView, WeeklyAvailabilityWindowDetailView, UnavailablePeriodListView, UnavailablePeriodDetailView)`.

### [github/gpt-4o] Excessive component size
- **File**: `generated/frontend-app/src/components/CalendarPanel.tsx`
- **Dimension**: `maintainability`

The `CalendarPanel` component is over 800 lines long, making it difficult to read, understand, and maintain. Large components are harder to test and debug.

> **Fix**: Break the `CalendarPanel` component into smaller, reusable components. For example, separate the session form, unavailable period form, and calendar views into their own components.

### [github/gpt-4o] Lack of CSRF protection for refresh token endpoint
- **File**: `generated/frontend-app/src/api.ts` line 136
- **Dimension**: `security`

The `/api/auth/refresh/` endpoint does not appear to include CSRF protection. This could allow an attacker to perform a CSRF attack to refresh tokens on behalf of a user.

> **Fix**: Ensure that the refresh token endpoint is protected against CSRF attacks by using CSRF tokens or other mitigation techniques.

### [github/gpt-4o] Lack of unit tests for CalendarPanel
- **File**: `generated/frontend-app/src/components/CalendarPanel.tsx` line 808
- **Dimension**: `maintainability`

The `CalendarPanel` component introduces significant new functionality but does not appear to have corresponding unit tests. This increases the risk of regressions.

> **Fix**: Write unit tests for the `CalendarPanel` component, focusing on key functionalities such as session creation, availability management, and error handling.

### [github/gpt-4o] Unused constant `GENERIC_API_ERROR_MESSAGE`
- **File**: `generated/frontend-app/src/api.ts` line 48
- **Dimension**: `technical_debt`

The constant `GENERIC_API_ERROR_MESSAGE` is imported but not used in the file. This adds unnecessary clutter to the codebase.

> **Fix**: Remove the unused `GENERIC_API_ERROR_MESSAGE` constant to reduce clutter and improve code clarity.

### [github/gpt-4o] New feature integration without feature flag
- **File**: `generated/frontend-app/src/App.tsx` line 222
- **Dimension**: `codebase_impact`

The new `CalendarPanel` feature is directly integrated into the application without a feature flag. This could lead to issues if the feature is not fully tested or needs to be rolled back.

> **Fix**: Wrap the `CalendarPanel` integration in a feature flag to allow for controlled rollout and easier rollback if issues arise.

### [github/gpt-4o] Inconsistent naming conventions
- **File**: `generated/frontend-app/src/components/calendar/CalendarViews.tsx` line 11
- **Dimension**: `coding_standards`

The naming conventions for interfaces and props are inconsistent. For example, `MonthCalendarViewProps` uses camelCase for property names, but `YearSummaryItem` uses snake_case for some properties (e.g., `sessionCount` vs. `unavailable_count`).

> **Fix**: Adopt a consistent naming convention across all interfaces and props, preferably camelCase for JavaScript/TypeScript.

### [github/gpt-4o] Hardcoded weekday labels
- **File**: `generated/frontend-app/src/components/calendar/calendarUtils.ts` line 1
- **Dimension**: `coding_standards`

The `WEEKDAY_LABELS` array is hardcoded in English, which limits internationalization and localization support.

> **Fix**: Use a localization library like `i18next` or `Intl.DateTimeFormat` to dynamically generate weekday labels based on the user's locale.

### [github/gpt-4o] Potential vulnerability in date parsing
- **File**: `generated/frontend-app/src/components/calendar/calendarUtils.ts` line 12
- **Dimension**: `security`

The `toLocalDateTimeInputValue` function uses `new Date(dateText)` to parse a date string. This can lead to unexpected behavior if the input is not properly validated, as `new Date()` has inconsistent behavior across browsers.

> **Fix**: Validate the input date string format explicitly using a library like `date-fns` or `luxon` before parsing.

### [github/gpt-4o] Large component with multiple responsibilities
- **File**: `generated/frontend-app/src/components/calendar/CalendarViews.tsx`
- **Dimension**: `maintainability`

The `MonthCalendarView`, `WeekCalendarView`, and `YearCalendarView` components are large and handle multiple responsibilities, making them harder to maintain and test.

> **Fix**: Break these components into smaller, reusable subcomponents (e.g., `CalendarCell`, `WeekRow`, `YearCard`) to improve readability and maintainability.

### [github/gpt-4o] Hardcoded styles in CSS
- **File**: `generated/frontend-app/src/styles.css` line 5
- **Dimension**: `maintainability`

Several styles are hardcoded in the CSS file (e.g., colors, padding, and font sizes), which makes it harder to maintain and customize the design.

> **Fix**: Use CSS variables or a design system to centralize and manage styles more effectively.

### [github/gpt-4o] No tests for utility functions
- **File**: `generated/frontend-app/src/components/calendar/calendarUtils.ts`
- **Dimension**: `technical_debt`

The utility functions in `calendarUtils.ts` are not covered by tests, which makes it difficult to ensure their correctness and reliability.

> **Fix**: Write unit tests for all utility functions, including edge cases for date parsing and formatting.

### [github/gpt-4o] Expansion of API surface area
- **File**: `generated/frontend-app/src/types/calendarTypes.ts`
- **Dimension**: `codebase_impact`

The addition of new types (`CalendarSession`, `WeeklyAvailabilityWindow`, `UnavailablePeriod`) expands the API surface area, increasing the potential for breaking changes in the future.

> **Fix**: Document these types thoroughly and ensure they are versioned properly to minimize the risk of breaking changes.

## 🔵 Low findings (4)

### [github/gpt-4o] No-op migration with unclear purpose
- **File**: `generated/backend-app/api/migrations/0002_message_task_id.py` line 12
- **Dimension**: `technical_debt`

The migration file `0002_message_task_id.py` is a no-op with a comment explaining its purpose. However, this could lead to confusion for future developers who might not understand why this migration exists.

> **Fix**: Consider adding a more detailed comment explaining the historical context and why this migration is necessary. Alternatively, consolidate migrations if possible.

### [github/gpt-4o] Inconsistent event naming convention
- **File**: `generated/frontend-app/src/App.tsx` line 66
- **Dimension**: `coding_standards`

The custom event `auth:expired` does not follow a consistent naming convention. This can lead to confusion and inconsistency in the codebase.

> **Fix**: Consider using a consistent naming convention for custom events, such as `auth-expired` or `auth/expired`, to align with other event naming patterns.

### [github/gpt-4o] Inline functions in JSX
- **File**: `generated/frontend-app/src/components/calendar/CalendarViews.tsx` line 45
- **Dimension**: `coding_standards`

Inline functions are used in JSX (e.g., `onClick={() => onCreateSession(date)}`), which can lead to unnecessary re-renders and performance issues.

> **Fix**: Move these inline functions to a separate function outside the JSX to improve performance and readability.

### [github/gpt-4o] Addition of new CSS variables
- **File**: `generated/frontend-app/src/styles.css` line 5
- **Dimension**: `codebase_impact`

New CSS variables (e.g., `--modal-card-padding`, `--modal-card-radius`, `--modal-card-shadow`) have been added, which could affect existing styles if not properly scoped.

> **Fix**: Ensure these variables are scoped to specific components or namespaces to avoid unintended side effects.
