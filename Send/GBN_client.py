#!/usr/bin/env python3

import os
import time
import random
import struct
import socket
import ctypes
import hashlib
import argparse
import threading
import subprocess
from tqdm import tqdm

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
        print(f"长度错误: {len(pkt)}")
        return False, None, None

    data_checksum: bytes = pkt[:2]
    exp_checksum = get_checksum(pkt[2:])
    if data_checksum != exp_checksum:
        print("校验和错误")
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


class GBN_Client:
    def __init__(self, host, port, filename, MSS, N, loss_rate, corrupt_rate):
        print(f"服务器: {host}:{port}")
        print(f"传输文件名: {filename}")
        print(f"最大负载长度: {MSS}")
        print(f"窗口大小: {N}")

        self.SERVER = (host, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.MSS = MSS
        self.filename = filename
        self.filesize = os.path.getsize(self.filename)
        self.totalSeq = (self.filesize + self.MSS - 1) // self.MSS

        self.N = N
        self.base = 0
        self.nextSeqNum = 0
        self.window_data = {}

        self.timer = None
        self.DevRTT = 0
        self.EstimatedRTT = 1
        self.wait_time = 1
        self.window_RTT = {}

        self.lock = threading.Lock()

        self.loss_rate = loss_rate
        self.corrupt_rate = corrupt_rate

        self.pbar = tqdm(total=self.filesize, unit="B", unit_scale=True, desc=self.filename)

    def udt_send(self, seqNum: int, data: bytes):
        """发送(校验和<2> 序列号<4> 数据负载)"""
        # 记录发送时间
        self.window_RTT[seqNum] = time.time()

        # 构建发送数据包
        packet = build_pkt(seqNum, data)

        # 模拟比特位差错
        if random.random() < self.corrupt_rate:
            bit = random.randint(0, len(packet) * 8 - 1)
            byte, bit = bit // 8, bit % 8
            packet = bytearray(packet)
            packet[byte] ^= 1 << bit

        # 模拟丢包
        if random.random() >= self.loss_rate:
            self.socket.sendto(packet, self.SERVER)

    def update_RTT(self, seqNum: int):
        """更新等待时间"""
        if seqNum not in self.window_RTT:
            return

        SampleRTT = time.time() - self.window_RTT[seqNum]
        self.DevRTT = 0.75 * self.DevRTT + 0.25 * abs(SampleRTT - self.EstimatedRTT)
        self.EstimatedRTT = 0.875 * self.EstimatedRTT + 0.125 * SampleRTT
        self.wait_time = self.EstimatedRTT + 4 * self.DevRTT
        del self.window_RTT[seqNum]

    def start_timer(self):
        """启动定时器"""
        self.stop_timer()
        self.timer = threading.Timer(self.wait_time, self.timeout)
        self.timer.start()

    def stop_timer(self):
        """停止定时器"""
        if self.timer:
            self.timer.cancel()

    def timeout(self):
        """超时重传"""
        self.wait_time *= 2  # 加倍等待时间
        minSeq = min(self.nextSeqNum, self.totalSeq)

        # 重传窗口内的所有数据包
        with self.lock:  # * 加锁阻止主循环发送乱序数据
            for i in range(self.base, minSeq):
                data = self.window_data.get(i, None)
                if data is not None:
                    self.udt_send(i, data)
            self.start_timer()

    def receive_acks(self):
        """ACK接收线程"""
        while True:
            ack_pkt, _ = self.socket.recvfrom(64)
            state, ack_seqNum, _ = parse_pkt(ack_pkt)
            if state == False:
                continue

            self.update_RTT(ack_seqNum)

            # 如果分组校验和正确, 则右移窗口基序号
            if ack_seqNum >= self.base:
                self.base = ack_seqNum + 1

                # 如果缓存数据过多, 则释放
                if len(self.window_data) > 2 * self.N:
                    for seqNum in list(self.window_data.keys()):
                        if seqNum < self.base:
                            self.window_data.pop(seqNum)

                # 如果缓存RTT过多, 则释放
                if len(self.window_RTT) > 2 * self.N:
                    for seqNum in list(self.window_RTT.keys()):
                        if seqNum < self.base:
                            del self.window_RTT[seqNum]

                # 更新定时器状态
                if self.base == self.nextSeqNum:
                    self.stop_timer()
                else:
                    self.start_timer()

    def run(self):
        # ~~ 启动ACK接收线程
        threading.Thread(target=self.receive_acks, daemon=True).start()

        # ~~ 发送文件主循环
        with open(self.filename, "rb") as f:
            while self.nextSeqNum < self.totalSeq:
                # 当窗口满时, 等待ACK接收线程更新base
                while self.nextSeqNum == self.base + self.N:
                    pass

                # 如果窗口未满, 则开始发送
                with self.lock:  # * 加锁保证超时重传不乱序
                    while self.nextSeqNum < self.base + self.N and self.nextSeqNum < self.totalSeq:
                        # 读取文件数据, 并缓存
                        data: bytes = f.read(self.MSS)
                        self.window_data[self.nextSeqNum] = data
                        self.pbar.update(len(data))

                        # 发送数据
                        self.udt_send(self.nextSeqNum, data)

                        # 如果是窗口首个分组, 则启动定时器
                        if self.base == self.nextSeqNum:
                            self.start_timer()

                        # 更新nextSeqNum
                        self.nextSeqNum += 1

            # 文件传输结束, 等待所有ACK接收
            while self.base < self.totalSeq:
                time.sleep(0.1)

            # 发送结束报文, 并等待结束ACK
            while self.base == self.totalSeq:
                self.udt_send(self.totalSeq, b"")
                time.sleep(0.1)

            # 关闭socket
            print("文件传输完成, 客户端关闭")
            self.socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-host", help="服务器地址", type=str, required=True)
    parser.add_argument("-port", help="服务器端口", type=int, required=True)
    parser.add_argument("-input", help="发送文件名称", type=str, required=True)
    parser.add_argument("-mss", help="最大负载长度", type=int, required=True)
    parser.add_argument("-window", help="窗口大小", type=int, required=True)
    parser.add_argument("-loss", help="丢包率", type=float, required=True)
    parser.add_argument("-corrupt", help="比特差错率", type=float, required=True)
    args = parser.parse_args()

    client = GBN_Client(
        host=args.host,
        port=args.port,
        filename=args.input,
        MSS=args.mss,
        N=args.window,
        loss_rate=args.loss,
        corrupt_rate=args.corrupt,
    )
    client.run()

    # 打印文件的md5值
    with open(args.input, "rb") as f:
        print(f"{args.input}: ", hashlib.md5(f.read()).hexdigest())
