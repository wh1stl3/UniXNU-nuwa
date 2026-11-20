// SPDX-License-Identifier: BSD-2-Clause-Patent
// Compile-only with the real 8796 CPO. Never part of a device build.
#include "NuwaDisplayRefresh.h"
#include <IOKit/IOService.h>
#include <kern/clock.h>
#include <libkern/c++/OSDictionary.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSSymbol.h>

namespace {
struct RegistryBackend {
    IOService &display;

    uint64_t ticks(uint64_t ns)
    {
        uint64_t value;
        nanoseconds_to_absolutetime(ns, &value);
        return value;
    }

    OSDictionary *dictionary(unsigned capacity) { return OSDictionary::withCapacity(capacity); }
    // Avoid the const char * IORegistryEntry overload, which unconditionally
    // releases its temporary symbol even if interning failed in 8796.
    const OSSymbol *key(const char *name) { return OSSymbol::withCString(name); }
    OSNumber *number(uint64_t value, unsigned bits) { return OSNumber::withNumber(value, bits); }
    bool insert(OSDictionary *dict, const OSSymbol *key, OSNumber *value)
    {
        return dict->setObject(key, value);
    }
    bool publish(const OSSymbol *key, OSDictionary *dict) { return display.setProperty(key, dict); }
    void release(const OSObject *object) { object->release(); }
};
}

NuwaDisplayRefresh::Result nuwa_host_publish_refresh_fallback(
    IOService &display, NuwaDisplayRefresh::Mode mode)
{
    RegistryBackend backend{display};
    return NuwaDisplayRefresh::publishFallback(backend, mode);
}
