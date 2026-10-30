from typing import Literal
from pydantic import BaseModel, Field


class NodeReading(BaseModel):
    node_id: str = Field(..., description="Unique node identifier, e.g. NODE_01")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    tilt_x: float = Field(..., description="Tilt along X axis in degrees")
    tilt_y: float = Field(..., description="Tilt along Y axis in degrees")
    vibration: float = Field(..., description="Peak vibration in g")
    distance: float = Field(..., description="Ultrasonic distance to target in cm")
    mpu6050_status: Literal["ok", "fault"] = Field("ok", description="Status of MPU-6050 IMU")
    hc_sr04_status: Literal["ok", "fault"] = Field("ok", description="Status of HC-SR04 ultrasonic sensor")
    ads1115_status: Literal["ok", "fault"] = Field("ok", description="Status of ADS1115 ADC")
    piezo_peak: float = Field(..., description="Piezo sensor peak voltage")
    piezo_rms: float = Field(..., description="Piezo sensor RMS voltage")
    piezo_peak_to_peak: float = Field(..., description="Piezo sensor peak-to-peak voltage")

