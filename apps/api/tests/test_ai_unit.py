"""Phase 3 AI inference engine unit tests (no DB, no network).

Covers core primitives, YOLO decode helpers, the deterministic sim backend,
IoU tracking, the event bus, storage-queue mechanics, the alert engine, the GPU
scheduler and the benchmark harness.
"""

import time

import numpy as np
import pytest
from src.inference.alerts import AlertEngine
from src.inference.events import EventBus
from src.inference.gpu import GpuScheduler
from src.inference.loader import ModelLoader
from src.inference.plugin import decode_yolo, letterbox, nms
from src.inference.primitives import BoxResult, DeviceInfo, InferItem, Timings
from src.inference.storage import DetectionStore
from src.inference.tracking import IoUTracker
from src.inference.yolov12 import SENTINEL_CLASSES, YoloV12Plugin


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #
def test_box_result_geometry():
    box = BoxResult(class_name="person", confidence=0.9, x=0.1, y=0.2, w=0.4, h=0.3)
    assert box.cx == pytest.approx(0.3)
    assert box.cy == pytest.approx(0.35)
    assert box.area == pytest.approx(0.12)

    other = BoxResult(class_name="person", confidence=0.8, x=0.15, y=0.25, w=0.3, h=0.2)
    assert box.iou(other) > 0.0
    assert box.iou(other) <= 1.0
    disjoint = BoxResult(class_name="person", confidence=0.5, x=0.8, y=0.8, w=0.1, h=0.1)
    assert box.iou(disjoint) == 0.0

    d = box.to_dict()
    assert d["x"] == 0.1 and set(d) >= {"class_name", "confidence", "x", "y", "w", "h", "cx", "cy"}


def test_timings_total_and_device_info():
    t = Timings(pre_ms=1.0, infer_ms=2.0, post_ms=0.5)
    assert t.total_ms == pytest.approx(3.5)
    dev = DeviceInfo(accelerator="cpu", device_name="cpu (onnxruntime)", providers=["CPUExecutionProvider"])
    assert dev.to_dict()["providers"] == ["CPUExecutionProvider"]


# --------------------------------------------------------------------------- #
# Decode / NMS / letterbox
# --------------------------------------------------------------------------- #
def test_decode_yolo_class_filter_and_conf():
    nc = 12  # any nc; we map ids via class_map
    num = 40
    output = np.zeros((1, 4 + nc, num), dtype=np.float32)
    for i in range(num):
        output[0, 0, i] = i * 0.01 + 0.1  # x (0..0.5)
        output[0, 1, i] = i * 0.01 + 0.1  # y
        output[0, 2, i] = 0.05  # w
        output[0, 3, i] = 0.05  # h
        cls_id = (i * 3) % nc  # cycles through ids incl. disallowed ones
        output[0, 4 + cls_id, i] = 0.2 + (i % 5) * 0.15  # conf 0.2..0.8

    class_map = {0: "person", 2: "car", 5: "bus", 12: "fire"}  # 12 intentionally missing
    boxes = decode_yolo(
        output,
        class_map={k: v for k, v in class_map.items() if v in SENTINEL_CLASSES},
        conf_threshold=0.4,
        input_size=(640, 640),
    )
    assert boxes, "expected some detections above 0.4"
    for b in boxes:
        assert b.class_name in SENTINEL_CLASSES
        assert 0.0 <= b.confidence <= 1.0
        assert 0.0 <= b.x <= 1.0 and 0.0 <= b.y <= 1.0


def test_nms_dedupe_same_class_and_keep_distinct():
    base = BoxResult(class_name="person", confidence=0.9, x=0.1, y=0.1, w=0.3, h=0.3)
    dup = BoxResult(class_name="person", confidence=0.85, x=0.12, y=0.12, w=0.28, h=0.28)
    far = BoxResult(class_name="person", confidence=0.6, x=0.6, y=0.6, w=0.2, h=0.2)
    car = BoxResult(class_name="car", confidence=0.7, x=0.1, y=0.1, w=0.3, h=0.3)
    kept = nms([far, dup, base, car], iou_threshold=0.45)
    # car is a different class so it survives even though overlapping base.
    assert len(kept) == 3
    assert all(b.class_name in ("person", "car") for b in kept)
    assert max(b.confidence for b in kept if b.class_name == "person") == 0.9


def test_letterbox_keeps_aspect_and_fills():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    canvas, scale, pad_x, pad_y = letterbox(image, (640, 640))
    assert canvas.shape == (640, 640, 3)
    assert scale == pytest.approx(1.0)
    assert pad_x == 0.0 and pad_y == 80.0  # h 480 -> 80px top/bottom gray fill

    tall = np.zeros((900, 450, 3), dtype=np.uint8)
    canvas2, scale2, pad_x2, pad_y2 = letterbox(tall, (640, 640))
    assert canvas2.shape == (640, 640, 3)
    assert scale2 < 1.0
    assert pad_x2 > 0.0 and pad_y2 == 0.0


# --------------------------------------------------------------------------- #
# Deterministic sim backend
# --------------------------------------------------------------------------- #
def test_sim_deterministic_same_input_same_output():
    p1 = YoloV12Plugin(ModelLoader("/tmp/does-not-exist-weights", "cpu"), DeviceInfo(), 0.4)
    items = [InferItem(image=np.zeros((720, 1280, 3), dtype=np.uint8), ctx={"seed": 42, "frame_seq": 10})]
    r1, _ = p1.infer_batch(items)
    r2, _ = p1.infer_batch(items)
    assert [(b.class_name, b.x, b.y, b.confidence) for b in r1[0]] == [
        (b.class_name, b.x, b.y, b.confidence) for b in r2[0]
    ]


def test_sim_deterministic_different_seed_differs():
    p1 = YoloV12Plugin(ModelLoader("/tmp/does-not-exist-weights", "cpu"), DeviceInfo(), 0.4)
    a, _ = p1.infer_batch([InferItem(image=np.zeros((720, 1280, 3), dtype=np.uint8), ctx={"seed": 1, "frame_seq": 5})])
    b, _ = p1.infer_batch([InferItem(image=np.zeros((720, 1280, 3), dtype=np.uint8), ctx={"seed": 99, "frame_seq": 5})])
    assert a[0] != b[0]


def test_sim_class_and_bounds():
    plugin = YoloV12Plugin(ModelLoader("/tmp/does-not-exist-weights", "cpu"), DeviceInfo(), 0.4)
    results, _ = plugin.infer_batch(
        [
            InferItem(
                image=np.zeros((720, 1280, 3), dtype=np.uint8),
                ctx={"seed": 7, "frame_seq": 12345},
            )
        ]
    )
    boxes = results[0]
    assert 2 <= len(boxes) <= 4
    for b in boxes:
        assert b.class_name in SENTINEL_CLASSES
        assert 0.4 <= b.confidence <= 0.96
        assert 0.0 <= b.x <= 1.0 and 0.0 <= b.y <= 1.0
        assert 0.0 < b.w <= 1.0 and 0.0 < b.h <= 1.0
        assert b.x + b.w <= 1.0 and b.y + b.h <= 1.0


# --------------------------------------------------------------------------- #
# IoU tracker
# --------------------------------------------------------------------------- #
def test_tracker_assigns_stable_ids_and_expires():
    tracker = IoUTracker(max_age=0.5)
    box = BoxResult(class_name="person", confidence=0.9, x=0.1, y=0.1, w=0.3, h=0.3)
    now = time.monotonic()
    t1 = tracker.update([box], now)
    assert len(t1) == 1
    tid1 = t1[0][0]
    # same box at same position -> same id
    t2 = tracker.update([box], now + 0.05)
    assert t2[0][0] == tid1
    # after max_age with no match, a new id is minted
    t3 = tracker.update([box], now + 5.0)
    assert t3[0][0] != tid1

    tracker.reset()
    assert tracker.update([box], now + 10.0)[0][0] != t3[0][0]


def test_tracker_class_consistent():
    tracker = IoUTracker(max_age=1.0)
    now = time.monotonic()
    person = BoxResult(class_name="person", confidence=0.9, x=0.1, y=0.1, w=0.3, h=0.3)
    car = BoxResult(class_name="car", confidence=0.9, x=0.11, y=0.11, w=0.3, h=0.3)
    t1 = tracker.update([person], now)
    person_tid = t1[0][0]
    t2 = tracker.update([car], now + 0.1)
    # Overlapping box of a different class must not steal the person's id.
    assert t2[0][0] != person_tid


# --------------------------------------------------------------------------- #
# Event bus
# --------------------------------------------------------------------------- #
async def test_event_bus_publish_and_unsubscribe():
    bus = EventBus()
    q = bus.subscribe("overlay")
    await bus.publish("overlay", {"type": "overlay", "camera_id": "c1"})
    assert (await q.get())["camera_id"] == "c1"
    bus.unsubscribe("overlay", q)
    await bus.publish("overlay", {"type": "overlay"})
    assert q.empty()


async def test_event_bus_drops_oldest_on_overflow():
    bus = EventBus()
    q = bus.subscribe("stats", maxsize=3)
    for i in range(5):
        await bus.publish("stats", {"i": i})
    # The three newest entries survive; the two oldest were dropped.
    got = []
    while not q.empty():
        got.append((await q.get())["i"])
    assert got == [2, 3, 4]


async def test_event_bus_subscribe_many():
    bus = EventBus()
    channels, queues = await bus.subscribe_many(["overlay", "alert"])
    assert channels == ["overlay", "alert"]
    await bus.publish("alert", {"type": "alert"})
    assert (await queues[1].get())["type"] == "alert"


# --------------------------------------------------------------------------- #
# Storage queue mechanics (no DB)
# --------------------------------------------------------------------------- #
def test_storage_disabled_swallows_submits():
    store = DetectionStore(enabled=False)
    store.submit_runs([{"camera_id": "x"}], [])
    store.submit_alert({"id": "y"})
    assert store._queue.empty()


def test_storage_submits_queue_items():
    store = DetectionStore(enabled=True)
    store.submit_runs([{"kind": "run"}], [{"kind": "det"}])
    store.submit_alert({"kind": "alert"})
    store.submit_model({"kind": "model", "name": "yolov12"})
    kinds = [store._queue.get_nowait()["kind"] for _ in range(3)]
    assert kinds == ["runs", "alert", "model"]


# --------------------------------------------------------------------------- #
# Alert engine
# --------------------------------------------------------------------------- #
def _box(cls: str, x: float = 0.1, y: float = 0.1) -> BoxResult:
    return BoxResult(class_name=cls, confidence=0.9, x=x, y=y, w=0.2, h=0.4)


def test_alert_persistence_threshold():
    engine = AlertEngine(enabled=True, persistence=3, crowd_persons=5, traffic_vehicles=6, cooldown=10.0)
    cam = "camera-1"
    tracked = [(10, _box("person"), 3)]
    counts = {"person": 1}
    assert engine.evaluate(camera_id=cam, model_name="yolov12", tracked=[], counts=counts) == []
    fired = []
    for _ in range(4):
        result = engine.evaluate(camera_id=cam, model_name="yolov12", tracked=tracked, counts=counts)
        if result:
            fired = result
            break  # cooldown coalesces the repeats; the first fire is what matters
    assert fired, "expected alert after persistence window"
    assert fired[0]["class_name"] == "person"
    assert fired[0]["count"] == 1


def test_alert_crowd_and_traffic_rules():
    engine = AlertEngine(enabled=True, persistence=1, crowd_persons=5, traffic_vehicles=6, cooldown=10.0)
    cam = "camera-2"
    crowd_counts = {"person": 6}
    fires = engine.evaluate(camera_id=cam, model_name="yolov12", tracked=[], counts=crowd_counts)
    assert any(f["rule"] == "crowd" and f["class_name"] == "person" for f in fires)

    traffic_counts = {"car": 4, "bus": 1, "truck": 2}
    fires = engine.evaluate(camera_id=cam, model_name="yolov12", tracked=[], counts=traffic_counts)
    assert any(f["rule"] == "traffic" and f["count"] == 7 for f in fires)


def test_alert_cooldown_coalesces():
    engine = AlertEngine(enabled=True, persistence=1, crowd_persons=5, traffic_vehicles=6, cooldown=30.0)
    cam = "camera-3"
    counts = {"person": 6}
    first = engine.evaluate(camera_id=cam, model_name="yolov12", tracked=[], counts=counts)
    second = engine.evaluate(camera_id=cam, model_name="yolov12", tracked=[], counts=counts)
    assert first and second == []
    engine.reset()
    third = engine.evaluate(camera_id=cam, model_name="yolov12", tracked=[], counts=counts)
    assert third, "reset should allow a fresh alert"


def test_alert_disabled():
    engine = AlertEngine(enabled=False, persistence=1, crowd_persons=5, traffic_vehicles=6, cooldown=30.0)
    assert engine.evaluate(camera_id="c", model_name="yolov12", tracked=[], counts={"person": 10}) == []


# --------------------------------------------------------------------------- #
# GPU scheduler
# --------------------------------------------------------------------------- #
def test_scheduler_cpu_mode_single_frame_batches():
    sched = GpuScheduler(accel_mode="cpu", batch_size=4)
    assert sched.device.accelerator == "cpu"
    plan = sched.batch_plan(7)
    assert plan == [1, 1, 1, 1, 1, 1, 1]


def test_scheduler_batch_plan_gpu():
    sched = GpuScheduler(accel_mode="cpu", batch_size=4)
    # force cuda semantics to test chunking (real device detection needs ort)
    sched._device = DeviceInfo(accelerator="cuda", device_name="cuda:0", providers=["CUDAExecutionProvider"])
    sched._detected_ts = time.monotonic()  # stop the 60s device re-detect
    plan = sched.batch_plan(9)
    assert plan == [4, 4, 1]


def test_scheduler_batch_plan_empty():
    assert GpuScheduler("cpu").batch_plan(0) == []


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #
def test_loader_resolve_weights_candidates(tmp_path):
    weights = tmp_path / "yolov12" / "yolov12s.onnx"
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"onnx")
    loader = ModelLoader(str(tmp_path), "cpu")
    assert loader.resolve_weights("yolov12") == weights
    assert loader.resolve_weights("missing") is None