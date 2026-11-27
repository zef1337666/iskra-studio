"""Мини-конструктор графов ComfyUI в API-формате."""
import itertools


class Graph:
    def __init__(self):
        self.nodes = {}
        self._ids = itertools.count(1)

    def add(self, class_type, title=None, **inputs):
        nid = str(next(self._ids))
        node = {"class_type": class_type, "inputs": {}}
        for k, v in inputs.items():
            if v is None:  # необязательный вход не подключён
                continue
            node["inputs"][k] = v.ref if isinstance(v, Out) else v
        if title:
            node["_meta"] = {"title": title}
        self.nodes[nid] = node
        return Node(nid)

    def to_api(self):
        return self.nodes


class Out:
    def __init__(self, nid, slot):
        self.ref = [nid, slot]


class Node:
    def __init__(self, nid):
        self.id = nid

    def __getitem__(self, slot):
        return Out(self.id, slot)

    @property
    def out(self):
        return Out(self.id, 0)
