import importlib.util
import sys
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'fpga/scripts'))
from lidar_ai_reader import features

spec = importlib.util.spec_from_file_location('reference_lidar', ROOT / 'src/igor_navigation/igor_navigation/drivers/lidar_subsampler.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def record(nodes):
    return dict(nodes=nodes, timestamp_utc='2026-10-20T00:00:00Z', period_ms=80, valid_points=len(nodes), minimum_m=min((n['distance_m'] for n in nodes), default=None))


def node(angle, distance=1, quality=20):
    return dict(angle_deg=angle, distance_m=distance, quality=quality)


class FeaturesTest(unittest.TestCase):
    def test_reference_equivalence_and_quantization_bound(self):
        ranges = np.linspace(.15, 6, 360, dtype=np.float32)
        result = features(record([node(i, float(d)) for i, d in enumerate(ranges)]))
        expected = reference.LidarSubsampler().subsample_from_laserscan(ranges)
        np.testing.assert_array_equal(result['distances_m'], expected)
        self.assertEqual(result['supported_features'], 64)
        self.assertLessEqual(result['quantization_max_error_normalized'], 1 / 512)

    def test_missing_and_invalid_are_not_measured_clear_space(self):
        r = features(record([node(0, float('nan')), node(20, 1, 0), node(40, .1), node(60, 13)]))
        self.assertEqual(r['measured_bins'], 0)
        self.assertEqual(r['supported_features'], 0)
        self.assertEqual(r['q88_candidates'], [256] * 64)
        self.assertFalse(r['complete_live_observation'])
        self.assertFalse(r['motion_permit'])

    def test_fresh_grid_does_not_retain_previous_rotation(self):
        features(record([node(i) for i in range(360)]))
        self.assertEqual(features(record([]))['measured_bins'], 0)

    def test_yaw_wrap_and_minimum_range(self):
        r = features(record([node(359, .15)]), yaw_deg=1)
        self.assertEqual(r['measured_bins'], 1)
        self.assertTrue(r['feature_contract_ok'])
        # Both neighbors are needed: one isolated return does not validate a beam.
        self.assertEqual(r['supported_features'], 0)
        r = features(record([node(i, .15) for i in range(360)]))
        np.testing.assert_allclose(r['distances_m'], .15)
        self.assertEqual(r['q88_candidates'], [11] * 64)

    def test_stale_or_zero_quality_return_cannot_overwrite_valid_bin(self):
        r = features(record([node(0, 1), node(0, 2, 0)]))
        self.assertEqual(r['measured_bins'], 1)


if __name__ == '__main__':
    unittest.main()
