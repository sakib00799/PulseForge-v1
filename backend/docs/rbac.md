# Centralized permissions and tenant isolation

Implemented 2026-09-05. Policy lives in `app/core/permissions.py`.
Routes use `require_permission(Permission.X)(session, organization_id, user_id)`.
Membership is read from the database for every request; JWT roles and request-body
roles are never used as authorization evidence.

| Action | OWNER | ADMIN | ENGINEER | VIEWER |
| --- | --- | --- | --- | --- |
| Read services, events, incidents, members, public key metadata | Yes | Yes | Yes | Yes |
| Create/update/delete services | Yes | Yes | No | No |
| Acknowledge/resolve incidents | Yes | Yes | Yes | No |
| Create/rotate/revoke API keys | Yes | No | No | No |
| Manage members | Yes | Restricted | No | No |
| Read audit logs | Yes | Yes | No | No |

Admin can manage only engineer/viewer memberships; owner membership cannot be
changed by these routes. No role can assign OWNER through add/change-member.
Unknown roles have no permissions. ORGANIZATION_DELETE is reserved owner-only;
there is still no organization-delete endpoint.

Resource lookup joins organization membership before returning service, event,
incident or API-key records. Nonexistent and foreign resource UUIDs produce the
same 404 code/message. Authorized membership with insufficient permission returns
403 PERMISSION_DENIED. Organization list queries remain scoped to the caller.

`GET /api/v1/organizations` now returns `permissions` alongside each membership.
The dashboard uses this list to display service creation, key generation, Ack and
Resolve controls. Backend enforcement remains authoritative. After role changes,
reload the dashboard to refresh visible controls; API enforcement changes on the
next request even with the same access token.

## Manual verification

1. Start backend and frontend using the commands in PROJECT_HANDOFF.md.
2. Register separate owner/admin/engineer/viewer accounts through Swagger. The
   registration limit is three/hour/IP; use existing accounts where available or
   wait for the window. Tests use isolated databases and reset limiter state.
3. As owner, create an organization. Add the other registered users through
   POST /organizations/{organization_id}/members using their respective roles.
4. Sign in separately as each user. In Swagger Authorize, replace the access
   token when switching users. Never put the token into a slug field.
5. Owner: create service and API key, then send five demo events to get an incident.
6. Engineer: acknowledge/resolve succeeds; creating services or keys returns 403.
7. Viewer: reading incidents succeeds; acknowledge/resolve returns 403. Dashboard
   should hide service creation, key generation, Ack and Resolve buttons.
8. Admin: create services and read audit logs succeeds; generating keys and
   changing an owner/admin membership returns 403.
9. With a user outside the organization, request the owner's incident/event/service
   UUID. Expect 404. A random UUID gives the same error except request_id.
10. Change an admin to viewer as owner. Reuse the admin's old access token for
    service creation: expect 403 without needing a new login.

Automated checks from backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\alembic.exe check
```

No database migration is needed; schema remains at 0008. Regression tests are in
tests/security/test_permission_matrix.py, test_rbac.py and test_tenant_isolation.py.
The database tests here use SQLite; they do not establish PostgreSQL concurrency
or row-level-security guarantees. Isolation is enforced by application queries.

## Following work

Add account security/session management and audit-log screens, then strengthen
PostgreSQL integration tests and CI before deployment. The earlier concurrency
test uses SQLite with three preloaded events and two parallel inserts; a true
PostgreSQL multi-connection race test is still needed. The refresh limiter keys
by rotating token hash, so a stable session/family limit also needs follow-up.
