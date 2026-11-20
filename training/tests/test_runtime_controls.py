"""Cooling pauses preserve saved work and remain interruptible."""
import unittest
from unittest.mock import Mock
from training.runtime_controls import epoch_cooldown


class CoolingTests(unittest.TestCase):
    def test_default_does_not_delay_cloud_runs(self):
        sleep = Mock()
        epoch_cooldown({}, sleep)
        sleep.assert_not_called()

    def test_break_uses_short_interruptible_intervals(self):
        sleep = Mock()
        epoch_cooldown({'DAISEE_EPOCH_COOLDOWN_SECONDS': '65'}, sleep)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [30, 30, 5])

    def test_interrupt_propagates_without_continuing(self):
        sleep = Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            epoch_cooldown({'DAISEE_EPOCH_COOLDOWN_SECONDS': '300'}, sleep)
        self.assertEqual(sleep.call_count, 1)

    def test_invalid_break_is_rejected(self):
        for value in ('-1', '3601', 'bad'):
            with self.assertRaises(ValueError):
                epoch_cooldown({'DAISEE_EPOCH_COOLDOWN_SECONDS': value}, Mock())
