"""Generated torrent bytes for offline and isolated tests."""

import hashlib


def bencode(value):
    if isinstance(value, int):
        return b"i" + str(value).encode() + b"e"
    if isinstance(value, bytes):
        return str(len(value)).encode() + b":" + value
    if isinstance(value, dict):
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in sorted(value.items())) + b"e"
    raise TypeError(type(value))


def sample(name):
    payload = ("Generated qbitbot acceptance data: " + name + "\n").encode() * 64
    info = bencode(
        {
            b"name": name.encode(),
            b"length": len(payload),
            b"piece length": 16384,
            b"pieces": hashlib.sha1(payload).digest(),
            b"private": 1,
        }
    )
    return {
        "name": name,
        "payload": payload,
        "info": info,
        "hash": hashlib.sha1(info).hexdigest(),
        "torrent": b"d4:info" + info + b"e",
    }
