#!/usr/bin/env python3

import os
import time
import random
import socket
import hashlib
import argparse
import threading
from tqdm import tqdm
from Module import parse_pkt, build_pkt


class Client:
    def __init__(self, mode, vegas, host, port, filename, MSS):
        assert mode in ["GBN", "SR"]
        assert vegas in ["True", "False"]
        print(f"服务器: {host}:{port}")
        print(f"传输文件名: {filename}")
        print(f"最大负载长度: {MSS}")
        print("\033[33m" + f"传输模式: {mode}")
        print("\033[33m" + f"Vegas拥塞控制: {vegas}" + "\033[0m")

        self.mode = mode
        self.vegas = True if vegas == "True" else False

        self.SERVER = (host, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.MSS = MSS
        self.filename = filename
        self.filesize = os.path.getsize(self.filename)
        self.totalSeq = (self.filesize + self.MSS - 1) // self.MSS

        # Reno变量
        self.cwnd = 1.0
        self.ssthresh = 1024.0
        self.STATE = "SLOW_START"

        # 发送窗口
        self.base = 0
        self.nextSeqNum = 0
        self.window_data = {}

        # GBN定时器
        self.timer = None
        self.GBN_dupACK = 0
        self.GBN_reSend = False

        # SR定时器
        self.window_acks = {}
        self.window_timer = {}

        # RTT相关变量
        self.DevRTT = 1.0
        self.MAX_TIME = 5.0
        self.EstimatedRTT = self.MAX_TIME
        self.wait_time = self.MAX_TIME
        self.window_RTT = {}

        self.P_total_send = 0
        self.pbar = tqdm(total=self.filesize, unit="B", unit_scale=True, desc=self.filename)

    def udt_send(self, seqNum: int, data: bytes):
        """发送(校验和<2> 序列号<4> 数据负载)"""
        # 统计发送数据总量
        self.P_total_send += self.MSS

        # 记录发送时间
        self.window_RTT[seqNum] = time.time()

        # 构建发送数据包
        packet = build_pkt(seqNum, data)
        self.socket.sendto(packet, self.SERVER)

    def update_RTT(self, seqNum: int):
        """更新等待时间"""
        if seqNum not in self.window_RTT or random.random() > 0.01:
            return

        SampleRTT = time.time() - float(self.window_RTT[seqNum])
        self.DevRTT = 0.75 * self.DevRTT + 0.25 * abs(SampleRTT - self.EstimatedRTT)
        self.EstimatedRTT = 0.875 * self.EstimatedRTT + 0.125 * SampleRTT
        self.wait_time = 1.2 * self.EstimatedRTT + 4 * self.DevRTT
        del self.window_RTT[seqNum]

        if self.vegas:
            if SampleRTT > self.EstimatedRTT:
                self.cwnd = max(self.cwnd - 100.0, 1.0)

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

    def timeout(self, seqNum=None):
        """超时重传"""
        # 超时加倍等待时间 RTT
        self.wait_time = min(self.wait_time * 2.0, self.MAX_TIME)

        # 超时减半窗口大小 Reno
        self.STATE = "SLOW_START"
        self.ssthresh = max(self.cwnd / 2, 1)
        self.cwnd = 1.0

        if self.mode == "GBN":
            # 重传窗口内的所有数据包
            self.GBN_reSend = True
            maxSeq = min(self.nextSeqNum, self.totalSeq)
            for i in range(self.base, maxSeq):
                data = self.window_data.get(i, None)
                if data is not None:
                    self.udt_send(i, data)
            self.GBN_reSend = False
            self.start_timer()

        elif self.mode == "SR":
            # 只重传超时的数据包
            data = self.window_data.get(seqNum, None)
            if data is not None:
                self.udt_send(seqNum, data)
                self.start_timer(seqNum)

    def expand_cwnd(self):
        if self.STATE == "SLOW_START":
            self.cwnd += 1.0
            if self.cwnd >= self.ssthresh:
                self.STATE = "CON_AVOID"
        elif self.STATE == "CON_AVOID":
            self.cwnd += 1.0 / self.cwnd

    def receive_acks(self):
        """ACK接收线程"""
        while True:
            ack_pkt, _ = self.socket.recvfrom(64)
            state, ack_seqNum, _ = parse_pkt(ack_pkt)
            if state == False:
                continue

            # 计算更新RTT
            self.update_RTT(ack_seqNum)

            # 丢弃旧的ACK
            if ack_seqNum < self.base:
                if self.mode == "GBN":
                    self.GBN_dupACK += 1
                if self.GBN_dupACK == 3:
                    self.stop_timer()
                    self.timeout()  # 快速重传
                continue

            if self.mode == "GBN":
                self.base = ack_seqNum + 1
                self.GBN_dupACK = 0
                self.expand_cwnd()
                self.start_timer()

            elif self.mode == "SR":
                self.stop_timer(ack_seqNum)
                if ack_seqNum not in self.window_acks:
                    self.expand_cwnd()
                    self.window_acks[ack_seqNum] = True
                    # 右移窗口基序号 直到有未确认的分组
                    while self.base in self.window_acks:
                        self.base += 1

            max_window = max(self.cwnd, 1024)

            # 释放缓存数据
            if len(self.window_data) > max_window:
                for seqNum in list(self.window_data.keys()):
                    if seqNum < self.base:
                        self.window_data.pop(seqNum)

            # 释放缓存RTT
            if len(self.window_RTT) > max_window:
                for seqNum in list(self.window_RTT.keys()):
                    if seqNum < self.base:
                        self.window_RTT.pop(seqNum)

            # 释放缓存确认号
            if len(self.window_acks) > max_window:
                for seqNum in list(self.window_acks.keys()):
                    if seqNum < self.base:
                        self.window_acks.pop(seqNum)

            # 释放缓存定时器
            if len(self.window_timer) > max_window:
                for seqNum in list(self.window_timer.keys()):
                    if seqNum < self.base:
                        self.stop_timer(seqNum)
                        self.window_timer.pop(seqNum)

    def run(self):
        # ~~ 启动ACK接收线程
        threading.Thread(target=self.receive_acks, daemon=True).start()

        # ~~ 发送文件主循环
        self.P_start_time = time.time()
        with open(self.filename, "rb") as f:
            while self.nextSeqNum < self.totalSeq:
                while self.GBN_reSend:
                    pass

                # 如果窗口未满, 则开始发送
                while self.nextSeqNum < self.base + int(self.cwnd) and self.nextSeqNum < self.totalSeq:
                    if self.GBN_reSend:
                        break
                    # 读取并缓存文件数据
                    data: bytes = f.read(self.MSS)
                    self.window_data[self.nextSeqNum] = data
                    self.pbar.update(len(data))

                    # 发送数据
                    self.udt_send(self.nextSeqNum, data)

                    # 启动定时器
                    if self.mode == "GBN":
                        if self.base == self.nextSeqNum:
                            self.start_timer()
                    elif self.mode == "SR":
                        self.start_timer(self.nextSeqNum)

                    # 更新nextSeqNum
                    self.nextSeqNum += 1

            print("文件发送结束, 等待所有ACK接收...")
            while self.base < self.totalSeq:
                pass

            self.P_end_time = time.time()
            print("发送结束报文, 并等待结束ACK...")
            while self.base == self.totalSeq:
                # 停止所有定时器
                if self.mode == "SR":
                    for seqNum in list(self.window_timer.keys()):
                        self.stop_timer(seqNum)
                        self.window_timer.pop(seqNum)
                elif self.mode == "GBN":
                    self.stop_timer()
                self.udt_send(self.totalSeq, b"")
                time.sleep(0.1)

            print("\033[32m" + f"有效吞吐量: {self.filesize / (self.P_end_time - self.P_start_time) / 1024 ** 2:.2f} MB/s")
            print("\033[32m" + f"流量利用率: {self.filesize / self.P_total_send * 100:.2f}%")
            print("\033[0m" + "文件传输完成, 客户端关闭")
            self.socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-mode", help="传输模式", type=str, required=True)
    parser.add_argument("-vegas", help="Vegas拥塞控制", type=str, required=True)
    parser.add_argument("-host", help="服务器地址", type=str, required=True)
    parser.add_argument("-port", help="服务器端口", type=int, required=True)
    parser.add_argument("-input", help="发送文件名称", type=str, required=True)
    parser.add_argument("-mss", help="最大负载长度", type=int, required=True)
    args = parser.parse_args()

    client = Client(
        mode=args.mode,
        vegas=args.vegas,
        host=args.host,
        port=args.port,
        filename=args.input,
        MSS=args.mss,
    )
    client.run()

    # 打印文件的md5值
    with open(args.input, "rb") as f:
        print(f"{args.input}: ", hashlib.md5(f.read()).hexdigest())
        print()
