from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class Alert:
    scenario_id: str
    time: str
    node_ids: List[str]
    level: Literal["WARNING", "CRITICAL"]
    reason: str
    source: Literal["B0", "B1", "AGENT"]


class Detector(ABC):
    """Abstract base class for all ground-subsidence hazard detectors.
    
    A detector must strictly follow the no-lookahead constraint:
    at any timestep t, only readings from timestamps <= t may be accessed.
    Future rows or ground-truth labels (type, is_hazard, onset_time, collapse_time, events)
    are strictly barred from scenario_meta and update().
    """

    @abstractmethod
    def reset(self, scenario_meta: Dict[str, Any]) -> None:
        """Reset internal state for a new scenario.
        
        scenario_meta may contain:
          - scenario_id (str)
          - node_coordinates_m (dict)
          - blast_schedule (list)
        Ground truth fields are strictly forbidden.
        """
        pass

    @abstractmethod
    def update(self, timestamp: str, readings_by_node: Dict[str, Any]) -> List[Alert]:
        """Process readings for all available nodes at the given timestamp.
        
        Returns a list of Alert instances triggered at this timestep.
        """
        pass

