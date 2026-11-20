"""CPU fallback must apply once, before any model creates GPU variables."""
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch
from training.common import tensorflow_runtime


class RuntimeTests(unittest.TestCase):
    def tearDown(self):
        tensorflow_runtime.cache_clear()

    def test_cpu_configuration_is_applied_before_return_and_only_once(self):
        tensorflow_runtime.cache_clear()
        tensorflow = types.SimpleNamespace(config=Mock())
        with patch.dict(sys.modules, {'tensorflow': tensorflow}), patch.dict(os.environ, {'DAISEE_TF_DEVICE': 'cpu'}):
            self.assertIs(tensorflow_runtime(), tensorflow)
            self.assertIs(tensorflow_runtime(), tensorflow)
        tensorflow.config.set_visible_devices.assert_called_once_with([], 'GPU')

    def test_auto_preserves_available_accelerators(self):
        tensorflow_runtime.cache_clear()
        tensorflow = types.SimpleNamespace(config=Mock())
        with patch.dict(sys.modules, {'tensorflow': tensorflow}), patch.dict(os.environ, {'DAISEE_TF_DEVICE': 'auto'}):
            tensorflow_runtime()
        tensorflow.config.set_visible_devices.assert_not_called()
