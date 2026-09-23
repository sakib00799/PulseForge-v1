from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.modules.organizations.models import Organization, OrganizationMember, OrganizationRole
from app.modules.services.models import Service, ServiceEnvironment
from app.modules.incidents.models import Incident, IncidentStatus, IncidentSeverity
from app.modules.events.models import Event, EventLevel
from app.modules.api_keys.models import ApiKey
from app.modules.users.models import User


@pytest.fixture
def tenant(security_client):
    client, factory = security_client
    with factory() as session:
        users = {role: User(email=f'{role}@example.com', full_name=role, password_hash='unused')
                 for role in ['OWNER', 'ADMIN', 'ENGINEER', 'VIEWER', 'OUTSIDER']}
        session.add_all(users.values())
        session.flush()
        org = Organization(name='Matrix', slug='matrix', created_by_id=users['OWNER'].id)
        session.add(org)
        session.flush()
        for role in OrganizationRole:
            session.add(OrganizationMember(organization_id=org.id, user_id=users[role].id, role=role))
        service = Service(organization_id=org.id, name='Payments', slug='payments',
                          environment=ServiceEnvironment.DEVELOPMENT)
        session.add(service)
        session.flush()
        incident = Incident(organization_id=org.id, service_id=service.id, title='Failure',
                            fingerprint='f', status=IncidentStatus.OPEN,
                            severity=IncidentSeverity.SEV_2, detected_at=datetime.now(timezone.utc))
        event = Event(organization_id=org.id, service_id=service.id, event_id='event',
                      event_type='FAILURE', level=EventLevel.ERROR, message='Failure',
                      fingerprint='f', occurred_at=datetime.now(timezone.utc), metadata_json={})
        key = ApiKey(organization_id=org.id, service_id=service.id, name='Key',
                     prefix='pf_test_', key_hash='hash', scopes=['events:write'])
        session.add_all([incident, event, key])
        session.commit()
        ids = dict(org=org.id, service=service.id, incident=incident.id, event=event.id, key=key.id)
        headers = {role: {'Authorization': f'Bearer {create_access_token(str(user.id))}'}
                   for role, user in users.items()}
    return client, factory, ids, headers


@pytest.mark.parametrize('role', ['OWNER', 'ADMIN', 'ENGINEER', 'VIEWER'])
@pytest.mark.parametrize('action,allowed', [
    ('service', {'OWNER', 'ADMIN'}), ('key', {'OWNER'}),
    ('acknowledge', {'OWNER', 'ADMIN', 'ENGINEER'}),
    ('resolve', {'OWNER', 'ADMIN', 'ENGINEER'}), ('audit', {'OWNER', 'ADMIN'}),
])
def test_action_permissions(tenant, role, action, allowed):
    client, _, ids, headers = tenant
    if action == 'service':
        response = client.post('/api/v1/services', headers=headers[role], json={
            'organization_id': str(ids['org']), 'name': 'New', 'slug': 'new', 'environment': 'development'})
    elif action == 'key':
        response = client.post(f"/api/v1/services/{ids['service']}/api-keys",
                               headers=headers[role], json={'name': 'New key'})
    elif action == 'audit':
        response = client.get('/api/v1/audit-logs', params={'organization_id': str(ids['org'])},
                              headers=headers[role])
    else:
        response = client.post(f"/api/v1/incidents/{ids['incident']}/{action}", headers=headers[role])
    expected = (201 if action in {'service', 'key'} else 200) if role in allowed else 403
    assert response.status_code == expected


@pytest.mark.parametrize('method,path,resource', [
    ('get', '/services/{}', 'service'), ('patch', '/services/{}', 'service'),
    ('delete', '/services/{}', 'service'), ('get', '/events/{}', 'event'),
    ('get', '/incidents/{}', 'incident'), ('post', '/incidents/{}/acknowledge', 'incident'),
    ('post', '/incidents/{}/resolve', 'incident'), ('delete', '/api-keys/{}', 'key'),
    ('post', '/api-keys/{}/rotate', 'key'), ('get', '/services/{}/api-keys', 'service'),
])
def test_foreign_and_missing_resource_have_identical_errors(tenant, method, path, resource):
    client, factory, ids, headers = tenant
    options = {'headers': headers['OUTSIDER']}
    if method == 'patch':
        options['json'] = {'name': 'Intrusion'}
    responses = [client.request(method, '/api/v1' + path.format(value), **options)
                 for value in [ids[resource], uuid4()]]
    errors = []
    for response in responses:
        assert response.status_code == 404
        error = response.json()['error']
        error.pop('request_id')
        errors.append(error)
    assert errors[0] == errors[1]
    with factory() as session:
        assert session.get(Service, ids['service']).name == 'Payments'
        assert session.get(Incident, ids['incident']).status == IncidentStatus.OPEN
        assert session.get(ApiKey, ids['key']).revoked_at is None


@pytest.mark.parametrize('route', ['events', 'incidents', 'services', 'audit-logs'])
def test_cross_tenant_lists_are_not_visible(tenant, route):
    client, _, ids, headers = tenant
    response = client.get(f'/api/v1/{route}', params={'organization_id': str(ids['org'])},
                          headers=headers['OUTSIDER'])
    assert response.status_code == 404


def test_membership_changes_take_effect_without_new_access_token(tenant):
    client, factory, ids, headers = tenant
    from sqlalchemy import select
    with factory() as session:
        membership = session.scalar(select(OrganizationMember).where(
            OrganizationMember.organization_id == ids['org'],
            OrganizationMember.role == OrganizationRole.ADMIN))
        membership.role = OrganizationRole.VIEWER
        session.commit()
    response = client.post('/api/v1/services', headers=headers['ADMIN'], json={
        'organization_id': str(ids['org']), 'name': 'New', 'slug': 'new', 'environment': 'development'})
    assert response.status_code == 403
    memberships = client.get('/api/v1/organizations', headers=headers['ADMIN']).json()
    assert 'service:create' not in memberships[0]['permissions']
    assert 'incident:read' in memberships[0]['permissions']


@pytest.mark.parametrize('role', ['OWNER', 'ADMIN'])
def test_ownership_assignment_is_denied(tenant, role):
    client, _, ids, headers = tenant
    response = client.post(f"/api/v1/organizations/{ids['org']}/members", headers=headers[role],
                           json={'email': 'OUTSIDER@example.com', 'role': 'OWNER'})
    assert response.status_code == 403
