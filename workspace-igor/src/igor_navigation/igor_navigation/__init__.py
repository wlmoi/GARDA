"""
=============================================================================
IGOR NAVIGATION: Autonomous Mobile Robot (AMR) Obstacle Avoidance Suite
Target Platform: Hiwonder JetAuto Mecanum (Jetson Orin Nano + STM32)
PERURI Chip Hackathon 2026
=============================================================================
"""

__version__ = "3.0.0"
__author__ = "Team IGOR - PERURI Chip Hackathon 2026"

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(PACKAGE_DIR, "weights")
HARDWARE_DIR = os.path.join(WEIGHTS_DIR, "hardware")

from .controllers import (
    BaseController,
    CLDRLController,
    CBFFilterController,
    MiniDWAShieldController,
    DWAController,
    APFController,
    create_controller
)

from .utils import (
    MecanumKinematics,
    GlobalPath,
    LookaheadCarrotTracker,
    BenchmarkMetricsTracker
)

from .drivers import (
    SerialJetAutoDriver,
    LidarSubsampler
)

__all__ = [
    "__version__",
    "PACKAGE_DIR",
    "WEIGHTS_DIR",
    "HARDWARE_DIR",
    "BaseController",
    "CLDRLController",
    "CBFFilterController",
    "MiniDWAShieldController",
    "DWAController",
    "APFController",
    "create_controller",
    "MecanumKinematics",
    "GlobalPath",
    "LookaheadCarrotTracker",
    "BenchmarkMetricsTracker",
    "SerialJetAutoDriver",
    "LidarSubsampler"
]
