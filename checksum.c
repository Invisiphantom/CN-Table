#include <stdint.h>
#include <stddef.h>

// gcc -O2 -shared -o checksum.so -fPIC checksum.c
uint16_t get_checksum(const uint8_t* data, size_t length)
{
    uint32_t sum = 0;

    // 每两个字节累加
    for (size_t i = 0; i < length - 1; i += 2)
        sum += (data[i] << 8) | data[i + 1];

    // 处理奇数情况
    if (length % 2 == 1)
        sum += data[length - 1] << 8;

    // 处理进位
    while (sum >> 16)
        sum = (sum & 0xFFFF) + (sum >> 16);

    return (uint16_t)~sum;
}