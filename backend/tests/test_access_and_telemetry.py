from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app


def create(client):
    data = client.post('/api/sessions', json=dict(instructor_name='Lecturer', instructor_email='test@example.org', course_name='Test class')).json()
    return data, {'Authorization': 'Bearer ' + data['instructor_token']}


def join(client, sid):
    return client.post(f'/api/sessions/{sid}/join', json={'consent_version': 'v1', 'display_name': 'Student alias'}).json()


def test_instructor_access_and_private_roster():
    with TestClient(app) as client:
        session, headers = create(client)
        sid = session['session_id']
        student = join(client, sid)
        assert client.get(f'/api/sessions/{sid}').json()['students'] == []
        assert len(client.get(f'/api/sessions/{sid}', headers=headers).json()['students']) == 1
        assert client.get(f'/api/sessions/code/{session["join_code"]}').json()['students'] == []
        for path in ['readings', 'export']:
            assert client.get(f'/api/sessions/{sid}/{path}').status_code == 403
            assert client.get(f'/api/sessions/{sid}/{path}', headers=headers).status_code == 200
        assert client.post(f'/api/sessions/{sid}/end').status_code == 403
        assert client.post(f'/api/sessions/{sid}/rtc-token?identity=x&instructor=true').status_code == 403
        assert client.post(f'/api/sessions/{sid}/rtc-token?identity=x&instructor=true', headers=headers).status_code == 200
        assert client.post(f'/api/sessions/{sid}/rtc-token?identity={student["student_id"]}', headers={'Authorization': 'Bearer ' + student['device_token']}).status_code == 200
        other, other_headers = create(client)
        assert client.post(f'/api/sessions/{sid}/end', headers=other_headers).status_code == 403
        assert client.post(f'/api/sessions/{sid}/end', headers=headers).status_code == 200
        assert client.post(f'/api/sessions/{sid}/join', json={'consent_version': 'v1', 'display_name': 'late'}).status_code == 400
        assert client.post(f'/api/sessions/{sid}/rtc-token?identity=x&instructor=true', headers=headers).status_code == 400


def test_student_socket_validation_and_dashboard():
    with TestClient(app) as client:
        session, headers = create(client)
        sid = session['session_id']
        student = join(client, sid)
        url = f'/ws/student/{sid}/{student["student_id"]}'
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(url, subprotocols=['attention', 'invalid']):
                pass
        with client.websocket_connect(url, subprotocols=['attention', student['device_token']]) as ws:
            assert ws.accepted_subprotocol == 'attention'
            ws.send_json({'s_eye': -1})
            assert ws.receive_json()['type'] == 'error'
            # Quality states discard a bogus zero index on ingestion.
            ws.send_json(dict(s_eye=0, s_gaze=0, s_yawn=0, s_affect=0, attention_index=0, quality_flag='monitoring_paused'))
            ws.send_json({'invalid': True})
            assert ws.receive_json()['type'] == 'error'  # Prior batch committed before this response.
            readings = client.get(f'/api/sessions/{sid}/readings', headers=headers).json()
            assert readings[0]['attention_index'] is None
            with client.websocket_connect(f'/ws/instructor/{sid}', subprotocols=['attention', session['instructor_token']]) as dashboard:
                data = dashboard.receive_json()
                assert data['class_average'] is None
                assert data['student_count'] == 1
                assert data['students'][0]['quality_flag'] == 'monitoring_paused'
            assert client.get(f'/api/sessions/{sid}/readings?limit=0', headers=headers).status_code == 422
            assert client.get(f'/api/sessions/{sid}/readings?offset=-1', headers=headers).status_code == 422
            assert client.get(f'/api/sessions/{sid}/readings?offset=1', headers=headers).json() == []


def test_socket_rejects_foreign_student_and_bad_origin():
    with TestClient(app) as client:
        first, _ = create(client)
        second, _ = create(client)
        student = join(client, first['session_id'])
        for sid, origin in [(second['session_id'], 'http://localhost:3000'), (first['session_id'], 'https://untrusted.example')]:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f'/ws/student/{sid}/{student["student_id"]}', subprotocols=['attention', student['device_token']], headers={'origin': origin}):
                    pass


def test_consent_required_and_student_can_withdraw():
    with TestClient(app) as client:
        session, headers = create(client)
        sid = session['session_id']
        assert client.post(f'/api/sessions/{sid}/join', json={'display_name': 'Alias'}).status_code == 422
        student = join(client, sid)
        path = f'/api/sessions/{sid}/students/{student["student_id"]}/withdraw'
        assert client.post(path).status_code == 403
        assert client.post(path, headers={'Authorization': 'Bearer ' + student['device_token']}).status_code == 200
        assert client.get(f'/api/sessions/{sid}', headers=headers).json()['students'] == []
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f'/ws/student/{sid}/{student["student_id"]}', subprotocols=['attention', student['device_token']]):
                pass
