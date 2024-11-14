import os
import socket
import readline
import argparse
from tqdm import tqdm


def completer(text, state):
    options = [f for f in os.listdir() if f.startswith(text)]
    if state < len(options):
        return options[state]
    else:
        return None


os.chdir(os.path.dirname(__file__))
readline.set_completer(completer)
readline.parse_and_bind("tab: complete")

parser = argparse.ArgumentParser()
parser.add_argument("-s", "--addr", default="localhost", help="服务器地址")
parser.add_argument("-p", "--port", type=int, default=12345, help="服务器端口")
args = parser.parse_args()
server_addr = args.addr
server_port = args.port

SERVER = (server_addr, server_port)

while True:
    command = input("选择操作 (exit/ls/rm/md5/put/get/): ").strip().lower()
    action = command.split()[0]
    filename = command.split()[1] if len(command.split()) > 1 else None

    if action == "exit":
        break

    elif action == "ls":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"ls", SERVER)
        data, _ = sock.recvfrom(1024)
        print(data.decode())

    elif action == "rm":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"rm {filename}".encode(), SERVER)
        print(f"文件 {filename} 删除完成")

    elif action == "md5":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"md5 {filename}".encode(), SERVER)
        data, _ = sock.recvfrom(1024)
        print(data.decode())

    elif action == "put":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"put {filename}".encode(), SERVER)

        file_size = os.path.getsize(filename)
        sock.sendto(str(file_size).encode(), SERVER)

        with open(filename, "rb") as f:
            pbar = tqdm(total=file_size, unit="B", unit_scale=True, desc=filename)
            while data := f.read(1024):
                sock.sendto(data, SERVER)
                pbar.update(len(data))
            sock.sendto(b"", SERVER)
            pbar.close()

        print(f"文件 {filename} 上传完成")

    elif action == "get":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"get {filename}".encode(), SERVER)

        data, _ = sock.recvfrom(1024)
        file_size = int(data.decode())

        with open(filename, "wb") as f:
            pbar = tqdm(total=file_size, unit="B", unit_scale=True, desc=filename)
            received_size = 0
            while received_size < file_size:
                data, _ = sock.recvfrom(1024)
                if not data:
                    break
                f.write(data)
                received_size += len(data)
                pbar.update(len(data))
            pbar.close()

        print(f"文件 {filename} 下载完成")

    else:
        print("无效操作！")
