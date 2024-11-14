import os
import socket
from tqdm import tqdm

os.chdir(os.path.dirname(__file__))

server_addr = "0.0.0.0"
server_port = 12345
SERVER = (server_addr, server_port)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(SERVER)

print(f"服务器启动，在 {SERVER} 等待连接...")

while True:
    data, client_addr = sock.recvfrom(1024)
    action = data.decode()

    print(f"接收到命令: {action} 来自 {client_addr}")

    if action == "ls":
        files = os.listdir()
        sock.sendto("\n".join(files).encode(), client_addr)

    elif action.startswith("rm"):
        filename = action.split()[1]
        os.remove(filename)
        print(f"文件 {filename} 删除完成")

    elif action.startswith("md5"):
        filename = action.split()[1]
        md5 = os.popen(f"md5sum {filename}").read()
        sock.sendto(md5.encode(), client_addr)

    elif action.startswith("put"):
        filename = action.split()[1]
        print(f"开始接收文件: {filename}")

        data, client_addr = sock.recvfrom(1024)
        file_size = int(data.decode())

        with open(filename, "wb") as f:
            pbar = tqdm(total=file_size, unit="B", unit_scale=True, desc=filename)
            received_size = 0
            while received_size < file_size:
                data, client_addr = sock.recvfrom(1024)
                if not data:
                    break
                f.write(data)
                received_size += len(data)
                pbar.update(len(data))
            pbar.close()

        print(f"文件 {filename} 上传完成")

    elif action.startswith("get"):
        filename = action.split()[1]
        if os.path.exists(filename):
            print(f"发送文件: {filename}")

            file_size = os.path.getsize(filename)
            sock.sendto(str(file_size).encode(), client_addr)

            with open(filename, "rb") as f:
                pbar = tqdm(total=file_size, unit="B", unit_scale=True, desc=filename)
                while data := f.read(1024):
                    sock.sendto(data, client_addr)
                    pbar.update(len(data))

            sock.sendto(b"", client_addr)
            pbar.close()

            print(f"文件 {filename} 下载完成")
        else:
            sock.sendto(b"File not found", client_addr)

    else:
        sock.sendto(b"Invalid command", client_addr)
