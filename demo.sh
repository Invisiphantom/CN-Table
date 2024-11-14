

# 创建桥接网络
sudo brctl addbr br0
sudo ip addr add 10.0.5.1/24 dev br0
sudo ip link set br0 up

# 创建虚拟接口
sudo ip link add veth0 type veth peer name veth1
sudo ip link set veth0 up
sudo brctl addif br0 veth0

# 配置 veth1
sudo ip addr add 10.0.5.2/24 dev veth1
sudo ip link set veth1 up

# wget https://dldir1v6.qq.com/weixin/Windows/WeChatSetup.exe
# head -c 100M WeChatSetup.exe > 100M.send
# head -c 10M WeChatSetup.exe > 10M.send

# ./recv.sh GBN data/10M.recv
# ./send.sh GBN data/10M.send 0.000 0ms

# ./recv.sh SR data/100M.recv
# ./send.sh SR data/100M.send 0.000 0ms
