// SPDX-License-Identifier: BSD-2-Clause-Patent
#include "NuwaDisplayRefresh.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <map>
#include <string>
#include <variant>
#include <vector>

using NuwaDisplayRefresh::Mode;
using NuwaDisplayRefresh::Result;
using NuwaDisplayRefresh::publishFixedForStart;
namespace {
constexpr auto minKey = "displayMinRefreshInterval";
constexpr auto maxKey = "displayMaxRefreshInterval";
constexpr auto minMach = "displayMinRefreshIntervalMachTime";
constexpr auto maxMach = "displayMaxRefreshIntervalMachTime";
constexpr auto step = "displayRefreshStep";
constexpr auto stepMach = "displayRefreshStepMachTime";
enum class Type { Number, Boolean, String };
struct Value { int64_t value; Type type = Type::Number; };
using Dict = std::map<std::string, Value>;

struct Fixture {
    struct Number { Value value; unsigned refs = 1; };
    using Building = std::map<std::string, Number *>;
    Dict registry{{"previous", {42}}};
    std::vector<uint64_t> ns;
    unsigned allocations = 0, inserts = 0, publications = 0, live = 0;
    unsigned keyAllocations = 0, failKey = 0, failNumber = 0, failInsert = 0;
    bool failDictionary = false, failPublish = false;
    uint64_t overrideTicks = UINT64_MAX;

    uint64_t ticks(uint64_t n)
    {
        ns.push_back(n);
        // Fixture timebase: 125/3 ns per tick. Not a mode or hardware selection.
        return overrideTicks == UINT64_MAX ? n * 3 / 125 : overrideTicks;
    }
    Building *dictionary(unsigned capacity)
    {
        assert(capacity == 6);
        if (failDictionary) return nullptr;
        ++live;
        return new Building;
    }
    std::string *key(const char *name)
    {
        if (++keyAllocations == failKey) return nullptr;
        ++live;
        return new std::string(name);
    }
    Number *number(uint64_t value, unsigned bits)
    {
        assert(bits == 64);
        if (++allocations == failNumber) return nullptr;
        ++live;
        return new Number{{static_cast<int64_t>(value)}};
    }
    bool insert(Building *dict, const std::string *key, Number *n)
    {
        if (++inserts == failInsert) return false;
        assert(dict->emplace(*key, n).second);
        ++n->refs;
        return true;
    }
    bool publish(const std::string *key, Building *dict)
    {
        assert(*key == "IOMFBDisplayRefresh" && dict->size() == 6);
        ++publications;
        if (failPublish) return false;
        registry.clear();
        for (const auto &entry : *dict) registry.emplace(entry.first, entry.second->value);
        return true;
    }
    void release(std::string *key) { delete key; --live; }
    void release(Number *n)
    {
        assert(n->refs);
        if (--n->refs == 0) { delete n; --live; }
    }
    void release(Building *dict)
    {
        for (const auto &entry : *dict) release(entry.second);
        delete dict;
        --live;
    }
};

// Typed-input models of the two traced branches in §14.
int64_t read(const Dict *d, const char *key, bool acceptsBoolean = false)
{
    if (!d) return 0;
    const auto it = d->find(key);
    if (it == d->end() || it->second.type == Type::String ||
        (!acceptsBoolean && it->second.type == Type::Boolean)) return 0;
    return it->second.value;
}
double quartz(const Dict *d, bool halve = false, bool allowStep = true)
{
    const auto ticks = static_cast<int32_t>(read(d, stepMach, true));
    const auto min = static_cast<int32_t>(read(d, minKey, true));
    if (allowStep && ticks) return ticks * (125.0 / 3 * 1e-9);
    if (min) return std::ldexp(double(min), halve ? -33 : -32);
    return 1.0 / 60;
}
void media(const Dict *d, int max, int min, int increment)
{
    const auto scale = [d](const char *key, double unit, int fallback) {
        const int64_t v = read(d, key);
        return v >= 1 ? static_cast<int>(std::round(unit / v)) : fallback;
    };
    assert(scale(maxKey, 4294967296., 60) == max);
    assert(scale(minKey, 4294967296., 60) == min);
    assert(scale(step, 1e9, 0) == increment); // 0 denotes kCMTimeInvalid.
}
void near(double actual, double expected) { assert(std::abs(actual - expected) < 1e-12); }

void readers()
{
    Fixture fixed, variable;
    assert(publishFallback(fixed, Mode::Fixed) == Result::Published);
    assert(publishFallback(variable, Mode::NonFixed) == Result::Published);
    assert((fixed.ns == std::vector<uint64_t>{16666666, 16666667}));
    assert((variable.ns == std::vector<uint64_t>{16666666, 41666666, 16666667}));
    assert(!fixed.live && !variable.live);
    for (const auto &f : {fixed, variable}) {
        assert(f.registry.size() == 6 && f.publications == 1);
        assert(read(&f.registry, minKey) == 0x04444444 && read(&f.registry, minMach) == 399999);
        assert(f.registry.at(step).value == 16666667 && f.registry.at(stepMach).value == 400000);
        near(quartz(&f.registry), 1.0 / 60);
    }
    assert(read(&fixed.registry, maxKey) == 0x04444444 && read(&fixed.registry, maxMach) == 399999);
    assert(read(&variable.registry, maxKey) == 0x0aaaaaaa && read(&variable.registry, maxMach) == 999999);
    media(&fixed.registry, 60, 60, 60);
    media(&variable.registry, 24, 60, 60);
    // 19.2 MHz, integer conversion truncates toward zero.
    assert(16666667ULL * 19200000ULL / 1000000000ULL == 320000);
    using Property = std::variant<std::monostate, Value, Dict>;
    for (const Property &p : {Property{}, Property{Value{42}}}) {
        const auto *dictionary = std::get_if<Dict>(&p);
        near(quartz(dictionary), 1.0 / 60);
        media(dictionary, 60, 60, 0);
    }
    const Dict empty;
    near(quartz(&empty), 1.0 / 60);
    media(&empty, 60, 60, 0);

    Dict input = variable.registry;
    input[minKey] = {0x08000000}; // Reader discrimination only, not formatter input.
    input[step] = {20000000};
    input[stepMach] = {240000};
    near(quartz(&input), 0.01);
    near(quartz(&input, true, false), 1.0 / 64);
    media(&input, 24, 32, 50);
    for (auto key : {minKey, maxKey, minMach, maxMach, step, stepMach}) {
        for (auto bad : {Value{0}, Value{9, Type::String}, Value{-1}}) {
            // Quartz takes signed values, including negative; test zero/type
            // fallback separately from MediaToolbox's positive-value filter.
            auto changed = input;
            changed[key] = bad;
            media(&changed, key == maxKey ? 60 : 24, key == minKey ? 60 : 32, key == step ? 0 : 50);
            near(quartz(&changed), key != stepMach ? 0.01 :
                 bad.value == -1 ? -(125.0 / 3 * 1e-9) : 1.0 / 32);
        }
        auto missing = input;
        missing.erase(key);
        media(&missing, key == maxKey ? 60 : 24, key == minKey ? 60 : 32, key == step ? 0 : 50);
        near(quartz(&missing), key == stepMach ? 1.0 / 32 : 0.01);
    }
    auto changed = input;
    changed[stepMach] = {480000};
    near(quartz(&changed), 0.02);
    media(&changed, 24, 32, 50);
    changed = input;
    changed[step] = {25000000};
    near(quartz(&changed), 0.01);
    media(&changed, 24, 32, 40);
    changed = input;
    changed[minKey] = {0x04000000};
    near(quartz(&changed, false, false), 1.0 / 64);
    media(&changed, 24, 64, 50);
    changed[stepMach] = {0};
    changed[minKey] = {1, Type::Boolean};
    near(quartz(&changed), std::ldexp(1., -32));
    media(&changed, 24, 60, 50);
}

void failures()
{
    const auto reject = [](Fixture &f, Result expected, unsigned count, unsigned attempts) {
        assert(publishFallback(f, Mode::NonFixed) == expected);
        assert(!f.live && f.registry.size() == 1 && f.registry.at("previous").value == 42);
        assert(f.allocations == count && f.publications == attempts);
    };
    for (uint64_t ticks : {uint64_t(0), uint64_t(UINT32_MAX) + 1}) {
        Fixture f;
        f.overrideTicks = ticks;
        reject(f, Result::TickRange, 0, 0);
    }
    Fixture allocation;
    allocation.failDictionary = true;
    reject(allocation, Result::DictionaryAllocation, 0, 0);
    for (unsigned index = 1; index <= 7; ++index) {
        Fixture key;
        key.failKey = index;
        reject(key, Result::KeyAllocation, index - 1, 0);
    }
    for (unsigned index = 1; index <= 6; ++index) {
        Fixture number, insert;
        number.failNumber = insert.failInsert = index;
        reject(number, Result::NumberAllocation, index, 0);
        reject(insert, Result::Insert, index, 0);
    }
    Fixture publish;
    publish.failPublish = true;
    reject(publish, Result::Publish, 6, 1);
}

void startPolicy()
{
    for (unsigned hz : {0U, 60U}) {
        Fixture f;
        assert(publishFixedForStart(f, hz));
        assert(!f.live && f.publications == 1 && f.registry.size() == 6);
        media(&f.registry, 60, 60, 60);
    }
    for (unsigned hz : {59U, 120U, 241U}) {
        Fixture f;
        assert(!publishFixedForStart(f, hz));
        assert(!f.live && f.ns.empty() && !f.publications);
    }
    Fixture f;
    f.failPublish = true;
    assert(!publishFixedForStart(f, 0));
    assert(!f.live && f.publications == 1 && f.registry.at("previous").value == 42);
}
}

int main()
{
    readers();
    failures();
    startPolicy();
    std::puts("20H392 refresh formatter, reader models and publication rejection: PASS");
}
