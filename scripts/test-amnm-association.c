#include "../package/diagnostics/amnm-record.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

static struct amnm_log *race_log;
void amnm_test_before_n2(void) {
    if (race_log) __atomic_fetch_add(&race_log->next_sequence, 1, __ATOMIC_RELAXED);
}
static const struct amnm_binding binding = { 0x777777, 0x888888, 0x999999 };
static void setup(struct amnm_log *log, unsigned input, unsigned store, unsigned branch) {
    memset(log, 0, sizeof(*log));
    log->next_sequence = 5;
    for (unsigned n = 0; n < 5; ++n) { log->slots[n].commit = n+1; log->slots[n].kind = n+1; }
    log->slots[0].entry = (struct amnm_entry_payload){0x10000, 0xaaaa, 0xbbbb};
    log->slots[1].precall = (struct amnm_precall_payload){binding.reader, 0x333, 12, binding.flag, 0xfe70, 0xfff0, binding.return_pc};
    log->slots[2].input = (struct amnm_input_payload){input,12,binding.flag,0xfe30,0xfe60,0xfff0,binding.return_pc};
    log->slots[3].store = (struct amnm_store_payload){store,binding.flag,12,0xfe30,0xfe60,0xfff0,binding.return_pc};
    log->slots[4].branch = (struct amnm_branch_payload){branch,0xfe70,0xfff0};
}
int main(void) {
    struct amnm_log log;
    struct amnm_snapshot s;
    struct amnm_association a;
    char buf[256];
    for (unsigned input = 0; input < 2; ++input) {
        setup(&log, input, input ? 0 : 1, input ? 0 : 1);
        assert(amnm_snapshot_read(&log, &s) == AMNM_SNAPSHOT_COMPLETE);
        a = amnm_associate(&s, &binding);
        assert(!a.loss && a.input == input && a.store == (input ? 0u : 1u));
        assert(amnm_summary(buf, sizeof(buf), &s, &a) < sizeof(buf));
        assert(strstr(buf, "I=1") && strstr(buf, "U=") && strstr(buf, "S=") && strstr(buf, "B="));
    }
    setup(&log, 1, 1, 0);
    assert(!amnm_snapshot_read(&log, &s));
    a = amnm_associate(&s, &binding);
    assert(!a.loss && a.store == 1 && a.branch == 0);
    /* Each checked payload field, including both saved frame copies. */
    const unsigned slots[] = {0,1,1,1,1,1,1,2,2,2,2,2,2,3,3,3,3,3,3,4,4};
    const unsigned words[] = {0,0,2,3,4,5,6,1,2,3,4,5,6,1,2,3,4,5,6,1,2};
    for (unsigned k = 0; k < sizeof(slots)/sizeof(slots[0]); ++k) {
        struct amnm_snapshot bad = s;
        bad.slots[slots[k]].payload[words[k]] ^= 1;
        assert(amnm_associate(&bad, &binding).loss);
    }
    struct amnm_snapshot bad = s;
    bad.slots[2].input.input_u32 = 0x100000000ULL;
    assert(amnm_associate(&bad, &binding).loss & AMNM_LOSS_VALUE);
    bad = s; bad.slots[3].store.byte_value = 256;
    assert(amnm_associate(&bad, &binding).loss & AMNM_LOSS_VALUE);
    bad = s; bad.slots[4].branch.input_u32 = 0x100000000ULL;
    assert(amnm_associate(&bad, &binding).loss & AMNM_LOSS_VALUE);
    bad = s; bad.slots[2].kind = AMNM_EVENT_ENTRY;
    assert(amnm_associate(&bad, &binding).loss & AMNM_LOSS_ORDER);
    bad = s; bad.slots[3].commit = 0;
    assert(amnm_associate(&bad, &binding).loss & AMNM_LOSS_COMMIT);
    setup(&log, 0, 1, 1); log.next_sequence = 6;
    log.slots[5].commit = 6; log.slots[5].kind = AMNM_EVENT_ENTRY;
    assert(!amnm_snapshot_read(&log, &s));
    assert(amnm_associate(&s, &binding).loss & AMNM_LOSS_COUNT);
    setup(&log, 0, 1, 1); log.slots[2].commit = 0;
    assert(amnm_snapshot_read(&log, &s) == AMNM_SNAPSHOT_LOST);
    assert(amnm_associate(&s, &binding).loss & AMNM_LOSS_COMMIT);
    setup(&log, 0, 1, 1); log.next_sequence = 17;
    assert(amnm_snapshot_read(&log, &s) == AMNM_SNAPSHOT_LOST);
    assert(amnm_associate(&s, &binding).loss & AMNM_LOSS_OVERFLOW);
    setup(&log, 0, 1, 1); race_log = &log;
    assert(amnm_snapshot_read(&log, &s) == AMNM_SNAPSHOT_LOST);
    race_log = 0;
    assert(amnm_associate(&s, &binding).loss & AMNM_LOSS_RACE);
    setup(&log, 0, 1, 1); assert(!amnm_snapshot_read(&log, &s));
    log.next_sequence = 6; /* outside snapshot: no claim about later uniqueness */
    a = amnm_associate(&s, &binding); assert(!a.loss);
    struct { unsigned char before; char small[4]; unsigned char after; } guard = {0x77,{0},0x88};
    assert(amnm_summary(guard.small, sizeof(guard.small), &s, &a) >= sizeof(guard.small));
    assert(guard.before == 0x77 && guard.after == 0x88 && guard.small[3] == 0);
    s.n1 = UINT64_MAX; s.n2 = UINT64_MAX;
    a.input = UINT32_MAX; a.store = UINT32_MAX; a.branch = UINT32_MAX;
    a.loss = 0;
    size_t needed = amnm_summary(buf, sizeof(buf), &s, &a);
    assert(needed < sizeof(buf) && strlen(buf) == needed);
    assert(strstr(buf, "ffffffffffffffff/ffffffffffffffff"));
    char exact[256];
    assert(amnm_summary(exact, needed + 1, &s, &a) == needed && !strcmp(buf, exact));
    assert(amnm_summary(exact, needed, &s, &a) == needed && exact[needed-1] == 0);
    puts("PASS association, snapshot loss/race and summary bounds");
}
