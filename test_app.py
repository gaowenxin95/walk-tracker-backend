import os
import tempfile
import unittest


class WalkTrackerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["WALK_TRACKER_DB"] = os.path.join(self.tmpdir.name, "test.sqlite3")

        import app

        app.DB_PATH = app.Path(os.environ["WALK_TRACKER_DB"])
        app.init_db()
        self.app = app

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_upsert_record_calculates_distance(self):
        record = self.app.upsert_record(
            user_id="u1",
            target_date="2026-05-18",
            checked_in=True,
            steps=8000,
            stride_meters=0.7,
            note="evening walk",
        )

        self.assertTrue(record["checked_in"])
        self.assertEqual(record["steps"], 8000)
        self.assertEqual(record["distance_km"], 5.6)

    def test_records_for_days_fills_missing_dates(self):
        self.app.upsert_record(
            user_id="u1",
            target_date=self.app.today_string(),
            checked_in=True,
            steps=3000,
            stride_meters=0.7,
            note=None,
        )

        records = self.app.records_for_days("u1", 7)

        self.assertEqual(len(records), 7)
        self.assertEqual(records[-1]["date"], self.app.today_string())
        self.assertTrue(records[-1]["checked_in"])
        self.assertFalse(records[0]["checked_in"])

    def test_stats_for_days(self):
        self.app.upsert_record(
            user_id="u1",
            target_date=self.app.today_string(),
            checked_in=True,
            steps=1000,
            stride_meters=0.7,
            note=None,
        )

        stats = self.app.stats_for_days("u1", 7)

        self.assertEqual(stats["checked_in_days"], 1)
        self.assertEqual(stats["total_steps"], 1000)
        self.assertEqual(stats["total_distance_km"], 0.7)
        self.assertEqual(stats["streak_days"], 1)

    def test_activity_fields_are_saved_and_aggregated(self):
        record = self.app.upsert_record(
            user_id="u1",
            target_date=self.app.today_string(),
            checked_in=True,
            steps=6200,
            stride_meters=1.05,
            note="morning run",
            activity_type="run",
            duration_minutes=32,
            calories=None,
        )

        stats = self.app.stats_for_days("u1", 7)

        self.assertEqual(record["activity_type"], "run")
        self.assertEqual(record["duration_minutes"], 32)
        self.assertEqual(record["distance_km"], 6.51)
        self.assertGreater(record["calories"], 0)
        self.assertEqual(stats["total_duration_minutes"], 32)
        self.assertEqual(stats["activity_counts"], {"run": 1})

    def test_captcha_and_session_helpers(self):
        captcha = self.app.create_captcha()
        self.assertIn("captcha_id", captcha)
        self.assertIn("image_url", captcha)
        self.assertIn("<svg", self.app.get_captcha_image(captcha["captcha_id"]))

        with self.assertRaises(ValueError):
            self.app.validate_captcha(captcha["captcha_id"], "wrong")

        session = self.app.create_session("高文欣", "13800138000")
        found = self.app.get_session(session["token"])

        self.assertEqual(found["name"], "高文欣")
        self.assertEqual(found["phone"], "13800138000")
        self.assertEqual(found["user_id"], session["user_id"])

    def test_profile_helpers(self):
        session = self.app.create_session("高文欣", "13800138000")
        profile = self.app.upsert_profile(
            session,
            name="高文欣",
            phone="13800138000",
            height_cm=168,
            weight_kg=58.5,
            target_weight_kg=55,
        )

        self.assertEqual(profile["height_cm"], 168)
        self.assertEqual(profile["weight_kg"], 58.5)
        self.assertEqual(profile["target_weight_kg"], 55)


if __name__ == "__main__":
    unittest.main()
