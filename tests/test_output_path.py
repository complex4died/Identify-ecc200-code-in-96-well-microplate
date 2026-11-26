import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from function.def_input import load_input, resolve_output_path


class OutputPathTests(unittest.TestCase):
    def test_existing_directory_including_dotted_name(self):
        with tempfile.TemporaryDirectory(suffix='.v1') as tmp:
            expected = Path(tmp) / 'plate_mapped.png'
            self.assertEqual(resolve_output_path('plate.jpg', tmp), expected)

    def test_new_extensionless_path_is_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'new_results'
            self.assertEqual(resolve_output_path('plate.jpg', output), output / 'plate_mapped.png')
            self.assertFalse(output.exists())

    def test_explicit_image_extension_preserved(self):
        for extension in ['png', 'jpg', 'JPEG', 'bmp', 'tif', 'tiff']:
            path = Path('results') / f'image.{extension}'
            self.assertEqual(resolve_output_path('plate.png', path), path)

    def test_invalid_extension_and_input_overwrite_rejected(self):
        with self.assertRaises(ValueError):
            resolve_output_path('plate.png', 'results.csv')
        with self.assertRaises(ValueError):
            resolve_output_path('plate.png', 'plate.png')

    def test_output_parent_is_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'occupied'
            path.touch()
            with self.assertRaises(ValueError):
                resolve_output_path('plate.png', path)
            with self.assertRaises(ValueError):
                resolve_output_path('plate.png', path / 'result.png')

    def test_default_png_and_invalid_format_rejected_before_image_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'input.png'
            self.assertTrue(cv2.imwrite(str(source), np.zeros((10,10,3), np.uint8)))
            with patch.object(sys, 'argv', ['main.py', '-i', str(source)]):
                _, output, args = load_input(include_options=True)
            self.assertEqual(output, Path('saved_image.png'))
            self.assertEqual(args.output, output)
            with patch.object(sys, 'argv', ['main.py', '-i', str(source), '-o', 'bad.csv']), \
                 patch.object(cv2, 'imread') as read, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    load_input()
                self.assertEqual(error.exception.code, 2)
                read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
