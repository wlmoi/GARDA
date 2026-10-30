"""
IGOR JetAuto Obstacle Avoidance Controllers Suite
"""

from .base_controller import BaseController
from .drl_controller import CLDRLController
from .cbf_safety_filter import CBFFilterController
from .mini_dwa_shield import MiniDWAShieldController
from .dwa_controller import DWAController
from .apf_controller import APFController


CONTROLLER_REGISTRY = {
    "drl": CLDRLController,
    "cl_drl": CLDRLController,
    "cbf": CBFFilterController,
    "drl_cbf": CBFFilterController,
    "cl_drl_cbf": CBFFilterController,
    "dwa_shield": MiniDWAShieldController,
    "mini_dwa": MiniDWAShieldController,
    "drl_dwa": MiniDWAShieldController,
    "cl_drl_dwa": MiniDWAShieldController,
    "dwa": DWAController,
    "standalone_dwa": DWAController,
    "apf": APFController,
    "standalone_apf": APFController
}


def create_controller(algo_name: str, **kwargs) -> BaseController:
    """
    Factory helper to instantiate any of the 5 obstacle avoidance controllers.

    Available names:
      - 'cl_drl' / 'drl'
      - 'cl_drl_cbf' / 'drl_cbf'
      - 'cl_drl_dwa' / 'drl_dwa'
      - 'dwa'
      - 'apf'
    """
    key = algo_name.lower().strip()
    if key not in CONTROLLER_REGISTRY:
        raise ValueError(
            f"Unknown controller '{algo_name}'. Available: {list(CONTROLLER_REGISTRY.keys())}"
        )
    return CONTROLLER_REGISTRY[key](**kwargs)


__all__ = [
    "BaseController",
    "CLDRLController",
    "CBFFilterController",
    "MiniDWAShieldController",
    "DWAController",
    "APFController",
    "create_controller",
    "CONTROLLER_REGISTRY"
]
