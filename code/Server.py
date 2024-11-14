#!/usr/bin/env python3

import socket
import hashlib
import argparse
from tqdm import tqdm
from Module import parse_pkt, build_pkt


class Server:
    def __init__(self, mode, port, output, mss):
        assert mode in ["SR", "GBN"]
        print(f"传输模式: {mode}")
        print(f"服务器绑定端口: {port}")
        print(f"输出文件名: {output}")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("0.0.0.0", port))
        self.socket.settimeout(0.5)

        self.mode = mode
        self.output = output
        self.bufsize = 10 + mss
        self.run_server = True

        if mode == "GBN":
            self.exp_seqNum = 0
        elif mode == "SR":
            self.N = 2048
            self.base = 0
            self.window_acks = {}
            self.window_data = {}

    def SR_write_window(self, f):
        """将窗口数据写入文件"""
        while self.base in self.window_acks:
            self.window_acks.pop(self.base)
            data = self.window_data.pop(self.base)

            if len(data) != 0:
                self.pbar.update(len(data))
                f.write(data)
            else:
                self.run_server = False
                self.pbar.close()

            self.base += 1

    def SR_run(self, f, client_addr, seqNum, data):
        # 发送 (校验和<2> 已确认序列号<8> "ACK")
        self.ack_pkt = build_pkt(seqNum, b"ACK")
        self.socket.sendto(self.ack_pkt, client_addr)

        # 缓存确认号和数据
        self.window_acks[seqNum] = True
        self.window_data[seqNum] = data

        # 如果缓存过大, 则写入文件
        if len(self.window_acks) > self.N:
            self.SR_write_window(f)

    def GBN_run(self, f, client_addr, seqNum, data):
        if seqNum != self.exp_seqNum:
            if self.exp_seqNum > 0:
                # 发送 (校验和<2> 已确认序列号<8> "ACK")
                self.ack_pkt = build_pkt(self.exp_seqNum - 1, b"ACK")
                self.socket.sendto(self.ack_pkt, client_addr)
        else:
            # 发送 (校验和<2> 已确认序列号<8> "ACK")
            self.ack_pkt = build_pkt(seqNum, b"ACK")
            self.socket.sendto(self.ack_pkt, client_addr)

            # 更新期望序号
            self.exp_seqNum += 1

            # 将数据写入文件
            if len(data) != 0:
                self.pbar.update(len(data))
                f.write(data)
            else:
                self.run_server = False
                self.pbar.close()

    def run(self):
        print("服务器启动, 等待客户端连接...")
        self.pbar = tqdm(unit="B", unit_scale=True, desc=self.output)
        with open(self.output, "wb") as f:
            while self.run_server:
                try:
                    data_pkt, client_addr = self.socket.recvfrom(self.bufsize)
                except socket.timeout:
                    if self.mode == "SR":
                        self.SR_write_window(f)
                    continue

                state, seqNum, data = parse_pkt(data_pkt)
                if state == False:
                    continue

                if self.mode == "GBN":
                    self.GBN_run(f, client_addr, seqNum, data)
                elif self.mode == "SR":
                    self.SR_run(f, client_addr, seqNum, data)

            while True:
                try:
                    # 不断回复结束ACK, 直到客户端关闭
                    self.socket.settimeout(1)
                    _, client_addr = self.socket.recvfrom(self.bufsize)
                    self.socket.sendto(self.ack_pkt, client_addr)
                except socket.timeout:
                    print("文件接收完成, 服务器关闭")
                    self.socket.close()
                    break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-mode", help="传输模式", type=str, required=True)
    parser.add_argument("-port", help="服务器端口", type=int, required=True)
    parser.add_argument("-output", help="接收文件名称", type=str, required=True)
    parser.add_argument("-mss", help="最大负载长度", type=int, required=True)
    args = parser.parse_args()

    server = Server(
        mode=args.mode,
        port=args.port,
        output=args.output,
        mss=args.mss,
    )
    server.run()

    # 打印文件的md5值
    with open(args.output, "rb") as f:
        print(f"{args.output}: ", hashlib.md5(f.read()).hexdigest())