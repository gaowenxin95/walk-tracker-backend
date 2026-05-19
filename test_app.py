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


if __name__ == "__main__":
    unittest.main()
