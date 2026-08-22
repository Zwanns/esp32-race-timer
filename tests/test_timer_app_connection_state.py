import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from timer_app import TimerApp


class FakeLabel:
    def __init__(self):
        self.text = None
        self.style = None

    def setText(self, text):
        self.text = text

    def setStyleSheet(self, style):
        self.style = style


class ConnectionStateUiTests(unittest.TestCase):
    def test_finish_offline_invalidates_values_and_cancels_active_race(self):
        app = SimpleNamespace(
            finish_module_online=True,
            race_start_time=10.0,
            live_timer=Mock(),
            finish_status=FakeLabel(),
            finish_indicator=FakeLabel(),
            finish_beam=FakeLabel(),
            finish_temp_label=FakeLabel(),
            cancel_race_due_to_module_loss=Mock(),
        )
        app.live_timer.isActive.return_value = True

        TimerApp.update_finish_connection_state(app, False)

        self.assertFalse(app.finish_module_online)
        self.assertEqual(app.finish_status.text, "Финишный модуль: Offline")
        self.assertEqual(app.finish_beam.text, "Финишный луч: —")
        self.assertEqual(app.finish_temp_label.text, "— °C")
        app.cancel_race_due_to_module_loss.assert_called_once_with("FINISH")

    def test_start_offline_does_not_change_finish_state(self):
        app = SimpleNamespace(
            start_module_online=True,
            finish_module_online=True,
            race_start_time=None,
            live_timer=Mock(),
            start_status=FakeLabel(),
            start_indicator=FakeLabel(),
            start_beam=FakeLabel(),
            start_temp_label=FakeLabel(),
            cancel_race_due_to_module_loss=Mock(),
        )
        app.live_timer.isActive.return_value = False

        TimerApp.update_start_connection_state(app, False)

        self.assertFalse(app.start_module_online)
        self.assertTrue(app.finish_module_online)
        self.assertEqual(app.start_temp_label.text, "— °C")
        app.cancel_race_due_to_module_loss.assert_not_called()

    def test_race_cancellation_clears_unsaveable_result(self):
        app = SimpleNamespace(
            live_timer=Mock(),
            race_start_time=10.0,
            current_time=1.234,
            finish_time_from_module=1.234,
            mode_label=FakeLabel(),
            time_label=FakeLabel(),
            time_display=FakeLabel(),
            save_btn=Mock(),
            manual_race_btn=FakeLabel(),
            set_ready_style=Mock(),
            update_google_status_label=Mock(),
            log=Mock(),
        )

        TimerApp.cancel_race_due_to_module_loss(app, "FINISH")

        app.live_timer.stop.assert_called_once_with()
        self.assertIsNone(app.race_start_time)
        self.assertIsNone(app.current_time)
        self.assertIsNone(app.finish_time_from_module)
        self.assertEqual(app.mode_label.text, "Режим системы: ERROR — FINISH Offline")
        app.save_btn.setEnabled.assert_called_once_with(False)
        app.log.assert_called_once()


if __name__ == "__main__":
    unittest.main()
