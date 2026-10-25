import pytest
from app import create_app
from models import db, User, Skill, MaidProfile, EmployerProfile, HiringRequest
from werkzeug.security import generate_password_hash

@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "SECRET_KEY": "test-secret",
    })
    with app.app_context():
        db.create_all()
        for name in ["Cooking","Cleaning","Washing Clothes","Ironing","Babysitting","Elderly Care","All Household Work"]:
            db.session.add(Skill(name=name))
        maid = User(full_name="Test Maid", mobile="9876543210", email="maid@test.com",
                    password_hash=generate_password_hash("TestPass123!"), role="maid")
        maid.maid_profile = MaidProfile(age=30, gender="Female", address="Private", city="Delhi", state="Delhi",
            experience_years=3, expected_salary=10000, working_hours="Morning", job_type="Part-time",
            consent_public_profile=True, is_available=True)
        employer = User(full_name="Test Employer", mobile="9876543211", email="employer@test.com",
                        password_hash=generate_password_hash("TestPass123!"), role="employer")
        employer.employer_profile = EmployerProfile(house_address="Private", city="Delhi", state="Delhi", budget=12000)
        db.session.add_all([maid, employer]); db.session.commit()
    yield app
    with app.app_context(): db.drop_all()

@pytest.fixture()
def client(app): return app.test_client()

def login(client, identity, password="TestPass123!"):
    return client.post("/login", data={"identity": identity, "password": password}, follow_redirects=True)

def test_login_with_email(client):
    response = login(client, "maid@test.com")
    assert response.status_code == 200
    assert b"Test Maid" in response.data

def test_login_rejects_wrong_password(client):
    response = login(client, "maid@test.com", "wrong")
    assert b"Invalid credentials" in response.data

def test_registration_rejects_duplicate_mobile(client):
    response = client.post("/register/maid", data={
        "full_name":"Duplicate", "mobile":"9876543210", "email":"new@test.com",
        "password":"TestPass123!", "confirm_password":"TestPass123!", "age":"25",
        "address":"Somewhere", "city":"Delhi", "state":"Delhi", "experience_years":"1",
        "expected_salary":"9000", "working_hours":"Morning", "job_type":"Part-time"
    }, follow_redirects=True)
    assert b"already registered" in response.data

def test_employer_can_search_maids(client):
    login(client, "employer@test.com")
    response = client.get("/maids")
    assert response.status_code == 200
    assert b"Test Maid" in response.data

def test_employer_can_send_hiring_request(client):
    login(client, "employer@test.com")
    with client.application.app_context():
        maid = User.query.filter_by(mobile="9876543210").first()
        maid_id = maid.id
    response = client.post(f"/hire/{maid_id}", data={
        "job_location":"Delhi", "salary_offered":"11000", "work_timings":"8 AM - 1 PM",
        "job_description":"Cooking and cleaning"
    }, follow_redirects=True)
    assert response.status_code == 200
    with client.application.app_context():
        assert HiringRequest.query.count() == 1
        assert HiringRequest.query.first().status == "Pending"


def test_chat_message_can_be_sent_only_by_hiring_participants(client, app):
    login(client, "employer@test.com")
    with app.app_context():
        maid = User.query.filter_by(mobile="9876543210").first()
        employer = User.query.filter_by(mobile="9876543211").first()
        req = HiringRequest(employer_id=employer.id, maid_id=maid.id, job_location="Delhi",
                            salary_offered=11000, work_timings="8 AM - 1 PM", status="Pending")
        db.session.add(req)
        db.session.commit()
        request_id = req.id
    response = client.post(f"/chat/{request_id}", data={"body": "Hello, are you available?"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Hello, are you available?" in response.data


def test_chat_is_forbidden_to_non_participant(client, app):
    login(client, "employer@test.com")
    with app.app_context():
        maid = User.query.filter_by(mobile="9876543210").first()
        employer = User.query.filter_by(mobile="9876543211").first()
        req = HiringRequest(employer_id=employer.id, maid_id=maid.id, job_location="Delhi",
                            salary_offered=11000, work_timings="8 AM - 1 PM", status="Pending")
        db.session.add(req)
        db.session.commit()
        request_id = req.id
    # Log out the employer and register/login a separate maid account for this authorization test.
    client.post("/logout", data={}, follow_redirects=True)
    with app.app_context():
        stranger = User(full_name="Other Employer", mobile="9876543212", email="other@test.com",
                        password_hash=generate_password_hash("TestPass123!"), role="employer")
        stranger.employer_profile = EmployerProfile(house_address="Private", city="Delhi", state="Delhi", budget=12000)
        db.session.add(stranger)
        db.session.commit()
    login(client, "other@test.com")
    response = client.get(f"/chat/{request_id}")
    assert response.status_code == 404
