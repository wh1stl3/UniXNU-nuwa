// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
// A read-only transport for the unchanged VerifiedRoot envelope. The caller
// must freeze the returned storage and run vr_open before publishing a device.
template<class Ops>
static IOReturn nuwaReadRootPolicy(Ops &ops, uint64_t first, uint64_t last,
    uint64_t imageBytes, uint64_t expectedImageBytes, uint64_t rootDataEnd,
    uint64_t offset, uint64_t bytes, const uint8_t *expectedHeader,
    uint8_t *destination, uint64_t destinationBytes)
{
  constexpr uint64_t headerBytes = 544, maxPolicyBytes = 64ULL * 1024 * 1024;
  if (!destination || !expectedHeader || first > last || last > UINT32_MAX ||
      !imageBytes || imageBytes != expectedImageBytes || (imageBytes & 4095) ||
      imageBytes > (last - first + 1) * 4096 || (rootDataEnd & 4095) ||
      rootDataEnd > imageBytes || (offset & 4095) || offset < rootDataEnd ||
      bytes < headerBytes || bytes > maxPolicyBytes || offset >= imageBytes)
    return kIOReturnBadArgument;
  const uint64_t rounded = (bytes + 4095) & ~uint64_t(4095);
  if (rounded > destinationBytes || rounded > imageBytes - offset)
    return kIOReturnBadArgument;
  for (uint64_t done = 0; done < rounded;) {
    const uint32_t blocks = static_cast<uint32_t>(
        (rounded - done > 131072 ? 131072 : rounded - done) / 4096);
    IOReturn result = ops.read(first + (offset + done) / 4096, blocks, destination + done);
    if (result != kIOReturnSuccess) return result;
    done += uint64_t(blocks) * 4096;
  }
  return memcmp(destination, expectedHeader, headerBytes) ? kIOReturnNotPrivileged : kIOReturnSuccess;
}
