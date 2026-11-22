// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <stdint.h>

// 20H392 Legacy fallback contract, not a measured panel timing.
namespace NuwaDisplayRefresh {
enum class Mode { Fixed, NonFixed };
enum class Result {
    Published, TickRange, DictionaryAllocation, KeyAllocation, NumberAllocation, Insert, Publish
};

template<class Backend>
Result publishFallback(Backend &backend, Mode mode)
{
    constexpr uint32_t min = 0x04444444;
    const uint32_t max = mode == Mode::Fixed ? min : 0x0aaaaaaa;
    const auto ticks = [&backend](uint32_t word) {
        return backend.ticks((uint64_t(word) * 1000000000ULL) >> 32);
    };
    const uint64_t minTicks = ticks(min);
    const uint64_t maxTicks = mode == Mode::Fixed ? minTicks : ticks(max);
    // Software 60 Hz fallback, not a measured panel period.
    constexpr uint64_t stepNs = 16666667;
    const uint64_t stepTicks = backend.ticks(stepNs);
    // Donor writes zero-extended w2 into a 64-bit OSNumber. Reject a
    // nonrepresentable conversion instead of silently wrapping the period.
    if (!minTicks || !maxTicks || !stepTicks || minTicks > UINT32_MAX ||
        maxTicks > UINT32_MAX || stepTicks > UINT32_MAX) {
        return Result::TickRange;
    }
    const char *const keys[] = {
        "displayMinRefreshInterval", "displayMinRefreshIntervalMachTime",
        "displayMaxRefreshInterval", "displayMaxRefreshIntervalMachTime",
        "displayRefreshStep", "displayRefreshStepMachTime",
    };
    const uint64_t values[] = {min, minTicks, max, maxTicks, stepNs, stepTicks};
    auto *dictionary = backend.dictionary(6);
    if (!dictionary) {
        return Result::DictionaryAllocation;
    }
    for (unsigned i = 0; i < 6; ++i) {
        auto *key = backend.key(keys[i]);
        if (!key) {
            backend.release(dictionary);
            return Result::KeyAllocation;
        }
        auto *number = backend.number(values[i], 64);
        if (!number) {
            backend.release(key);
            backend.release(dictionary);
            return Result::NumberAllocation;
        }
        const bool inserted = backend.insert(dictionary, key, number);
        backend.release(number);
        backend.release(key);
        if (!inserted) {
            backend.release(dictionary);
            return Result::Insert;
        }
    }
    auto *property = backend.key("IOMFBDisplayRefresh");
    if (!property) {
        backend.release(dictionary);
        return Result::KeyAllocation;
    }
    const bool published = backend.publish(property, dictionary);
    backend.release(property);
    backend.release(dictionary);
    return published ? Result::Published : Result::Publish;
}

template<class Backend>
bool publishFixedForStart(Backend &backend, unsigned requestedHz)
{
    // Absent/zero selects the software fallback; 60 is compatible with it.
    return (requestedHz == 0 || requestedHz == 60) &&
        publishFallback(backend, Mode::Fixed) == Result::Published;
}
}

class IOService;
extern "C" bool nuwa_legacy_publish_start_refresh(IOService &display, unsigned requestedHz);
