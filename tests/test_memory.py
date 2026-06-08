import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from memory import Memory


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.mem = Memory(self.db_path)

    def tearDown(self):
        self.mem._conn.close()
        self.tmpdir.cleanup()

    def test_add_and_get_messages(self):
        self.mem.add_message("user", "hello")
        self.mem.add_message("assistant", "hi there")
        msgs = self.mem.get_recent_messages(10)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "hello")
        self.assertEqual(msgs[1]["role"], "assistant")
        self.assertEqual(msgs[1]["content"], "hi there")

    def test_get_messages_respects_limit(self):
        for i in range(5):
            self.mem.add_message("user", str(i))
        msgs = self.mem.get_recent_messages(3)
        self.assertEqual(len(msgs), 3)

    def test_remember_and_recall(self):
        self.mem.remember("name", "Alice")
        self.mem.remember("city", "Beijing")
        self.assertEqual(self.mem.recall("name"), "Alice")
        self.assertEqual(self.mem.recall("city"), "Beijing")
        self.assertIsNone(self.mem.recall("nonexistent"))

    def test_remember_updates_existing(self):
        self.mem.remember("key1", "value1")
        self.mem.remember("key1", "value2")
        self.assertEqual(self.mem.recall("key1"), "value2")

    def test_recall_all(self):
        self.mem.remember("a", "1")
        self.mem.remember("b", "2")
        all_mem = self.mem.recall_all()
        self.assertEqual(all_mem, {"a": "1", "b": "2"})

    def test_forget(self):
        self.mem.remember("temp", "data")
        self.mem.forget("temp")
        self.assertIsNone(self.mem.recall("temp"))

    def test_clear_conversations(self):
        self.mem.add_message("user", "msg1")
        self.mem.clear_conversations()
        self.assertEqual(len(self.mem.get_recent_messages(10)), 0)

    def test_persistence_across_instances(self):
        self.mem.remember("key", "val")
        self.mem.add_message("user", "persist")
        self.mem._conn.close()

        mem2 = Memory(self.db_path)
        self.assertEqual(mem2.recall("key"), "val")
        msgs = mem2.get_recent_messages(10)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["content"], "persist")
        mem2._conn.close()
