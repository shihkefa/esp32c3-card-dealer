#pragma once
#include "SPIFFS.h"
struct esp_partition_t {size_t size;};
constexpr int ESP_PARTITION_TYPE_DATA=1, ESP_PARTITION_SUBTYPE_DATA_SPIFFS=2, ESP_OK=0;
inline const esp_partition_t* esp_partition_find_first(int,int,const char*) {
  static const esp_partition_t storage{4096};
  return &storage;
}
inline int esp_partition_read(const esp_partition_t*,size_t offset,void* buf,size_t len) {
  if (offset+len>testfs::partition.size()) return -1;
  std::memcpy(buf,testfs::partition.data()+offset,len);
  return ESP_OK;
}
