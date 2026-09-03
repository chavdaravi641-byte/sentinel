"""Camera schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.camera import CameraStatus


class CameraBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    rtsp_url: str = Field(min_length=7, max_length=512)
    location: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp(cls, v: str) -> str:
        scheme = v.split("://", 1)[0].lower() if "://" in v else ""
        if scheme not in {"rtsp", "rtsps", "rtmp", "http", "https", "hls", "lavfi"}:
            raise ValueError(
                "RTSP URL must use rtsp/rtsps/rtmp/http(s)/lavfi scheme "
                "(e.g. rtsp://user:pass@host:554/stream)."
            )
        if "://" not in v or len(v.split("://", 1)[1]) < 3:
            raise ValueError("RTSP URL must include a valid host.")
        return v


class CameraCreate(CameraBase):
    status: CameraStatus = CameraStatus.UNKNOWN
    is_active: bool = True


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    rtsp_url: str | None = Field(default=None, min_length=7, max_length=512)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    description: str | None = Field(default=None, max_length=2000)
    status: CameraStatus | None = None
    is_active: bool | None = None


class CameraRead(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: CameraStatus
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CameraTestResult(BaseModel):
    id: UUID
    name: str
    ok: bool
    reachable: bool
    host: str | None = None
    port: int | None = None
    latency_ms: float | None = None
    rtt_ms: float | None = None
    message: str
    tested_at: datetime

    @staticmethod
    def from_url_probe(probe: dict) -> "CameraTestResult":
        return CameraTestResult.model_validate(probe)