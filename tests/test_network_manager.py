import unittest

from network_manager import MODULE_OFFLINE_TIMEOUT_SEC, ModuleHealth, NetworkManager


class ModuleHealthTests(unittest.TestCase):
    def test_recent_message_is_online_and_not_timed_out(self):
        health = ModuleHealth(timeout_sec=15.0)
        health.mark_socket_connected(now=100.0)
        health.mark_valid_message(now=105.0)

        self.assertTrue(health.online)
        self.assertFalse(health.has_timed_out(now=119.9))

    def test_message_older_than_timeout_times_out(self):
        health = ModuleHealth(timeout_sec=15.0)
        health.mark_socket_connected(now=100.0)
        health.mark_valid_message(now=101.0)

        self.assertTrue(health.has_timed_out(now=116.1))

    def test_start_timeout_does_not_change_finish(self):
        start = ModuleHealth(timeout_sec=15.0)
        finish = ModuleHealth(timeout_sec=15.0)
        start.mark_socket_connected(now=10.0)
        finish.mark_socket_connected(now=10.0)
        start.mark_valid_message(now=10.0)
        finish.mark_valid_message(now=20.0)

        self.assertTrue(start.has_timed_out(now=26.0))
        self.assertFalse(finish.has_timed_out(now=26.0))
        self.assertTrue(finish.online)

    def test_finish_timeout_does_not_change_start(self):
        start = ModuleHealth(timeout_sec=15.0)
        finish = ModuleHealth(timeout_sec=15.0)
        start.mark_socket_connected(now=20.0)
        finish.mark_socket_connected(now=10.0)
        start.mark_valid_message(now=20.0)
        finish.mark_valid_message(now=10.0)

        self.assertFalse(start.has_timed_out(now=26.0))
        self.assertTrue(finish.has_timed_out(now=26.0))
        self.assertTrue(start.online)

    def test_valid_message_after_reconnect_resets_timestamp_and_online(self):
        health = ModuleHealth(timeout_sec=MODULE_OFFLINE_TIMEOUT_SEC)
        health.mark_socket_connected(now=1.0)
        health.mark_valid_message(now=2.0)
        health.mark_disconnected()
        health.mark_socket_connected(now=30.0)

        became_online, was_previously_online = health.mark_valid_message(now=31.0)

        self.assertTrue(became_online)
        self.assertTrue(was_previously_online)
        self.assertTrue(health.online)
        self.assertEqual(health.last_message(), 31.0)
        self.assertFalse(health.has_timed_out(now=40.0))


class ProtocolValidationTests(unittest.TestCase):
    def test_start_protocol_messages(self):
        self.assertTrue(NetworkManager.is_valid_message("START", "CONNECTED_START"))
        self.assertTrue(NetworkManager.is_valid_message("START", "START"))
        self.assertTrue(NetworkManager.is_valid_message("START", "TEMP_START:42.5"))
        self.assertFalse(NetworkManager.is_valid_message("START", "TEMP_FINISH:42.5"))
        self.assertFalse(NetworkManager.is_valid_message("START", "garbage"))

    def test_finish_protocol_messages(self):
        for message in ("CONNECTED", "START", "FINISH", "READY", "RESULT_READY"):
            self.assertTrue(NetworkManager.is_valid_message("FINISH", message))
        self.assertTrue(NetworkManager.is_valid_message("FINISH", "TEMP_FINISH:39.1"))
        self.assertTrue(NetworkManager.is_valid_message("FINISH", "TIME:1.234"))
        self.assertFalse(NetworkManager.is_valid_message("FINISH", "TIME:not-a-number"))
        self.assertFalse(NetworkManager.is_valid_message("FINISH", "TEMP_START:39.1"))


if __name__ == "__main__":
    unittest.main()
