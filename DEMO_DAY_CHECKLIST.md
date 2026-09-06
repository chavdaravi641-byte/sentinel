# Sentinel AI — Demo Day Checklist

Use this checklist on the presentation machine. Do not change application code on
demo day unless a defect blocks the demonstration.

## T-60 Minutes

- [ ] Laptop is charged and connected to power
- [ ] Mouse and charger are available
- [ ] Internet connection is verified
- [ ] Mobile hotspot is ready
- [ ] Presentation PDF is available offline
- [ ] Repository and documentation open locally
- [ ] Docker Desktop is running
- [ ] Backup machine is available, if one has been prepared

## Infrastructure

Verify that these services are healthy before rehearsal:

- [ ] PostgreSQL
- [ ] Redis
- [ ] MediaMTX
- [ ] FastAPI
- [ ] Next.js
- [ ] WebSocket connectivity
- [ ] API health endpoint

Run the repository's normal stack startup command, then confirm the health
endpoint and the service status before opening the browser.

## Camera and AI Pipeline

- [ ] Camera registration succeeds
- [ ] Camera status becomes online
- [ ] Stream opens
- [ ] Frames are received
- [ ] AI status is visible
- [ ] Plate detection is visible
- [ ] Watchlist match is visible
- [ ] Alert is generated
- [ ] GIS location updates
- [ ] Vehicle route is visible
- [ ] Incident can be created
- [ ] Evidence can be viewed or exported

Where a simulation or mock adapter is used, confirm that the UI's simulation
indicator is visible and explain it to the judges.

## Demo Assets

Keep these files locally and verify that each opens before leaving:

- [ ] Presentation deck
- [ ] Architecture document or PDF
- [ ] Sample evidence PDF
- [ ] Screenshots of key flows
- [ ] Validated sample RTSP/video source
- [ ] Database backup
- [ ] Working `.env` backup stored securely
- [ ] Release commit or tag, if created

Never place credentials or secrets in the presentation deck or repository.

## Emergency Recovery

| Failure | Recovery |
|---|---|
| Internet unavailable | Use the prepared mobile hotspot |
| RTSP source unavailable | Switch to the validated recorded sample |
| Live AI unavailable | Use the pre-validated scenario and disclose simulation |
| Browser issue | Switch to the prepared second browser |
| Docker service issue | Restart the Compose stack and recheck health |
| Laptop issue | Use the prepared backup machine |

Do not improvise an unverified production claim during recovery.

## Questions to Rehearse

Prepare concise answers for:

- Why use a hybrid architecture?
- Why FastAPI?
- Why PostgreSQL and PostGIS?
- Why Redis Pub/Sub?
- Why not Kafka in the MVP?
- How do vendor-neutral adapters work?
- How would VAHAN/CCTNS integration be implemented?
- How does the design scale toward 80,000 cameras?
- How are false positives handled?
- How is RBAC enforced?
- What happens when Redis fails?
- What happens when a camera goes offline?
- Why was this deployment architecture chosen?

## Final Verification

- [ ] `git status` is clean, if the release snapshot is intended to be final
- [ ] `master` is synchronized with the intended remote revision
- [ ] Release tag is created, if permanent freeze is authorized
- [ ] Full test suite reports `293 passed`
- [ ] Frontend build passes
- [ ] Backend health endpoint responds
- [ ] Docker stack is verified
- [ ] Demo flow has been rehearsed at least three times
- [ ] Backups are available
- [ ] Documentation is complete

## Rehearsal Sequence

Use the same sequence every time:

1. Login
2. Dashboard overview
3. Register a camera
4. Confirm online status
5. Open the live feed
6. Show vehicle detection
7. Show ANPR recognition
8. Show the watchlist hit
9. Show the critical alert
10. Show GIS highlighting
11. Show route reconstruction
12. Create the incident
13. View evidence or export the PDF
14. Explain the architecture
15. Explain the 80,000-camera roadmap
16. Take questions
