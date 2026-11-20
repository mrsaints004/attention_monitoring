"""Exercise real backbone loading, one weighted update, save/reload and JS conversion."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from .common import HEADS, read_spec
from .train import make_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pretrained', type=Path, default=Path('training/artifacts/pretrained/mobilenet_7.h5'))
    parser.add_argument('--output', type=Path, default=Path('training/artifacts/environment_smoke.json'))
    args = parser.parse_args()
    from .common import tensorflow_runtime
    tf = tensorflow_runtime()
    from .keras_export import keras_converter
    converter = keras_converter()
    import numpy as np
    import mediapipe as mp
    tf.keras.utils.set_random_seed(42)
    spec = read_spec()
    with mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=2) as mesh:
        mesh.process(np.zeros((224, 224, 3), dtype=np.uint8))
    model = make_model(str(args.pretrained))
    model.compile(optimizer=tf.keras.optimizers.Adam(0.001),
                  loss={head: 'sparse_categorical_crossentropy' for head in HEADS})
    pixels = np.random.default_rng(42).integers(0, 256, size=(2, *spec['input']['shape']), dtype=np.uint8)
    values = pixels.astype('float32') - np.asarray(spec['input']['mean'], dtype='float32')
    model.train_on_batch(values, {head: np.asarray([0, 1]) for head in HEADS},
                         sample_weight={head: np.asarray([1.0, 1.0]) for head in HEADS})
    with tempfile.TemporaryDirectory(prefix='daisee-smoke-') as temp:
        directory = Path(temp)
        checkpoint = directory / 'resume.keras'
        model.save(checkpoint)
        restored = tf.keras.models.load_model(checkpoint, custom_objects={'relu6': tf.nn.relu6})
        # Confirm that optimizer state as well as predictions can survive a saved checkpoint.
        restored.train_on_batch(values, {head: np.asarray([0, 1]) for head in HEADS})
        export = directory / 'browser'
        converter.save_keras_model(restored, str(export))
        probabilities = restored.predict(values[:1], verbose=0)
        probe = directory / 'parity.json'
        probe.write_text(json.dumps({'input': spec['input'], 'cases': [
            {'pixels': pixels[0].flatten().tolist(), 'expected': [p[0].tolist() for p in probabilities]}]}))
        subprocess.run(['node', str(Path(__file__).with_name('verify_export.cjs')), str(export), str(probe)], check=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'status': 'passed', 'scope': 'Environment smoke test only; synthetic inputs, no DAiSEE training or accuracy',
        'tensorflow': tf.__version__, 'gpu_devices': [d.name for d in tf.config.get_visible_devices('GPU')],
        'checks': ['MediaPipe initialisation', 'real face backbone loading', 'weighted three-head gradient update',
                   'optimizer save/reload/update', 'Python/JavaScript inference parity']}, indent=2) + '\n')
    print('Environment smoke test passed. This is not a trained DAiSEE release.')


if __name__ == '__main__':
    main()
