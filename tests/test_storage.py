"""Storage tests: inspections, logs, migration of old databases and artifact versions.

Each test uses a temporary data folder. TemporaryDirectory cleanup fails on
Windows if a connection stays open, so passing tests also prove connections close.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import storage

URL = "http://localhost:8000/login"
SNAPSHOT = {"sourceUrl": URL, "elements": []}


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(storage, "DATA_DIR", Path(self.tmp.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()


class InspectionStorageTests(StorageTestCase):
    def test_save_and_load_with_timestamp(self):
        saved = storage.save_inspection(SNAPSHOT)
        self.assertTrue(saved["inspectedAt"])
        self.assertEqual(storage.load_inspection(saved["inspectionId"]), saved)

    def test_missing_inspection_raises(self):
        with self.assertRaises(FileNotFoundError):
            storage.load_inspection("00000000-0000-0000-0000-000000000000")

    def test_list_inspections_filters_by_url_newest_first(self):
        first = storage.save_inspection(SNAPSHOT)
        storage.save_inspection({"sourceUrl": "http://localhost:8000/other", "elements": []})
        second = storage.save_inspection(SNAPSHOT)
        listed = storage.list_inspections(URL)
        self.assertEqual([i["inspectionId"] for i in listed], [second["inspectionId"], first["inspectionId"]])
        self.assertEqual(len(storage.list_inspections()), 3)

    def test_failed_write_is_rolled_back(self):
        saved = storage.save_inspection(SNAPSHOT)
        with self.assertRaises(sqlite3.IntegrityError):
            with storage.connect() as db:
                db.execute("INSERT INTO logs (payload) VALUES ('{}')")
                db.execute("INSERT INTO inspections (id, payload) VALUES (?, '{}')", (saved["inspectionId"],))
        self.assertEqual(storage.list_logs(), [])


class LogStorageTests(StorageTestCase):
    def test_logs_filtered_by_inspection(self):
        storage.save_log({"inspectionId": "a", "goal": "g1"})
        storage.save_log({"inspectionId": "b", "goal": "g2"})
        logs = storage.list_logs("a")
        self.assertEqual([log["goal"] for log in logs], ["g1"])
        self.assertTrue(logs[0]["loggedAt"])
        self.assertEqual(len(storage.list_logs()), 2)


class MigrationTests(StorageTestCase):
    def test_old_database_is_migrated_and_backfilled(self):
        old = sqlite3.connect(Path(self.tmp.name) / storage.DB_NAME)
        old.execute("CREATE TABLE inspections (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        old.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        inspection_id = "11111111-1111-1111-1111-111111111111"
        old.execute("INSERT INTO inspections VALUES (?, ?)",
                    (inspection_id, json.dumps({**SNAPSHOT, "inspectionId": inspection_id})))
        old.execute("INSERT INTO logs (payload) VALUES (?)",
                    (json.dumps({"inspectionId": inspection_id, "goal": "old"}),))
        old.commit()
        old.close()

        self.assertEqual(storage.load_inspection(inspection_id)["sourceUrl"], URL)
        self.assertEqual(storage.list_inspections(URL)[0]["inspectionId"], inspection_id)
        self.assertEqual(storage.list_logs(inspection_id)[0]["goal"], "old")


class VersionStorageTests(StorageTestCase):
    def test_versions_number_list_and_get(self):
        v1 = storage.save_version("testcases", "plan-1", {"cases": ["a"]}, note="draft")
        v2 = storage.save_version("testcases", "plan-1", {"cases": ["a", "b"]})
        other = storage.save_version("code", "plan-1", "print('x')")
        self.assertEqual((v1["version"], v2["version"], other["version"]), (1, 2, 1))
        listed = storage.list_versions("testcases", "plan-1")
        self.assertEqual([v["version"] for v in listed], [1, 2])
        self.assertNotIn("payload", listed[0])
        self.assertEqual(storage.get_version("testcases", "plan-1", 1)["payload"], {"cases": ["a"]})

    def test_restore_saves_old_payload_as_new_version(self):
        storage.save_version("code", "pom", "v1 code")
        storage.save_version("code", "pom", "v2 code")
        old = storage.get_version("code", "pom", 1)
        restored = storage.save_version("code", "pom", old["payload"], note="restored from v1")
        self.assertEqual(restored["version"], 3)
        self.assertEqual(storage.get_version("code", "pom", 3)["payload"], "v1 code")

    def test_unknown_type_and_missing_version(self):
        with self.assertRaises(ValueError):
            storage.save_version("screenshots", "x", {})
        with self.assertRaises(FileNotFoundError):
            storage.get_version("code", "missing", 1)


if __name__ == "__main__":
    unittest.main()
