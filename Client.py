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


class Client:
    def __init__(self, mode, host, port, filename, MSS, N, loss_rate, corrupt_rate):
        assert mode in ["GBN", "SR"]
        print(f"传输模式: {mode}")
        print(f"服务器: {host}:{port}")
        print(f"传输文件名: {filename}")
        print(f"最大负载长度: {MSS}")
        print(f"窗口大小: {N}")

        self.mode = mode
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

        if mode == "GBN":
            self.timer = None
        elif mode == "SR":
            self.window_acks = {}
            self.window_timer = {}

        self.DevRTT = 0.0
        self.MAX_TIME = 1.0
        self.EstimatedRTT = self.MAX_TIME
        self.wait_time = self.MAX_TIME
        self.window_RTT = {}

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
        if seqNum not in self.window_RTT or random.random() > 0.01:
            return

        SampleRTT = time.time() - float(self.window_RTT[seqNum])
        self.DevRTT = 0.75 * self.DevRTT + 0.25 * abs(SampleRTT - self.EstimatedRTT)
        self.EstimatedRTT = 0.875 * self.EstimatedRTT + 0.125 * SampleRTT
        self.wait_time = self.EstimatedRTT + 4 * self.DevRTT
        del self.window_RTT[seqNum]

    def start_timer(self, seqNum=None):
        """启动定时器"""

        if self.mode == "GBN":
            self.stop_timer()
            self.timer = threading.Timer(self.wait_time, self.timeout)
            self.timer.start()

        elif self.mode == "SR":
            self.stop_timer(seqNum)
            self.window_timer[seqNum] = threading.Timer(self.wait_time, self.timeout, args=(seqNum,))
            self.window_timer[seqNum].start()

    def stop_timer(self, seqNum=None):
        """停止定时器"""

        if self.mode == "GBN":
            if self.timer:
                self.timer.cancel()

        elif self.mode == "SR":
            if seqNum in self.window_timer:
                self.window_timer[seqNum].cancel()

    def stop_all_timer(self):
        """停止所有定时器"""
        for seqNum in list(self.window_timer.keys()):
            self.stop_timer(seqNum)

    def timeout(self, seqNum):
        """超时重传"""
        # 超时加倍等待时间
        self.wait_time = min(self.wait_time * 2.0, self.MAX_TIME)

        if self.mode == "GBN":
            # 重传窗口内的所有数据包
            maxSeq = min(self.nextSeqNum, self.totalSeq)
            for i in range(self.base, maxSeq):
                data = self.window_data.get(i, None)
                if data is not None:
                    self.udt_send(i, data)
            self.start_timer()

        elif self.mode == "SR":
            data = self.window_data.get(seqNum, None)
            if data is not None:
                self.udt_send(seqNum, data)
                self.start_timer(seqNum)

    def receive_acks(self):
        """ACK接收线程"""
        while True:
            ack_pkt, _ = self.socket.recvfrom(64)
            state, ack_seqNum, _ = parse_pkt(ack_pkt)
            if state == False:
                continue

            # 计算更新RTT
            self.update_RTT(ack_seqNum)

            if self.mode == "GBN":
                self.GBN_acks(ack_seqNum)
            elif self.mode == "SR":
                self.SR_acks(ack_seqNum)

    def GBN_acks(self, ack_seqNum):
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

    def SR_acks(self, ack_seqNum):
        # 如果分组校验和正确
        if ack_seqNum >= self.base:
            # 标记分组已确认 并停止定时器
            self.window_acks[ack_seqNum] = True
            self.stop_timer(ack_seqNum)

            # 右移窗口基序号 直到有未确认的分组
            if ack_seqNum == self.base:
                while self.base in self.window_acks:
                    self.base += 1

            # 如果缓存数据过多, 则释放
            if len(self.window_data) > 2 * self.N:
                for seqNum in list(self.window_data.keys()):
                    if seqNum < self.base:
                        self.window_data.pop(seqNum)

            # 如果缓存确认号过多, 则释放
            if len(self.window_acks) > 2 * self.N:
                for seqNum in list(self.window_acks.keys()):
                    if seqNum < self.base:
                        self.window_acks.pop(seqNum)

    def run(self):
        # ~~ 启动ACK接收线程
        threading.Thread(target=self.receive_acks, daemon=True).start()

        # ~~ 发送文件主循环
        with open(self.filename, "rb") as f:
            while self.nextSeqNum < self.totalSeq:
                # 如果窗口未满, 则开始发送
                while self.nextSeqNum < self.base + self.N and self.nextSeqNum < self.totalSeq:
                    # 读取并缓存文件数据
                    data: bytes = f.read(self.MSS)
                    self.window_data[self.nextSeqNum] = data
                    self.pbar.update(len(data))

                    # 发送数据
                    self.udt_send(self.nextSeqNum, data)

                    # 启动定时器
                    if self.mode == "GBN":
                        if self.base == self.nextSeqNum:
                            self.GBN_start_timer()
                    elif self.mode == "SR":
                        self.start_timer(self.nextSeqNum)

                    # 更新nextSeqNum
                    self.nextSeqNum += 1

            # 文件传输结束, 等待所有ACK接收
            while self.base < self.totalSeq:
                time.sleep(0.1)

            # 停止所有定时器
            if self.mode == "SR":
                for seqNum in list(self.window_timer.keys()):
                    self.stop_timer(seqNum)
            elif self.mode == "GBN":
                self.stop_timer()

            # 发送结束报文, 并等待结束ACK
            while self.base == self.totalSeq:
                self.udt_send(self.totalSeq, b"")
                time.sleep(0.1)

            print("文件传输完成, 客户端关闭")
            self.socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-mode", help="传输模式", type=str, required=True)
    parser.add_argument("-host", help="服务器地址", type=str, required=True)
    parser.add_argument("-port", help="服务器端口", type=int, required=True)
    parser.add_argument("-input", help="发送文件名称", type=str, required=True)
    parser.add_argument("-mss", help="最大负载长度", type=int, required=True)
    parser.add_argument("-window", help="窗口大小", type=int, required=True)
    parser.add_argument("-loss", help="丢包率", type=float, required=True)
    parser.add_argument("-corrupt", help="比特差错率", type=float, required=True)
    args = parser.parse_args()

    client = Client(
        mode=args.mode,
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
