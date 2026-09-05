"""PostGIS + performance hardening for 80k scale

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-05

- PostGIS extension + geometry columns (camera_registry, cameras, anpr_plate_detections)
- GIST spatial indexes
- Composite indexes for hot paths (normalized_plate+ts, camera+ts, etc.)
- pg_trgm GIN for ILIKE searches
- BRIN for time partitions
- FK indexes + evidence_id FK
- JSONB GIN
- Audit log total bug is code-only (fixed in registry.py) — no migration needed
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Geometry columns — camera_registry
    op.execute("SELECT AddGeometryColumn('camera_registry', 'geom', 4326, 'POINT', 2)")
    op.execute("UPDATE camera_registry SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_camera_registry_geom_gist ON camera_registry USING GIST (geom)")

    # Cameras geometry functional index
    op.execute("CREATE INDEX IF NOT EXISTS ix_cameras_geom_gist ON cameras USING GIST (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) WHERE latitude IS NOT NULL AND longitude IS NOT NULL")

    # ANPR geometry
    op.execute("CREATE INDEX IF NOT EXISTS ix_anpr_plate_detections_geom_gist ON anpr_plate_detections USING GIST (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) WHERE latitude IS NOT NULL AND longitude IS NOT NULL")

    # Composite indexes — hot paths
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_anpr_plate_detections_norm_plate_ts_desc ON anpr_plate_detections (normalized_plate, ts DESC) INCLUDE (camera_id, plate)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_anpr_plate_detections_camera_ts_desc ON anpr_plate_detections (camera_id, ts DESC)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_detections_camera_class_ts ON detections (camera_id, class_name, ts DESC)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_inference_runs_camera_ts ON inference_runs (camera_id, ts DESC)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_anpr_alerts_camera_resolved_lastseen ON anpr_alerts (camera_id, resolved, last_seen_at DESC)")

    # pg_trgm GIN for ILIKE %...%
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS trgm_idx_anpr_make ON anpr_plate_detections USING GIN (make gin_trgm_ops)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS trgm_idx_anpr_camera_name ON anpr_plate_detections USING GIN (camera_name gin_trgm_ops)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS trgm_idx_watchlist_identifier ON watchlists USING GIN (identifier_number gin_trgm_ops)")

    # BRIN for time ranges (partitioning readiness)
    op.execute("CREATE INDEX IF NOT EXISTS ix_anpr_plate_detections_ts_brin ON anpr_plate_detections USING BRIN (ts)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_detections_ts_brin ON detections USING BRIN (ts)")

    # FK indexes + missing FK
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_recordings_stream_id ON recordings (stream_id)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_camera_registry_registered_by ON camera_registry (registered_by)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_camera_audit_log_actor_id ON camera_audit_log (actor_id)")
    # evidence_id FK (if not exists)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_anpr_plate_detections_evidence_id') THEN
                ALTER TABLE anpr_plate_detections ADD CONSTRAINT fk_anpr_plate_detections_evidence_id
                FOREIGN KEY (evidence_id) REFERENCES anpr_evidence(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # JSONB GIN
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS gin_camera_audit_log_before ON camera_audit_log USING GIN (before)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS gin_camera_audit_log_after ON camera_audit_log USING GIN (after)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS gin_security_events_detail ON security_events USING GIN (detail)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_camera_registry_geom_gist")
    op.execute("DROP INDEX IF EXISTS ix_cameras_geom_gist")
    op.execute("DROP INDEX IF EXISTS ix_anpr_plate_detections_geom_gist")
    op.execute("DROP INDEX IF EXISTS ix_anpr_plate_detections_norm_plate_ts_desc")
    op.execute("DROP INDEX IF EXISTS ix_anpr_plate_detections_camera_ts_desc")
    op.execute("DROP INDEX IF EXISTS ix_detections_camera_class_ts")
    op.execute("DROP INDEX IF EXISTS ix_inference_runs_camera_ts")
    op.execute("DROP INDEX IF EXISTS ix_anpr_alerts_camera_resolved_lastseen")
    op.execute("DROP INDEX IF EXISTS trgm_idx_anpr_make")
    op.execute("DROP INDEX IF EXISTS trgm_idx_anpr_camera_name")
    op.execute("DROP INDEX IF EXISTS trgm_idx_watchlist_identifier")
    op.execute("DROP INDEX IF EXISTS ix_anpr_plate_detections_ts_brin")
    op.execute("DROP INDEX IF EXISTS ix_detections_ts_brin")
    op.execute("DROP INDEX IF EXISTS ix_recordings_stream_id")
    op.execute("DROP INDEX IF EXISTS ix_camera_registry_registered_by")
    op.execute("DROP INDEX IF EXISTS ix_camera_audit_log_actor_id")
    op.execute("DROP INDEX IF EXISTS gin_camera_audit_log_before")
    op.execute("DROP INDEX IF EXISTS gin_camera_audit_log_after")
    op.execute("DROP INDEX IF EXISTS gin_security_events_detail")
    op.execute("SELECT DropGeometryColumn('camera_registry', 'geom')")
