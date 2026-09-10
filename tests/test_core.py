"""CPU regression checks; no network, downloaded model, FFmpeg or GPU required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import workflow as wf


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'time': 0., 'duration': .04}, {'time': .04, 'duration': .12},
                     {'time': .16, 'duration': .20}, {'time': .36, 'duration': .08}]

    def test_time_formats(self):
        for value in ('92.417', '01:32.417', '1分32.417秒'):
            self.assertAlmostEqual(wf.seconds(value), 92.417)

    def test_invalid_times(self):
        for value in ('nan', 'inf', '-1', '1:99', '1:2:3:4'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                wf.seconds(value)

    def test_vfr_nearest(self):
        self.assertEqual(wf.select_indices(self.rows, .30, False), [3])

    def test_float_equidistant_prefers_earlier(self):
        rows = [{'time': 92.4, 'duration': .034}, {'time': 92.434, 'duration': .033}]
        self.assertEqual(wf.select_indices(rows, 92.417, False), [0])

    def test_nearby_keeps_center_and_stays_in_window(self):
        selected = wf.select_indices(self.rows, .16, True, count=3, radius=.13)
        self.assertIn(2, selected)
        self.assertTrue(all(abs(self.rows[i]['time']-.16) <= .13 for i in selected))

    def test_last_frame_valid_until_end(self):
        self.assertEqual(wf.select_indices(self.rows, .43, False), [3])
        with self.assertRaises(ValueError):
            wf.select_indices(self.rows, .44, False)


class InputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='anime-enhance-tests-')
        self.root = Path(self.temp.name)
        self.patch = patch.object(wf, 'ROOT', self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_unique_output_directories(self):
        a, b = wf.job_dir('output', 'same'), wf.job_dir('output', 'same')
        self.assertNotEqual(a, b)
        self.assertTrue(a.is_dir() and b.is_dir())

    def test_16bit_rejected_before_output(self):
        path = self.root / '16bit.png'
        Image.fromarray(np.full((8, 8), 1024, dtype=np.uint16)).save(path)
        original = wf.digest(path)
        with self.assertRaisesRegex(ValueError, '8-bit'):
            wf.enhance(path)
        self.assertEqual(wf.digest(path), original)
        self.assertFalse((self.root/'output').exists())

    def test_large_image_rejected_before_inference(self):
        path = self.root / 'large.png'
        Image.new('RGB', (10, 10)).save(path)
        with patch.dict(wf.CONFIG, {'max_native_output_pixels': 100}):
            with self.assertRaisesRegex(ValueError, '阈值'):
                wf.enhance(path)
        self.assertFalse((self.root/'output').exists())

    def test_ultra_2x_rejected(self):
        path = self.root / 'image.png'
        Image.new('RGB', (8, 8)).save(path)
        with self.assertRaises(ValueError):
            wf.enhance(path, level='ultra', scale=2)

    def test_project_relative_path_is_portable(self):
        inside = self.root / 'output' / 'job' / 'result.json'
        self.assertEqual(wf.project_relative(inside), 'output/job/result.json')


if __name__ == '__main__':
    unittest.main()
