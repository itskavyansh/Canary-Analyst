import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

from agent.tools import (
    get_node_history,
    compare_neighbor_nodes,
    get_sensor_health,
    check_blast_schedule,
    project_time_to_threshold
)

# OpenAI-style tool function definitions (additionalProperties: False)
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_node_history",
            "description": "Retrieve summary metrics, baseline noise std, peak timing, return to baseline, and downsampled values for a sensor channel on a specific node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Node identifier (e.g., NODE_01)"},
                    "channel": {"type": "string", "enum": ["tilt", "tilt_x", "tilt_y", "vibration", "distance", "piezo_peak", "piezo_rms", "piezo_peak_to_peak"], "description": "Sensor metric channel"},
                    "minutes_back": {"type": "integer", "description": "Number of minutes of historical telemetry to analyze prior to as_of (e.g. 60)"}
                },
                "required": ["node_id", "channel", "minutes_back"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_neighbor_nodes",
            "description": "Compare cross-node spatial dynamics, correlation matrix, peak time sequence, and distance-decay physics across the 4-node monitoring array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["tilt", "tilt_x", "tilt_y", "vibration", "distance", "piezo_peak"], "description": "Channel to compare across nodes"},
                    "window_minutes": {"type": "integer", "description": "Observation window duration in minutes prior to as_of (e.g. 30)"}
                },
                "required": ["channel", "window_minutes"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sensor_health",
            "description": "Inspect hardware diagnostics, status flags (MPU-6050, HC-SR04, ADS1115), consecutive constant readings count (stuck detection), rail saturation fraction, and noise ratio versus calibrated baseline profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Node identifier (e.g. NODE_02)"}
                },
                "required": ["node_id"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_blast_schedule",
            "description": "Check quarry operations log for scheduled blasting activities occurring within +-30 minutes of the event time.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "project_time_to_threshold",
            "description": "Perform ordinary least squares (OLS) trend projection on a channel to calculate slope, statistical significance (t-stat, r2), and projected minutes until crossing demonstration threshold.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Node identifier (e.g. NODE_01)"},
                    "channel": {"type": "string", "enum": ["tilt", "distance", "vibration"], "description": "Physical channel under drift"},
                    "fit_minutes": {"type": "integer", "description": "Lookback duration in minutes used for OLS regression fitting (e.g. 30)"},
                    "threshold": {"type": "number", "description": "Optional explicit threshold value"}
                },
                "required": ["node_id", "channel", "fit_minutes"],
                "additionalProperties": False
            }
        }
    }
]


# Pydantic validation models
class NodeHistoryArgs(BaseModel):
    node_id: str
    channel: str
    minutes_back: int


class CompareNeighborArgs(BaseModel):
    channel: str
    window_minutes: int


class SensorHealthArgs(BaseModel):
    node_id: str


class BlastScheduleArgs(BaseModel):
    pass


class ProjectThresholdArgs(BaseModel):
    node_id: str
    channel: str
    fit_minutes: int
    threshold: Optional[float] = None


class ToolDispatcher:
    """Safe tool dispatcher that validates arguments and returns clean JSON error structures on failure."""

    def __init__(
        self,
        readings: List[Dict[str, Any]],
        blast_schedule: List[Dict[str, Any]],
        as_of: str,
        node_layout: Optional[Dict[str, Any]] = None
    ):
        self.readings = readings
        self.blast_schedule = blast_schedule
        self.as_of = as_of
        self.node_layout = node_layout or {}

    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool call, guaranteeing a JSON-serializable dictionary output without throwing unhandled exceptions."""
        try:
            if tool_name == "get_node_history":
                args = NodeHistoryArgs(**arguments)
                return get_node_history(
                    readings=self.readings,
                    as_of=self.as_of,
                    node_id=args.node_id,
                    channel=args.channel,
                    minutes_back=args.minutes_back
                )

            elif tool_name == "compare_neighbor_nodes":
                args = CompareNeighborArgs(**arguments)
                return compare_neighbor_nodes(
                    readings=self.readings,
                    as_of=self.as_of,
                    channel=args.channel,
                    window_minutes=args.window_minutes
                )

            elif tool_name == "get_sensor_health":
                args = SensorHealthArgs(**arguments)
                return get_sensor_health(
                    readings=self.readings,
                    as_of=self.as_of,
                    node_id=args.node_id
                )

            elif tool_name == "check_blast_schedule":
                BlastScheduleArgs(**arguments)
                return check_blast_schedule(
                    blast_schedule=self.blast_schedule,
                    as_of=self.as_of
                )

            elif tool_name == "project_time_to_threshold":
                args = ProjectThresholdArgs(**arguments)
                return project_time_to_threshold(
                    readings=self.readings,
                    as_of=self.as_of,
                    node_id=args.node_id,
                    channel=args.channel,
                    fit_minutes=args.fit_minutes,
                    threshold=args.threshold
                )

            else:
                return {
                    "error": f"Unknown tool '{tool_name}'",
                    "status": "failed",
                    "available_tools": [s["function"]["name"] for s in TOOL_SCHEMAS]
                }

        except ValidationError as e:
            return {
                "error": "Argument validation failed",
                "details": json.loads(e.json()),
                "status": "failed"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }

