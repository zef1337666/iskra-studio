"""Лица: поиск (SCRFD) и сходство лиц (ArcFace). Всё на CPU, модели ~190 МБ в models/insightface/buffalo_l.

Нужно для замеров точности переноса персонажа (tests/bench_identity.py).
"""
import pathlib
import numpy as np
from ..config import ROOT

MODELS = ROOT / "models" / "insightface" / "buffalo_l"
_ARC = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)
_s = {}


def available():
    return (MODELS / "det_10g.onnx").exists() and (MODELS / "w600k_r50.onnx").exists()


def _sess(name):
    if name not in _s:
        import onnxruntime as ort
        _s[name] = ort.InferenceSession(str(MODELS / name), providers=["CPUExecutionProvider"])
    return _s[name]


def _read(path):
    import cv2
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)  # путь с кириллицей тоже читается
    if img is None:
        raise ValueError(f"не удалось прочитать {path}")
    return img  # BGR


def faces(img, thresh=0.5):
    """Лица на картинке (BGR ndarray): список (bbox[x1,y1,x2,y2], kps[5,2], score), крупные первыми."""
    import cv2
    sess = _sess("det_10g.onnx")
    h0, w0 = img.shape[:2]
    k = 640 / max(h0, w0)
    rs = cv2.resize(img, (int(w0 * k), int(h0 * k)))
    pad = np.zeros((640, 640, 3), np.uint8)
    pad[:rs.shape[0], :rs.shape[1]] = rs
    blob = cv2.dnn.blobFromImage(pad, 1.0 / 128, (640, 640), (127.5, 127.5, 127.5), swapRB=True)
    outs = [o.reshape(-1, o.shape[-1]) for o in sess.run(None, {sess.get_inputs()[0].name: blob})]
    boxes, kpss, scores = [], [], []
    for i, st in enumerate((8, 16, 32)):
        sc, bb, kp = outs[i][:, 0], outs[i + 3] * st, outs[i + 6] * st
        n = 640 // st
        c = np.stack(np.mgrid[:n, :n][::-1], axis=-1).astype(np.float32).reshape(-1, 2) * st
        c = np.repeat(c, 2, axis=0)
        m = sc >= thresh
        c, bb, kp = c[m], bb[m], kp[m]
        boxes.append(np.stack([c[:, 0] - bb[:, 0], c[:, 1] - bb[:, 1], c[:, 0] + bb[:, 2], c[:, 1] + bb[:, 3]], 1))
        kpss.append(np.stack([c[:, 0:1] + kp[:, 0::2], c[:, 1:2] + kp[:, 1::2]], -1))
        scores.append(sc[m])
    boxes, kpss, scores = np.concatenate(boxes) / k, np.concatenate(kpss) / k, np.concatenate(scores)
    if not len(scores):
        return []
    xywh = np.concatenate([boxes[:, :2], boxes[:, 2:] - boxes[:, :2]], 1)
    keep = cv2.dnn.NMSBoxes(xywh.tolist(), scores.tolist(), thresh, 0.4)
    res = [(boxes[i], kpss[i], float(scores[i])) for i in np.array(keep).reshape(-1)]
    return sorted(res, key=lambda f: -(f[0][2] - f[0][0]) * (f[0][3] - f[0][1]))


def embed(path):
    """Вектор лица (самого крупного) или None, если лица нет."""
    import cv2
    img = _read(path)
    f = faces(img)
    if not f:
        return None
    M, _ = cv2.estimateAffinePartial2D(f[0][1].astype(np.float32), _ARC, method=cv2.LMEDS)
    crop = cv2.warpAffine(img, M, (112, 112), borderValue=0.0)
    blob = cv2.dnn.blobFromImage(crop, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True)
    sess = _sess("w600k_r50.onnx")
    v = sess.run(None, {sess.get_inputs()[0].name: blob})[0][0]
    return v / np.linalg.norm(v)


def similarity(a, b):
    """Сходство лиц 0..1 (ArcFace). Один человек обычно > 0.5, разные — < 0.3."""
    ea, eb = embed(a), embed(b)
    if ea is None or eb is None:
        return None
    return float(np.dot(ea, eb))

