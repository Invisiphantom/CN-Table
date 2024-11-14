
# head -c 100M hadoop-3.3.6.tar.gz > 100M.send
# head -c 10M hadoop-3.3.6.tar.gz > 10M.send

# ./recv.sh GBN data/10M.recv
# ./send.sh GBN data/10M.send

# ./recv.sh SR data/100M.recv
# ./send.sh SR data/100M.send
