import unittest
from app import create_app


class FinanceApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()
        # Tests use the configured SQLite file; create a unique user for each test run.
        import uuid

        self.email = f"test-{uuid.uuid4().hex}@example.test"
        self.client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": self.email,
                "password": "testpassword123",
            },
        )

    def test_authenticated_dashboard(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertIn("balance", response.json["data"])

    def test_user_is_required(self):
        client = self.app.test_client()
        response = client.get("/api/transactions")
        self.assertEqual(response.status_code, 401)

    def test_transaction_create(self):
        categories = self.client.get("/api/categories").json["data"]
        category = next(c for c in categories if c["kind"] == "expense")
        response = self.client.post(
            "/api/transactions",
            json={
                "kind": "expense",
                "amount": 12.5,
                "transaction_date": "2026-11-17",
                "category_id": category["id"],
                "note": "Test expense",
            },
        )
        self.assertEqual(response.status_code, 201)

    def _notices(self):
        return [n["title"] for n in self.client.get("/api/notifications").json["data"]]

    def test_daily_reminder_once_per_day_and_can_be_disabled(self):
        self.client.get("/api/auth/me")
        self.client.get("/api/auth/me")
        self.assertEqual(self._notices().count("Daily expenditure reminder"), 1)
        response = self.client.put("/api/settings", json={"expenditure_reminder": 0})
        self.assertEqual(response.json["data"]["expenditure_reminder"], 0)

    def test_new_month_notice_and_carry_forward(self):
        from database.db import connect

        self.client.get("/api/auth/me")
        with connect() as conn:
            conn.execute(
                "UPDATE user_settings SET last_open_month='2000-01' WHERE user_id=(SELECT id FROM users WHERE email=?)",
                (self.email,),
            )
        self.client.get("/api/auth/me")
        self.client.get("/api/auth/me")
        self.assertEqual(self._notices().count("New month balance updated"), 1)
        categories = self.client.get("/api/categories").json["data"]
        income = next(c for c in categories if c["kind"] == "income")
        self.client.post(
            "/api/transactions",
            json={"kind": "income", "amount": 100, "category_id": income["id"], "transaction_date": "2020-05-10"},
        )
        data = self.client.get("/api/dashboard?month=2020-06").json["data"]
        self.assertEqual(data["carried_forward"], 100)
        self.assertEqual(data["balance"], 100)

    def test_display_settings_validation(self):
        ok = self.client.put(
            "/api/settings", json={"theme": "system", "language": "tl", "date_format": "DD/MM/YYYY", "decimal_separator": ","}
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.put("/api/settings", json={"language": "fr"}).status_code, 400)
        self.assertEqual(self.client.put("/api/settings", json={"theme": "pink"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
