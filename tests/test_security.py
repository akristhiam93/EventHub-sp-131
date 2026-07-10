import os
import unittest

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import app
from api.models import Admin, Promotor, User, db
from api.security import hash_password


class SecurityFlowTests(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        app.config["TESTING"] = True
        db.drop_all()
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_roles_and_password_hashing(self):
        response = self.client.post("/api/users", json={
            "name": "Ana", "email": "ana@example.com", "password": "secret"
        })
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(User.query.first().password, "secret")

        user_token = self.client.post("/api/user/login", json={
            "email": "ana@example.com", "password": "secret"
        }).get_json()["token"]
        self.assertEqual(self.client.post("/api/categories", json={"name": "Music"}).status_code, 401)
        self.assertEqual(self.client.post("/api/categories", json={"name": "Music"}, headers={
            "Authorization": f"Bearer {user_token}"
        }).status_code, 403)

        db.session.add(Admin(email="admin@example.com", password=hash_password("admin-secret"), is_active=True))
        db.session.add(Promotor(name="Org", email="org@example.com", password=hash_password("org-secret"),
                                location="Madrid", phone=123456789, web_page="https://example.com", verified_org=True))
        db.session.commit()

        admin_token = self.client.post("/api/admin/login", json={
            "email": "admin@example.com", "password": "admin-secret"
        }).get_json()["token"]
        self.assertEqual(self.client.post("/api/categories", json={"name": "Music"}, headers={
            "Authorization": f"Bearer {admin_token}"
        }).status_code, 201)
        self.assertEqual(self.client.get("/api/promotor/1/events", headers={
            "Authorization": f"Bearer {user_token}"
        }).status_code, 403)


if __name__ == "__main__":
    unittest.main()
