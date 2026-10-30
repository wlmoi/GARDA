"""
LiDAR Subsampler for IGOR Obstacle Avoidance Suite.
Converts raw 360-degree LiDAR pointcloud/scans into precisely 64 frontal beams [-pi/2, +pi/2].
"""

from typing import Optional, Union, List
import numpy as np


class LidarSubsampler:
    """
    Subsamples and filters full 360-degree LiDAR scans (e.g. Slamtec RPLiDAR A1/A2)
    into standard 64 frontal beams [-90 deg, +90 deg] expected by IGOR controllers.
    """

    def __init__(
        self,
        num_target_rays: int = 64,
        angle_min: float = -np.pi / 2.0,
        angle_max: float = np.pi / 2.0,
        min_range: float = 0.15,
        max_range: float = 3.50
    ):
        self.num_target_rays = num_target_rays
        self.angle_min = angle_min
        self.angle_max = angle_max
        self.min_range = min_range
        self.max_range = max_range
        self.target_angles = np.linspace(angle_min, angle_max, num_target_rays)

    def subsample_scan(
        self,
        raw_ranges: Union[np.ndarray, List[float]],
        raw_angle_min: float = -np.pi,
        raw_angle_max: float = np.pi
    ) -> np.ndarray:
        """
        Resamples raw 360 scan array into 64 frontal beams.

        Args:
            raw_ranges: 1D array of ranges from sensor (meters).
            raw_angle_min: starting angle of raw scan (-pi for standard ROS LaserScan).
            raw_angle_max: ending angle of raw scan (+pi for standard ROS LaserScan).

        Returns:
            np.ndarray of shape (64,) with ranges in meters clipped to [0.15, 3.50].
        """
        raw_ranges = np.array(raw_ranges, dtype=np.float32)
        n_raw = len(raw_ranges)
        if n_raw == 0:
            return np.full(self.num_target_rays, self.max_range, dtype=np.float32)

        raw_angles = np.linspace(raw_angle_min, raw_angle_max, n_raw)

        # Sanitize NaNs and Infs to max_range
        clean_ranges = np.where(
            np.isnan(raw_ranges) | np.isinf(raw_ranges) | (raw_ranges <= 0.05),
            self.max_range,
            raw_ranges
        )

        # Interpolate onto target frontal angle grid
        subsampled = np.interp(self.target_angles, raw_angles, clean_ranges)
        return np.clip(subsampled, self.min_range, self.max_range).astype(np.float32)

    def subsample_from_laserscan(
        self,
        raw_ranges: Union[np.ndarray, List[float]],
        angle_min: float = 0.0,
        angle_max: float = 2.0 * np.pi
    ) -> np.ndarray:
        """
        Resamples a 360-degree LaserScan (whether [0, 2pi] or [-pi, pi]) into 64 frontal beams [-pi/2, +pi/2].
        """
        raw_ranges = np.array(raw_ranges, dtype=np.float32)
        n_raw = len(raw_ranges)
        if n_raw == 0:
            return np.full(self.num_target_rays, self.max_range, dtype=np.float32)

        angles = np.linspace(angle_min, angle_max, n_raw, endpoint=False)
        # Wrap all angles to [-pi, pi]
        wrapped_angles = (angles + np.pi) % (2.0 * np.pi) - np.pi

        # Sort by wrapped angles so np.interp works monotonically
        sort_idx = np.argsort(wrapped_angles)
        sorted_angles = wrapped_angles[sort_idx]
        sorted_ranges = raw_ranges[sort_idx]

        # Sanitize NaNs and Infs to max_range
        clean_ranges = np.where(
            np.isnan(sorted_ranges) | np.isinf(sorted_ranges) | (sorted_ranges <= 0.05),
            self.max_range,
            sorted_ranges
        )

        subsampled = np.interp(self.target_angles, sorted_angles, clean_ranges)
        return np.clip(subsampled, self.min_range, self.max_range).astype(np.float32)
