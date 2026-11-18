#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <map>
#include <string>
#include <vector>

constexpr char FILE_READ = 'r', FILE_WRITE = 'w';

namespace testfs {
using Bytes = std::vector<uint8_t>;
inline std::map<std::string,Bytes> files;
inline size_t writeBudget = std::numeric_limits<size_t>::max();
inline bool formatted = false, mountFailure = false, denyWrite = false;
inline unsigned formats = 0;
inline Bytes partition(4096, 0xff);
}

class File {
 public:
  File() = default;
  explicit File(testfs::Bytes* data): data_(data) {}
  explicit operator bool() const {return data_ != nullptr;}
  size_t size() const {return data_->size();}
  size_t read(uint8_t* out, size_t count) {
    size_t n = std::min(count, data_->size()-pos_);
    std::memcpy(out,data_->data()+pos_,n); pos_+=n;
    return n;
  }
  size_t write(const uint8_t* src, size_t count) {
    size_t n = std::min(testfs::writeBudget,count);
    data_->insert(data_->end(),src,src+n);
    testfs::writeBudget-=n;
    return n;
  }
  void close() {data_=nullptr;}
 private:
  testfs::Bytes* data_ = nullptr;
  size_t pos_ = 0;
};

struct TestSPIFFS {
  bool begin(bool format) {
    if (testfs::mountFailure) return false;
    if (!testfs::formatted && format) {
      ++testfs::formats;
      testfs::files.clear();
      testfs::partition.front()=0;
      testfs::formatted=true;
    }
    return testfs::formatted;
  }
  bool exists(const char* path) const {return testfs::files.count(path)!=0;}
  bool remove(const char* path) {return testfs::files.erase(path)!=0;}
  bool rename(const char* from,const char* to) {
    if (!exists(from)||exists(to)) return false;
    testfs::files[to]=std::move(testfs::files.at(from));
    return remove(from);
  }
  File open(const char* path,char mode) {
    if (mode==FILE_WRITE) {
      if (testfs::denyWrite) return {};
      auto& bytes=testfs::files[path]; bytes.clear(); return File(&bytes);
    }
    return exists(path)?File(&testfs::files.at(path)):File{};
  }
};
inline TestSPIFFS SPIFFS;
