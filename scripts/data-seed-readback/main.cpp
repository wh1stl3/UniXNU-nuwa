// Host-only validation against a hash-pinned, read-only SparseDisk.h snapshot.
#include "SparseDisk.h"
#include <openssl/evp.h>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <vector>

struct Disk {
  RamSparseDisk value{};
  ~Disk() {
    if (!value.pages) return;
    for (uint64_t i = 0; i < value.bytes / 4096; ++i) free(value.pages[i]);
    free(value.pages);
  }
};
int main(int argc, char **argv) {
  if (argc != 2) return 64;
  std::ifstream input(argv[1], std::ios::binary | std::ios::ate);
  if (!input) return 2;
  auto size = input.tellg();
  if (size < 32 || size > 0x10000000) return 2;
  std::vector<uint8_t> bytes(static_cast<size_t>(size));
  input.seekg(0); input.read(reinterpret_cast<char *>(bytes.data()), size);
  if (!input) return 2;
  uint64_t logical = 0;
  if (!ramPackedLayout(bytes.data(), bytes.size(), &logical)) return 3;
  Disk disk;
  disk.value.bytes = logical;
  disk.value.pages = static_cast<uint8_t **>(calloc(logical / 4096, sizeof(uint8_t *)));
  if (!disk.value.pages) return 4;
  struct Ops { uint8_t *allocate() { return static_cast<uint8_t *>(calloc(1, 4096)); } } ops;
  if (!ramSparseImport(disk.value, bytes.data(), bytes.size(), ops)) return 4;
  EVP_MD_CTX *context = EVP_MD_CTX_new();
  if (!context) return 4;
  bool ok = EVP_DigestInit_ex(context, EVP_sha256(), nullptr) == 1;
  const uint8_t zero[4096]{};
  for (uint64_t i = 0; ok && i < logical / 4096; ++i)
    ok = EVP_DigestUpdate(context, disk.value.pages[i] ? disk.value.pages[i] : zero, 4096) == 1;
  uint8_t digest[32]; unsigned length = 0;
  ok = ok && EVP_DigestFinal_ex(context, digest, &length) == 1 && length == sizeof(digest);
  EVP_MD_CTX_free(context);
  if (!ok) return 5;
  printf("{\"logical_bytes\":%llu,\"resident_bytes\":%llu,\"pointer_table_bytes\":%llu,\"sha256\":\"",
         static_cast<unsigned long long>(logical), static_cast<unsigned long long>(disk.value.resident),
         static_cast<unsigned long long>(logical / 4096 * sizeof(uint8_t *)));
  for (auto value : digest) printf("%02x", value);
  puts("\"}");
  return 0;
}
