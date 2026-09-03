# Docker Root Cause Diagnosis — 2026-09-03 01:51 UTC

> No repair, reinstall, or Sentinel codebase modification performed. Evidence only.

## 1. Service Control — com.docker.service

### sc query (before start)
```
SERVICE_NAME: com.docker.service
        TYPE               : 10  WIN32_OWN_PROCESS
        STATE              : 1  STOPPED
        WIN32_EXIT_CODE    : 1077  (0x435)
        SERVICE_EXIT_CODE  : 0  (0x0)
        CHECKPOINT         : 0x0
        WAIT_HINT          : 0x0
```
- **WIN32_EXIT_CODE 1077**: `ERROR_SERVICE_NEVER_STARTED` — service has not been started since last boot. Not a crash; clean stopped state.
- **CHECKPOINT 0 / WAIT_HINT 0**: No pending start in progress.

### sc qc
```
SERVICE_NAME: com.docker.service
        TYPE               : 10  WIN32_OWN_PROCESS
        START_TYPE         : 3   DEMAND_START
        ERROR_CONTROL      : 1   NORMAL
        BINARY_PATH_NAME   : "C:\Program Files\Docker\Docker\com.docker.service"
        LOAD_ORDER_GROUP   :
        TAG                : 0
        DISPLAY_NAME       : Docker Desktop Service
        DEPENDENCIES       : LanmanServer
        SERVICE_START_NAME : LocalSystem
```
- Configuration is correct. Binary exists (36784 bytes). Runs as LocalSystem, depends on LanmanServer.

### sc start
```
[SC] StartService: OpenService FAILED 5:
Access is denied.
EXIT:5 (after Tool error handling)
```
- **Win32 error 5 = ERROR_ACCESS_DENIED**. Caller lacks `SC_MANAGER_CONNECT` / `SERVICE_START` privilege for `com.docker.service`. Requires elevated (Administrator) shell/UAC.
- **No service-specific exit code** — failure is at SCM OpenService, before service code runs.

### sc query (after start attempt)
- Identical to before: still STOPPED, 1077. No state change.

**Conclusion for service**: Service is correctly installed but cannot be started from current non-elevated context. This is a permission/UAC boundary, not corruption.

## 2. Windows Event Viewer (last 15 min)

- **System / Service Control Manager**: No entries for `com.docker.service`, `Docker Desktop`, `docker-desktop` in last 15 min. Only unrelated `BITS` start-type change `2026-09-03 01:51:11 ID 7040`.
- **Application / Docker provider**: No Docker entries in last 15 min.
- **Interpretation**: No crash, no SCM timeout, no dependency failure logged. Consistent with 1077 (never attempted) and Access Denied at OpenService (blocked before SCM logs start).

## 3. WSL Status

### wsl -l -v
```
  NAME                   STATE           VERSION
* docker-desktop         Stopped         2
```
- Only `docker-desktop` registered. **Missing** `docker-desktop-data` / `Ubuntu` (previously seen before `wsl --shutdown`).
- Stopped state is expected when Docker Desktop Service not running.

### wsl --status
```
Default Distribution: docker-desktop
Default Version: 2
```

### wsl --version
```
WSL version: 2.7.3.0
Kernel version: 6.6.114.1-1
WSLg version: 1.0.73
MSRDC version: 1.2.6676
Direct3D version: 1.611.1-81528511
DXCore version: 10.0.26100.1-240331-1435.ge-release
Windows version: 10.0.26200.9278
```

### WSL disk files (host)
```
C:\Users\PC\AppData\Local\Docker\wsl\disk\docker_data.vhdx  20613955584  2026-09-01 17:05:06
C:\Users\PC\AppData\Local\Docker\wsl\main\ext4.vhdx           109051904  2026-08-31 09:39:43
```
- VHDX files **exist** and are sizable. Docker Desktop 4.75 uses `wsl/disk` + `wsl/main` layout, not legacy `docker-desktop-data` distro name. So “missing distro” in `wsl -l -v` does **not** prove data corruption — registration is stale because service never started to import/attach them. Data likely recoverable on next elevated start.

## 4. Docker Desktop Installation

- `C:\Program Files\Docker\Docker\Docker Desktop.exe` — **exists**, 13207984 bytes, FileVersion 4.75.0.227598
- `C:\Program Files\Docker\Docker\com.docker.service` — **exists**, 36784 bytes
- `com.docker.service` SCM entry points to correct binary.
- Installation path and binaries intact — **no corruption**.

### Docker client
```
Client Version 29.5.2 / API 1.54 / Go 1.26.3 / OS windows/amd64 / Context desktop-linux
```

### Docker daemon
```
docker version (server): failed to connect to npipe:////./pipe/dockerDesktopLinuxEngine — file not found
docker info (server): same npipe failure
docker context ls: desktop-linux * -> npipe:////./pipe/dockerDesktopLinuxEngine (error)
```
- Client works; daemon npipe absent because service/WSL not running.

### Windows build
- `Microsoft Windows 11 Home Single Language Build 26200` — supported.
- Hyper-V hypervisor detected (systeminfo: “A hypervisor has been detected”). `Get-WindowsOptionalFeature` requires elevation (failed with COMException), **NOT MEASURED** for feature state.
- WSL 2.7.3 present and previously ran both distros as Running — virtualization is functional.

## 5. Sentinel Impact

- No Sentinel source modified.
- No containers rebuilt.
- No volumes removed.
- Alembic / compose not executed (blocked on Docker engine).

## 6. Classification

**Primary root cause: A. Service permission/UAC failure**

Evidence:
- `sc start` → `OpenService FAILED 5: Access is denied.` (Win32 error 5) from non-elevated shell.
- SCM never attempted start (1077), so no crash/corruption signal.
- Event log clean — no Docker/SCM errors.

**Secondary observation: C. WSL registration failure (stale)**

Evidence:
- `wsl -l -v` shows only `docker-desktop Stopped`; previously showed `docker-desktop Running`, `docker-desktop-data Running`, `Ubuntu Running`.
- After `wsl --shutdown`, distros did not auto-restart without service.
- VHDX files still present (20 GB + 109 MB), so data not lost; registration will be restored when `com.docker.service` starts elevated and Docker Desktop re-imports WSL distros.

**Not primary:**
- B (data corrupted) — FAIL: VHDX exist, sizes plausible.
- D (installation corruption) — FAIL: binaries present, versions consistent, SCM config correct.
- E (virtualization) — NOT MEASURED for feature flags (needs elevation), but WSL 2.7.3 kernel 6.6 and prior Running distros prove it was working; recent `systeminfo` shows hypervisor present.
- F (unknown) — rejected; evidence sufficient for A.

## 7. Checks Summary

| Check | Result |
|-------|--------|
| sc query com.docker.service | **FAIL** — STOPPED 1077, never started |
| sc qc com.docker.service | **PASS** — config correct |
| sc start com.docker.service | **FAIL** — Access is denied (5), needs elevation |
| Event Viewer SCM/Docker (15 min) | **PASS** — no errors (clean) |
| wsl -l -v docker-desktop | **FAIL** — Stopped |
| wsl -l -v docker-desktop-data | **FAIL** — not listed (but VHDX exists) |
| wsl --status | **PASS** — default docker-desktop v2 |
| wsl --version | **PASS** — 2.7.3.0 |
| Docker Desktop exe exists | **PASS** — 4.75.0.227598 |
| com.docker.service exe exists | **PASS** — 36784 bytes |
| docker version client | **PASS** — 29.5.2 |
| docker version server | **FAIL** — npipe not found (daemon down) |
| docker context ls | **PASS** — lists desktop-linux (error expected) |
| docker info server | **FAIL** — daemon down |
| VHDX files on disk | **PASS** — both present |
| Hyper-V / VMP feature state | **NOT MEASURED** — requires elevation |
| Sentinel modification | **PASS** — none |

## 8. Recovery Note (no action taken)

- `com.docker.service` will start only from **elevated** PowerShell/CMD (`Run as Administrator`) → `sc start com.docker.service` or launching Docker Desktop elevated.
- On successful start, Docker Desktop should re-register/attach WSL distros (`docker-desktop`, `docker-desktop-data`/`disk`/`main`) and recreate `\\.\pipe\dockerDesktopLinuxEngine`. If `wsl -l -v` still shows single distro after elevated start, Repair (Docker Desktop Installer → Repair) may be needed, but data loss unlikely due to intact VHDX.

**Overall diagnosis: FAIL — Docker engine down due to UAC-blocked service start; host virtualization and installation intact.**

---
*Generated without modifying Sentinel codebase or rebuilding containers.*
