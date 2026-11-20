"""Load the official TF.js Keras writer without unused native SavedModel converters.

The tensorflowjs package eagerly imports TensorFlow Decision Forests for graph
conversion. Keras LayersModel export only uses its HDF5 writer, which is portable
on Apple silicon. Load that installed upstream module via package namespaces;
no model, operator or weight-conversion code is replaced. Numerical parity is
still required by the export/smoke-test callers.
"""
from __future__ import annotations
import importlib
import importlib.metadata
import importlib.machinery
from pathlib import Path
import sys
import types


def keras_converter():
    distribution = importlib.metadata.distribution('tensorflowjs')
    location = Path(distribution.locate_file('tensorflowjs')).resolve()
    for name, directory in [('tensorflowjs', location), ('tensorflowjs.converters', location / 'converters')]:
        if name in sys.modules:
            continue
        namespace = types.ModuleType(name)
        namespace.__path__ = [str(directory)]
        namespace.__package__ = name
        namespace.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
        namespace.__spec__.submodule_search_locations = namespace.__path__
        sys.modules[name] = namespace
    return importlib.import_module('tensorflowjs.converters.keras_h5_conversion')
