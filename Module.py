import os
import struct
import ctypes
import subprocess


os.chdir(os.path.dirname(__file__))
subprocess.run(["gcc", "-O2", "-shared", "-o", "checksum.so", "-fPIC", "checksum.c"])
lib = ctypes.CDLL("./checksum.so")
lib.get_checksum.argtypes = (ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t)
lib.get_checksum.restype = ctypes.c_uint16


def get_checksum(data: bytes):
    data = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
    return lib.get_checksum(data, len(data)).to_bytes(2, "big")


def parse_pkt(pkt: bytes):
    """(校验和<2> 序列号<4> 数据负载)"""
    if len(pkt) < 6:
        return False, None, None

    data_checksum: bytes = pkt[:2]
    exp_checksum = get_checksum(pkt[2:])
    if data_checksum != exp_checksum:
        return False, None, None

    seqNum = struct.unpack("I", pkt[2:6])[0]
    data: bytes = pkt[6:] if len(pkt) > 6 else b""
    return True, seqNum, data


def build_pkt(seqNum: int, data: bytes):
    """(校验和<2> 序列号<4> 数据负载)"""
    seqNum_bytes = struct.pack("I", seqNum)
    checksum = get_checksum(seqNum_bytes + data)
    return checksum + seqNum_bytes + data
