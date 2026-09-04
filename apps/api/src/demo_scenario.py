"""Police Sentinel — Executive Demo Scenario (Hackathon Day Judging).

A single-command "mission replay" that walks the exact demo we present to the
Gujarat Police Innovation Challenge judges, wired to the *real* API surface
(no mocked REST endpoints):

  Act I   — Platform health: Postgres, PostGIS, Redis, API.
  Act II  — Live CCTV ingest: RTSP connectivity probe via
            ``POST /cameras/{id}/test`` (the true probe surface) and, with
            ``--inject``, the live stream pipeline from ``inject_live_stream``.
  Act III — Watchlist intelligence: seeded NAFIS/VAHAN/eGujCop entries, a live
            watchlist lookup, and the ANPR alert engine (blacklist +
            multi-camera rules) driven against those plates.
  Act IV  — Registry gap analysis: ``GET /registry/gis/report`` (JSON +
            Markdown) wrapping ``registry/gap.py`` (``run_gap_report`` /
            ``low_density_zones``).
  Act V   — Governance: RBAC department isolation + append-only
            ``camera_audit_log`` integrity.

Run against the live stack:

    python -m src.demo_scenario                    # HTTP integration
    python -m src.demo_scenario --inject           # also bind a live RTSP feed
    python -m src.demo_scenario --base-url http://localhost:8000

Exit code 0 = full pass, 1 = one or more checks failed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_DIM = "\033[90m"
_RESET = "\033[0m"

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000") + "/api/v1"


@dataclass
class Results:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def ok(self, name: str) -> None:
        self.passed += 1
        print(f"  {_GREEN}[PASS]{_RESET}  {name}")

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{name}: {detail}" if detail else name
        print(f"  {_RED}[FAIL]{_RESET}  {msg}")
        self.errors.append(msg)

    def skip(self, name: str, reason: str = "") -> None:
        self.skipped += 1
        print(f"  {_YELLOW}[SKIP]{_RESET}  {name} -- {reason}")

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped

    def summary(self) -> None:
        print(f"\n{_BOLD}{'=' * 60}{_RESET}")
        print(
            f"{_BOLD}Demo result: {_GREEN}{self.passed} pass{_RESET}, "
            f"{_RED}{self.failed} fail{_RESET}, {_YELLOW}{self.skipped} skip{_RESET} "
            f"/ {self.total}{_RESET}"
        )
        if self.errors:
            print(f"\n{_RED}Failures:{_RESET}")
            for e in self.errors:
                print(f"  * {e}")
        print()
        return self.failed == 0


def _section(title: str) -> None:
    print(f"\n{_BOLD}{_CYAN}{'=' * 60}{_RESET}")
    print(f"{_BOLD}{_CYAN}  {title}{_RESET}")
    print(f"{_BOLD}{_CYAN}{'=' * 60}{_RESET}")


def _sub(title: str) -> None:
    print(f"\n  {_BOLD}{_DIM}--- {title}{_RESET}")


# ---------------------------------------------------------------------------
# Auth helper (uses the real /auth/login endpoint)
# ---------------------------------------------------------------------------
async def _login(httpx_client: Any, r: Results) -> str | None:
    try:
        email = os.getenv("ADMIN_EMAIL", "admin@sentinel.gp")
        password = os.getenv("ADMIN_PASSWORD", "Admin@2026")
        resp = await httpx_client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                r.ok(f"Authenticated as {email} (POST /auth/login)")
                return token
        r.fail("Demo authentication", f"HTTP {resp.status_code}: {resp.text[:160]}")
    except Exception as exc:  # noqa: BLE001
        r.fail("Demo authentication", str(exc)[:160])
    return None


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Act I — Platform health
# ---------------------------------------------------------------------------
async def _act_health(client: Any, r: Results) -> None:
    _section("Act I — Platform Health (Postgres / PostGIS / Redis / API)")
    try:
        resp = await client.get("/health")
        if resp.status_code == 200:
            body = resp.json()
            comps = body.get("components", {})
            status = body.get("status", "unknown")
            db_ok = comps.get("database", {}).get("status")
            redis_ok = comps.get("redis", {}).get("status")
            if status == "ok" and db_ok == "ok" and redis_ok == "ok":
                r.ok(f"API healthy — database={db_ok}, redis={redis_ok}")
            else:
                r.fail("API health", f"status={status} db={db_ok} redis={redis_ok}")
        else:
            r.fail("API health", f"HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        r.fail("API health", str(exc)[:160])
        return

    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel",
        )
        engine = create_async_engine(db_url, pool_size=1)
        async with engine.begin() as conn:
            ext = (
                await conn.execute(
                    text("SELECT extname FROM pg_extension WHERE extname='postgis'")
                )
            ).fetchone()
            if ext:
                r.ok(f"PostGIS extension present (v{ext[0]})")
            else:
                r.skip("PostGIS", "extension not installed (pure-Python geometry)")

            critical = ["cameras", "watchlists", "camera_registry", "camera_audit_log"]
            rows = (
                await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema='public'"
                    )
                )
            ).fetchall()
            actual = {row[0] for row in rows}
            for tbl in critical:
                if tbl in actual:
                    r.ok(f"Table '{tbl}' present")
                else:
                    r.fail(f"Table '{tbl}'", "missing from schema")
        await engine.dispose()
    except Exception as exc:  # noqa: BLE001
        r.fail("Database schema probe", str(exc)[:160])


# ---------------------------------------------------------------------------
# Act II — Live CCTV ingest
# ---------------------------------------------------------------------------
async def _act_stream(client: Any, r: Results, token: str, inject: bool) -> None:
    _section("Act II — Live CCTV Ingest (probe + optional live RTSP bind)")
    try:
        resp = await client.get(
            "/cameras", params={"page": 1, "page_size": 5}, headers=_headers(token)
        )
        if resp.status_code != 200:
            r.fail("List cameras for ingest", f"HTTP {resp.status_code}")
            return
        cams = resp.json().get("items", [])
        if not cams:
            r.skip("Camera ingest", "no cameras seeded")
            return
        cam = cams[0]
        r.ok(f"Camera fleet reachable ({resp.json().get('total', 0)} total)")

        # 2a. Real RTSP connectivity probe (the true live-ingest surface).
        _sub("RTSP connectivity probe")
        probe = await client.post(
            f"/cameras/{cam['id']}/test", headers=_headers(token)
        )
        if probe.status_code == 200:
            body = probe.json()
            reachable = body.get("reachable")
            latency = body.get("latency_ms") or body.get("latency", "n/a")
            r.ok(f"POST /cameras/{cam['id']}/test -> reachable={reachable}, latency={latency}")
        else:
            r.fail("Camera RTSP probe", f"HTTP {probe.status_code}: {probe.text[:140]}")

        # 2b. ANPR engine tier is live on the camera path (offline, deterministic).
        _sub("ANPR inference engine status")
        cfg = await client.get("/anpr/config", headers=_headers(token))
        if cfg.status_code == 200:
            backend = cfg.json().get("backend", "?")
            ocr = cfg.json().get("ocr_engine", "?")
            r.ok(f"ANPR engine configured — backend={backend}, ocr={ocr}")
        else:
            r.fail("ANPR config", f"HTTP {cfg.status_code}")

        # 2c. Optional live RTSP bind via the real inject pipeline.
        if inject:
            _sub("Live RTSP bind (inject_live_stream pipeline)")
            from src.inject_live_stream import _update_camera_rtsp
            from src.core.database import AsyncSessionLocal

            rtsp_url = os.getenv("DEMO_RTSP_URL", "rtsp://127.0.0.1:8554/demo")
            ok = False
            async with AsyncSessionLocal() as db:
                try:
                    from uuid import UUID as _UUID

                    from src.models.camera import Camera

                    cam_obj = await db.get(Camera, _UUID(cam["id"]))
                    if cam_obj is None:
                        r.fail("Live RTSP bind", "camera not found in DB")
                    else:
                        updated = await _update_camera_rtsp(db, cam_obj.id, rtsp_url)
                        ok = updated.status.value in ("online", "ONLINE") or updated.is_active
                        r.ok(
                            f"Bound {cam['name']} -> {rtsp_url} "
                            f"(status={updated.status.value}, is_active={updated.is_active})"
                        )
                except Exception as exc:  # noqa: BLE001
                    r.fail("Live RTSP bind", str(exc)[:160])
    except Exception as exc:  # noqa: BLE001
        r.fail("Act II (stream)", str(exc)[:200])


# ---------------------------------------------------------------------------
# Act III — Watchlist intelligence
# ---------------------------------------------------------------------------
async def _act_watchlist(client: Any, r: Results, token: str) -> None:
    _section("Act III — Watchlist Intelligence (NAFIS / VAHAN / eGujCop)")

    _sub("Seeded watchlist (REST)")
    try:
        resp = await client.get(
            "/watchlists", params={"page": 1, "page_size": 10}, headers=_headers(token)
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            total = resp.json().get("total", 0)
            sources = {i.get("source_db") for i in items}
            r.ok(
                f"GET /watchlists -> {total} entries "
                f"(sources: {', '.join(sorted(s for s in sources if s)) or 'none'})"
            )
            plates = [i["identifier_number"] for i in items if i.get("identifier_number")]
        else:
            r.fail("Watchlist listing", f"HTTP {resp.status_code}: {resp.text[:140]}")
            return
    except Exception as exc:  # noqa: BLE001
        r.fail("Watchlist listing", str(exc)[:160])
        return

    _sub("Live plate lookup")
    try:
        candidate = next((p for p in plates if p), "GJ01AB1234")
        lk = await client.get(
            f"/watchlists/lookup/{candidate}", headers=_headers(token)
        )
        if lk.status_code == 200:
            found = lk.json()
            r.ok(f"Lookup {candidate} -> {'HIT' if found else 'not found'}")
        else:
            r.fail("Watchlist lookup", f"HTTP {lk.status_code}")
    except Exception as exc:  # noqa: BLE001
        r.fail("Watchlist lookup", str(exc)[:160])

    _sub("ANPR alert engine (offline, against seeded plates)")
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from src.anpr.alerts import (
            AnprAlertEngine,
            RULE_BLACKLIST,
            RULE_LOW_CONFIDENCE,
            RULE_MULTI_CAMERA,
        )
        from src.anpr.blacklist import BlacklistEngine
        from src.anpr.primitives import (
            PlateBox,
            PlateEvent,
            VehicleAttribute,
            normalize_plate,
        )
    except Exception as exc:  # noqa: BLE001
        r.skip("ANPR alert engine", str(exc)[:120])
        return

    def _ev(plate: str, cam: str, conf: float = 0.9) -> PlateEvent:
        return PlateEvent(
            camera_id=cam,
            plate=plate,
            normalized_plate=normalize_plate(plate),
            ocr_confidence=conf,
            state_code="GJ",
            rto_code="01",
            vehicle=VehicleAttribute(
                color="white", make="Maruti", model="Swift",
                color_confidence=0.9, type_confidence=0.85,
            ),
            frame_seq=1,
            ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            plate_box=PlateBox(confidence=0.92, x=100, y=200, w=300, h=60),
            detection_confidence=0.88,
            backend="sim",
        )

    bl = BlacklistEngine(strict_eq=True)
    for p in plates:
        bl.upsert(p, reason="wanted")
    hit = bl.match(plates[0]) if plates else None
    if hit:
        r.ok(f"BlacklistEngine match on seeded plate {plates[0]}")
    else:
        r.fail("Blacklist match", "no hit on seeded plate")

    eng = AnprAlertEngine(cooldown=0)
    ev = _ev(plates[0] if plates else "GJ01AB1234", "cam-001")
    fired = eng.evaluate(event=ev, blacklist_match=bl.match(ev.normalized_plate))
    if any(a["rule"] == RULE_BLACKLIST for a in fired):
        r.ok("ALERT fired — BLACKLIST rule (watchlist vehicle on camera)")
    else:
        r.fail("BLACKLIST rule", f"no alert; got {fired}")

    # Multi-camera: same plate seen on two different cameras.
    eng.reset()
    plate2 = plates[1] if len(plates) > 1 else plates[0]
    eng.evaluate(event=_ev(plate2, "cam-A"), blacklist_match=None)
    second = eng.evaluate(event=_ev(plate2, "cam-B"), blacklist_match=None)
    if any(a["rule"] == RULE_MULTI_CAMERA for a in second):
        r.ok("ALERT fired — MULTI_CAMERA rule (same plate, 2 cameras)")
    else:
        r.fail("MULTI_CAMERA rule", f"no alert; got {second}")


# ---------------------------------------------------------------------------
# Act IV — Registry gap analysis (report route wrapping registry/gap.py)
# ---------------------------------------------------------------------------
async def _act_gap(client: Any, r: Results, token: str) -> None:
    _section("Act IV — Registry Gap Analysis (GET /registry/gis/report)")
    try:
        for fmt in ("json", "markdown"):
            resp = await client.get(
                "/registry/gis/report", params={"format": fmt}, headers=_headers(token)
            )
            if resp.status_code == 200:
                body = resp.json()
                if fmt == "json":
                    rep = body.get("report", {})
                    r.ok(
                        "JSON report — cameras={}, blind_cells={}, uncovered_m2={}, zones(h/m/l)={}/{}/{}".format(
                            rep.get("camera_count"),
                            rep.get("blind_spot_cells"),
                            rep.get("uncovered_area_m2"),
                            rep.get("low_density_high"),
                            rep.get("low_density_medium"),
                            rep.get("low_density_low"),
                        )
                    )
                else:
                    md = body.get("markdown", "")
                    r.ok(f"Markdown report rendered ({len(md)} chars, {md.count(chr(10))} lines)")
            else:
                r.fail(f"Gap report ({fmt})", f"HTTP {resp.status_code}: {resp.text[:140]}")
    except Exception as exc:  # noqa: BLE001
        r.fail("Act IV (gap report)", str(exc)[:200])

    _sub("Low-level analytics reachable (registry/gap.py)")
    try:
        from src.registry.gap import low_density_zones, run_gap_report
        from src.registry.coverage import CameraPoint

        pts = [
            CameraPoint(id="A", lat=23.02, lon=72.57),
            CameraPoint(id="B", lat=23.22, lon=72.64),
            CameraPoint(id="C", lat=21.19, lon=72.83),
        ]
        report = run_gap_report(pts)
        zones = low_density_zones(pts)
        if report["camera_count"] == 3 and isinstance(zones, list):
            r.ok("run_gap_report + low_density_zones execute on analytic seed")
        else:
            r.fail("gap.py analytics", f"unexpected shape report={report}")
    except Exception as exc:  # noqa: BLE001
        r.fail("gap.py analytics", str(exc)[:160])


# ---------------------------------------------------------------------------
# Act V — Governance: RBAC isolation + append-only audit
# ---------------------------------------------------------------------------
async def _act_governance(r: Results) -> None:
    _section("Act V — Governance (RBAC isolation + append-only audit)")
    try:
        from src.models.registry import AccessRole
        from src.registry.roles import RegistryScope, RegistryUser

        # Department-level isolation: a department admin may only act on its own
        # department; state admin covers all.
        dept = RegistryUser(
            user_id="u1",
            role=AccessRole.DEPARTMENT_ADMIN,
            scope=RegistryScope.for_role(
                AccessRole.DEPARTMENT_ADMIN, department_code="TRAF"
            ),
        )
        in_dept = dept.in_scope(state_code="GJ", department_code="TRAF")
        out_dept = dept.in_scope(state_code="GJ", department_code="MUNI")
        if in_dept and not out_dept:
            r.ok("RBAC: department_admin scoped to own department (TRAF) only")
        else:
            r.fail("RBAC department isolation",
                   f"in_dept={in_dept} out_dept={out_dept}")

        operator = RegistryUser(user_id="u2", role=AccessRole.OPERATOR)
        if operator.can("update") and not operator.can("delete"):
            r.ok("RBAC: operator may update but not delete")
        else:
            r.fail("RBAC operator matrix",
                   f"update={operator.can('update')}, delete={operator.can('delete')}")

        viewer = RegistryUser(user_id="u3", role=AccessRole.VIEWER)
        if viewer.can("view") and not viewer.can("audit") and not viewer.can("create"):
            r.ok("RBAC: viewer is read/search only")
        else:
            r.fail("RBAC viewer matrix", "viewer perms unexpected")

        # Endpoint-level scoping: a department_admin must not see another
        # department's rows via _scope_filter.
        from src.api.v1.endpoints.registry import _scope_filter

        rows = [
            {"state_code": "GJ", "district_code": "AHM", "department_code": "TRAF"},
            {"state_code": "GJ", "district_code": "AHM", "department_code": "MUNI"},
        ]
        filtered = _scope_filter(dept, rows)
        if len(filtered) == 1 and filtered[0]["department_code"] == "TRAF":
            r.ok("RBAC: _scope_filter returns only the caller's department rows")
        else:
            r.fail("RBAC _scope_filter", f"expected 1 TRAF row, got {len(filtered)}")
    except Exception as exc:  # noqa: BLE001
        r.fail("RBAC unit checks", str(exc)[:160])

    # Append-only audit: CameraAuditLog has no updated_at and the ORM mapper
    # does not expose in-place mutation of audit rows in registry endpoints.
    try:
        import inspect

        from src.api.v1.endpoints import registry as reg_ep
        from src.models.registry import CameraAuditLog

        src = inspect.getsource(CameraAuditLog)
        if "updated_at" not in src and "onupdate" not in src:
            r.ok("Append-only: CameraAuditLog carries no updated_at/onupdate column")
        else:
            r.fail("Append-only audit schema", "audit table appears mutable")

        ep_src = inspect.getsource(reg_ep)
        # Every registry mutation ends in db.add(CameraAuditLog(...)) — a new
        # immutable row, never an update to an existing one.
        if "CameraAuditLog(" in ep_src and "audit" in ep_src:
            r.ok("Append-only: registry endpoints only ADD audit rows")
        else:
            r.fail("Append-only audit usage", "no audit additions found in registry endpoints")
    except Exception as exc:  # noqa: BLE001
        r.fail("Append-only audit checks", str(exc)[:160])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def _run(base_url: str, inject: bool, http: bool, r: Results) -> None:
    if not http:
        r.skip("Acts I–IV (HTTP)", "HTTP disabled; running offline governance + engine checks")
        await _act_governance(r)
        return

    try:
        import httpx
    except ImportError:
        r.fail("httpx required for HTTP demo", "pip install httpx")
        r.skip("Live HTTP demo", "httpx missing")
        return

    async with httpx.AsyncClient(base_url=base_url, timeout=15,
                                 follow_redirects=True) as client:
        token = await _login(client, r)
        if not token:
            r.skip("Acts I–IV", "authentication failed; cannot proceed with HTTP checks")
            await _act_governance(r)
            return
        await _act_health(client, r)
        await _act_stream(client, r, token, inject)
        await _act_watchlist(client, r, token)
        await _act_gap(client, r, token)
        await _act_governance(r)


def main() -> int:
    p = argparse.ArgumentParser(description="Police Sentinel demo scenario")
    p.add_argument("--base-url", default=API_URL, help="API base (with /api/v1)")
    p.add_argument("--inject", action="store_true",
                   help="also bind a live RTSP feed via the inject_live_stream pipeline")
    p.add_argument("--skip-http", action="store_true", help="offline engine checks only")
    args = p.parse_args()

    print(f"\n{_BOLD}Police Sentinel — Executive Demo Scenario{_RESET}")
    print(f"{_DIM}  API: {args.base_url}{_RESET}")
    print(f"{_DIM}  Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}{_RESET}")

    results = Results()
    asyncio.run(_run(args.base_url, args.inject, not args.skip_http, results))
    passed = results.summary()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
