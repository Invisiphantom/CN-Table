#!/usr/bin/env python3

import os
import time
import struct
import socket
import ctypes
import hashlib
import argparse
import subprocess
from tqdm import tqdm

DEBUG = False

os.chdir(os.path.dirname(__file__))
if not os.path.exists("./checksum.so"):
    subprocess.run("gcc -O2 -shared -o checksum.so -fPIC checksum.c")

lib = ctypes.CDLL("./checksum.so")
lib.get_checksum.argtypes = (ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t)
lib.get_checksum.restype = ctypes.c_uint16


def get_checksum(data: bytes):
    data = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
    return lib.get_checksum(data, len(data)).to_bytes(2, "big")


def parse_pkt(pkt: bytes):
    """(校验和<2> 序列号<4> 数据负载)"""
    if len(pkt) < 6:
        if DEBUG:
            print(f"长度错误: {len(pkt)}")
        return False, None, None

    data_checksum: bytes = pkt[:2]
    exp_checksum = get_checksum(pkt[2:])

    if data_checksum != exp_checksum:
        if DEBUG:
            print("\n校验和错误")
            print(f"期望: {exp_checksum.hex()}")
            print(f"实际: {data_checksum.hex()}")
        return False, None, None

    seqNum = struct.unpack("I", pkt[2:6])[0]
    data: bytes = pkt[6:] if len(pkt) > 6 else b""
    return True, seqNum, data


def build_pkt(seqNum: int, data: bytes):
    """(校验和<2> 序列号<4> 数据负载)"""
    seqNum_bytes = struct.pack("I", seqNum)
    checksum = get_checksum(seqNum_bytes + data)
    return checksum + seqNum_bytes + data


class GBN_Server:
    def __init__(self, port, output, mss):
        print(f"服务器绑定端口: {port}")
        print(f"输出文件名: {output}")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("0.0.0.0", port))
        self.output = output
        self.bufsize = 10 + mss
        self.exp_seqNum = 0

    def run(self):
        print("服务器启动, 等待客户端连接...")
        self.pbar = tqdm(unit="B", unit_scale=True, desc=self.output)
        with open(self.output, "wb") as f:
            while True:
                data_pkt, client_addr = self.socket.recvfrom(self.bufsize)
                state, seqNum, data = parse_pkt(data_pkt)

                if state == False:
                    continue

                # 确保序号正确
                if seqNum != self.exp_seqNum:
                    if DEBUG:
                        print("\n序号错误")
                        print(f"期望: {self.exp_seqNum}")
                        print(f"实际: {seqNum}")
                    self.ack_pkt = build_pkt(self.exp_seqNum - 1, b"ACK")
                    self.socket.sendto(self.ack_pkt, client_addr)
                    continue

                # 发送 (校验和<2> 已确认序列号<8> "ACK")
                self.ack_pkt = build_pkt(self.exp_seqNum, b"ACK")
                self.socket.sendto(self.ack_pkt, client_addr)

                # 更新期望序号
                self.exp_seqNum += 1

                # 将数据写入文件
                if len(data) != 0:
                    self.pbar.update(len(data))
                    f.write(data)
                else:
                    self.pbar.close()
                    print("文件接收完成")
                    break

        while True:
            try:
                # 不断回复结束ACK, 直到客户端关闭
                self.socket.settimeout(2)
                _, client_addr = self.socket.recvfrom(self.bufsize)
                self.socket.sendto(self.ack_pkt, client_addr)
            except socket.timeout:
                print("服务器关闭")
                self.socket.close()
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-port", help="服务器端口", type=int, required=True)
    parser.add_argument("-output", help="接收文件名称", type=str, required=True)
    parser.add_argument("-mss", help="最大负载长度", type=int, required=True)
    args = parser.parse_args()

    server = GBN_Server(
        port=args.port,
        output=args.output,
        mss=args.mss,
    )
    server.run()

    # 打印文件的md5值
    with open(args.output, "rb") as f:
        print(f"{args.output}: ", hashlib.md5(f.read()).hexdigest())
