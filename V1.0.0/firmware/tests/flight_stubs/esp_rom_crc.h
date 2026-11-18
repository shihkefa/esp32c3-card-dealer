#pragma once
#include <cstdint>
#include <cstddef>
inline uint32_t esp_rom_crc32_le(uint32_t crc, const uint8_t* ptr, size_t len) {
  crc=~crc;
  while (len--) {
    crc ^= *ptr++;
    for (unsigned bit=0;bit<8;++bit) crc=(crc>>1)^(0xedb88320U&uint32_t(-int32_t(crc&1)));
  }
  return ~crc;
}
