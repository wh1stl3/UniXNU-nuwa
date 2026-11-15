#include "../package/diagnostics/amnm-record.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    struct amnm_log log = {0};
    struct amnm_snapshot snapshot = {0};
    uint64_t a, b;
    assert(amnm_snapshot_read(&log, &snapshot) == AMNM_SNAPSHOT_COMPLETE);
    assert(snapshot.count == 0);
    struct amnm_slot *first = amnm_reserve(&log, &a);
    assert(first && a == 0);
    first->kind = 42;
    first->payload[9] = UINT64_MAX;
    assert(amnm_snapshot_read(&log, &snapshot) == AMNM_SNAPSHOT_LOST);
    struct amnm_slot *second = amnm_reserve(&log, &b);
    assert(second && b == 1);
    second->kind = 43;
    amnm_commit(second, b);
    assert(amnm_snapshot_read(&log, &snapshot) == AMNM_SNAPSHOT_LOST);
    amnm_commit(first, a);
    assert(amnm_snapshot_read(&log, &snapshot) == AMNM_SNAPSHOT_COMPLETE);
    assert(snapshot.count == 2 && snapshot.slots[0].kind == 42);
    assert(snapshot.slots[0].payload[9] == UINT64_MAX);
    assert(snapshot.slots[1].kind == 43);
    for (unsigned i = 2; i < AMNM_SLOT_COUNT; ++i) {
        uint64_t ticket;
        struct amnm_slot *slot = amnm_reserve(&log, &ticket);
        assert(slot && ticket == i);
        amnm_commit(slot, ticket);
    }
    assert(amnm_snapshot_read(&log, &snapshot) == AMNM_SNAPSHOT_COMPLETE);
    assert(!amnm_reserve(&log, &a) && a == AMNM_SLOT_COUNT);
    assert(amnm_snapshot_read(&log, &snapshot) == AMNM_SNAPSHOT_LOST);
    puts("snapshot basic tests passed");
    return 0;
}
