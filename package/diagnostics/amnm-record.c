#include "amnm-record.h"

struct amnm_slot *
amnm_reserve(struct amnm_log *log, uint64_t *ticket)
{
    uint64_t n = __atomic_fetch_add(&log->next_sequence, 1, __ATOMIC_ACQ_REL);
    *ticket = n;
    return n < AMNM_SLOT_COUNT ? &log->slots[n] : 0;
}

void
amnm_commit(struct amnm_slot *slot, uint64_t ticket)
{
    __atomic_store_n(&slot->commit, ticket + 1, __ATOMIC_RELEASE);
}

enum amnm_snapshot_status
amnm_snapshot_read(const struct amnm_log *log, struct amnm_snapshot *snapshot)
{
    uint64_t n1 = __atomic_load_n(&log->next_sequence, __ATOMIC_ACQUIRE);
    unsigned loss = n1 > AMNM_SLOT_COUNT ? AMNM_LOSS_OVERFLOW : 0;
    uint64_t count = loss ? AMNM_SLOT_COUNT : n1;

    snapshot->n1 = n1;
    snapshot->count = count;
    for (uint64_t i = 0; i < count; ++i) {
        const struct amnm_slot *src = &log->slots[i];
        struct amnm_slot *dst = &snapshot->slots[i];
        uint64_t commit = __atomic_load_n(&src->commit, __ATOMIC_ACQUIRE);
        dst->commit = commit;
        if (commit != i + 1) {
            loss |= AMNM_LOSS_COMMIT;
            continue;
        }
        dst->kind = src->kind;
        for (unsigned j = 0; j < AMNM_PAYLOAD_WORDS; ++j)
            dst->payload[j] = src->payload[j];
    }
#ifdef AMNM_TEST_SNAPSHOT_HOOK
    extern void amnm_test_before_n2(void);
    amnm_test_before_n2();
#endif
    uint64_t n2 = __atomic_load_n(&log->next_sequence, __ATOMIC_ACQUIRE);
    if (n1 != n2) loss |= AMNM_LOSS_RACE;
    snapshot->n2 = n2;
    snapshot->loss = loss;
    return loss ? AMNM_SNAPSHOT_LOST : AMNM_SNAPSHOT_COMPLETE;
}

struct amnm_association
amnm_associate(const struct amnm_snapshot *s, const struct amnm_binding *b)
{
    struct amnm_association a = {0};
    a.loss = s->loss;
    if (s->n1 != s->n2) a.loss |= AMNM_LOSS_RACE;
    if (s->n1 > AMNM_SLOT_COUNT || s->n2 > AMNM_SLOT_COUNT) a.loss |= AMNM_LOSS_OVERFLOW;
    if (s->count != 5 || s->n1 != 5) a.loss |= AMNM_LOSS_COUNT;
    if (a.loss) return a;
    for (unsigned i = 0; i < 5; ++i) {
        if (s->slots[i].commit != i + 1) a.loss |= AMNM_LOSS_COMMIT;
        if (s->slots[i].kind != i + 1) a.loss |= AMNM_LOSS_ORDER;
    }
    if (a.loss) return a;
    const struct amnm_entry_payload *e = &s->slots[0].entry;
    const struct amnm_precall_payload *p = &s->slots[1].precall;
    const struct amnm_input_payload *i = &s->slots[2].input;
    const struct amnm_store_payload *t = &s->slots[3].store;
    const struct amnm_branch_payload *r = &s->slots[4].branch;
    if (!b->reader || !b->flag || !b->return_pc || p->callee != b->reader ||
        p->return_pc != b->return_pc || p->id != 12 || i->id != 12 || t->id != 12 ||
        p->output != b->flag || i->output != b->flag || t->target != b->flag)
        a.loss |= AMNM_LOSS_BINDING;
    if (e->entry_sp < 0x190 || p->caller_sp < 0x40 ||
        p->caller_sp != e->entry_sp - 0x190 || p->caller_fp != e->entry_sp - 0x10 ||
        i->reader_sp != p->caller_sp - 0x40 || i->reader_fp != i->reader_sp + 0x30 ||
        i->caller_fp != p->caller_fp || i->caller_lr != p->return_pc ||
        t->reader_sp != i->reader_sp || t->reader_fp != i->reader_fp ||
        t->caller_fp != i->caller_fp || t->caller_lr != i->caller_lr ||
        r->initializer_sp != p->caller_sp || r->initializer_fp != p->caller_fp)
        a.loss |= AMNM_LOSS_FRAME;
    if (i->input_u32 > UINT32_MAX || t->byte_value > UINT8_MAX || r->input_u32 > UINT32_MAX)
        a.loss |= AMNM_LOSS_VALUE;
    if (!a.loss) {
        a.input = (uint32_t)i->input_u32;
        a.store = (uint32_t)t->byte_value;
        a.branch = (uint32_t)r->input_u32;
    }
    return a;
}

static void summary_put(char *dst, size_t cap, size_t *n, char ch)
{
    if (cap && *n + 1 < cap) dst[*n] = ch;
    ++*n;
}
static void summary_hex(char *dst, size_t cap, size_t *n, uint64_t value)
{
    int started = 0;
    for (int shift = 60; shift >= 0; shift -= 4) {
        unsigned v = (unsigned)((value >> shift) & 15);
        if (v || started || !shift) { summary_put(dst, cap, n, "0123456789abcdef"[v]); started = 1; }
    }
}
size_t amnm_summary(char *dst, size_t cap, const struct amnm_snapshot *s,
                    const struct amnm_association *a)
{
    size_t n = 0;
#define C(ch) summary_put(dst, cap, &n, (ch))
#define H(x) summary_hex(dst, cap, &n, (x))
    C('\n'); C('C'); C('='); H(s->n1); C('/'); H(s->n2);
    C(' '); C('L'); C('='); H(a->loss);
    C(' '); C('I'); C('='); C(a->loss ? '0' : '1');
    if (!a->loss) {
        C(' '); C('U'); C('='); H(a->input);
        C(' '); C('S'); C('='); H(a->store);
        C(' '); C('B'); C('='); H(a->branch);
    }
    if (cap) dst[n < cap ? n : cap - 1] = 0;
#undef C
#undef H
    return n;
}
