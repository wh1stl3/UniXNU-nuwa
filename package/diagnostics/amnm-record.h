#ifndef NUWA_AMNM_RECORD_H
#define NUWA_AMNM_RECORD_H

#include <stdint.h>
#include <stddef.h>

enum { AMNM_SLOT_COUNT = 16, AMNM_PAYLOAD_WORDS = 10 };
enum { AMNM_EVENT_INPUT = 3 };
enum { AMNM_EVENT_STORE = 4, AMNM_EVENT_BRANCH = 5 };
enum { AMNM_EVENT_ENTRY = 1, AMNM_EVENT_PRECALL = 2 };

struct amnm_entry_payload {
    uint64_t entry_sp, entry_fp, entry_lr;
};

struct amnm_precall_payload {
    uint64_t callee, runtime, id, output, caller_sp, caller_fp, return_pc;
};

struct amnm_input_payload {
    uint64_t input_u32;
    uint64_t id;
    uint64_t output;
    uint64_t reader_sp;
    uint64_t reader_fp;
    uint64_t caller_fp;
    uint64_t caller_lr;
};

struct amnm_store_payload {
    uint64_t byte_value, target, id, reader_sp, reader_fp, caller_fp, caller_lr;
};

struct amnm_branch_payload {
    uint64_t input_u32, initializer_sp, initializer_fp;
};

struct amnm_slot {
    uint64_t commit;
    uint64_t kind;
    union {
        uint64_t payload[AMNM_PAYLOAD_WORDS];
        struct amnm_input_payload input;
        struct amnm_store_payload store;
        struct amnm_branch_payload branch;
        struct amnm_entry_payload entry;
        struct amnm_precall_payload precall;
    };
};

struct amnm_log {
    uint64_t next_sequence;
    uint8_t header_reserved[120];
    struct amnm_slot slots[AMNM_SLOT_COUNT];
    char summary[256];
};

/* Caller-owned storage. Only committed records below count are meaningful. */
struct amnm_snapshot {
    uint64_t count;
    uint64_t n1, n2;
    unsigned loss;
    struct amnm_slot slots[AMNM_SLOT_COUNT];
};

enum { AMNM_LOSS_OVERFLOW = 1, AMNM_LOSS_COMMIT = 2, AMNM_LOSS_RACE = 4,
       AMNM_LOSS_COUNT = 8, AMNM_LOSS_ORDER = 16, AMNM_LOSS_BINDING = 32,
       AMNM_LOSS_FRAME = 64, AMNM_LOSS_VALUE = 128 };

struct amnm_binding { uint64_t reader, flag, return_pc; };
struct amnm_association { unsigned loss; uint32_t input, store, branch; };

enum amnm_snapshot_status {
    AMNM_SNAPSHOT_COMPLETE = 0,
    AMNM_SNAPSHOT_LOST = 1
};

_Static_assert(sizeof(struct amnm_slot) == 96, "AMNM slot size");
_Static_assert(sizeof(struct amnm_input_payload) <= sizeof(((struct amnm_slot *)0)->payload), "INPUT fits");
_Static_assert(offsetof(struct amnm_slot, kind) == 8, "INPUT kind offset");
_Static_assert(offsetof(struct amnm_slot, payload) == 16, "INPUT payload offset");
_Static_assert(offsetof(struct amnm_slot, input) == 16 && offsetof(struct amnm_slot, store) == 16 && offsetof(struct amnm_slot, branch) == 16, "event union offset");
_Static_assert(offsetof(struct amnm_slot, entry) == 16 && offsetof(struct amnm_slot, precall) == 16, "ENTRY/PRECALL union offset");
_Static_assert(sizeof(struct amnm_entry_payload) <= sizeof(((struct amnm_slot *)0)->payload), "ENTRY fits");
_Static_assert(offsetof(struct amnm_entry_payload, entry_sp) == 0 && offsetof(struct amnm_entry_payload, entry_fp) == 8 && offsetof(struct amnm_entry_payload, entry_lr) == 16, "ENTRY fields");
_Static_assert(sizeof(struct amnm_precall_payload) <= sizeof(((struct amnm_slot *)0)->payload), "PRECALL fits");
_Static_assert(offsetof(struct amnm_precall_payload, callee) == 0 && offsetof(struct amnm_precall_payload, runtime) == 8 && offsetof(struct amnm_precall_payload, id) == 16 && offsetof(struct amnm_precall_payload, output) == 24, "PRECALL args");
_Static_assert(offsetof(struct amnm_precall_payload, caller_sp) == 32 && offsetof(struct amnm_precall_payload, caller_fp) == 40 && offsetof(struct amnm_precall_payload, return_pc) == 48, "PRECALL frame");
_Static_assert(offsetof(struct amnm_input_payload, input_u32) == 0, "INPUT value offset");
_Static_assert(offsetof(struct amnm_input_payload, id) == 8, "INPUT id offset");
_Static_assert(offsetof(struct amnm_input_payload, output) == 16, "INPUT output offset");
_Static_assert(offsetof(struct amnm_input_payload, reader_sp) == 24, "INPUT sp offset");
_Static_assert(offsetof(struct amnm_input_payload, reader_fp) == 32, "INPUT fp offset");
_Static_assert(offsetof(struct amnm_input_payload, caller_fp) == 40, "INPUT caller fp offset");
_Static_assert(offsetof(struct amnm_input_payload, caller_lr) == 48, "INPUT caller lr offset");
_Static_assert(sizeof(struct amnm_store_payload) <= sizeof(((struct amnm_slot *)0)->payload), "STORE fits");
_Static_assert(offsetof(struct amnm_store_payload, byte_value) == 0 && offsetof(struct amnm_store_payload, target) == 8 && offsetof(struct amnm_store_payload, id) == 16, "STORE fields");
_Static_assert(offsetof(struct amnm_store_payload, reader_sp) == 24 && offsetof(struct amnm_store_payload, reader_fp) == 32 && offsetof(struct amnm_store_payload, caller_fp) == 40 && offsetof(struct amnm_store_payload, caller_lr) == 48, "STORE frame");
_Static_assert(sizeof(struct amnm_branch_payload) <= sizeof(((struct amnm_slot *)0)->payload), "BRANCH fits");
_Static_assert(offsetof(struct amnm_branch_payload, input_u32) == 0 && offsetof(struct amnm_branch_payload, initializer_sp) == 8 && offsetof(struct amnm_branch_payload, initializer_fp) == 16, "BRANCH fields");
_Static_assert(offsetof(struct amnm_log, slots) == 128, "AMNM header size");
_Static_assert(sizeof(struct amnm_log) == 1920, "AMNM RW budget");

/* Tickets are never reused. NULL means overflow; the ticket remains consumed. */
struct amnm_slot *amnm_reserve(struct amnm_log *, uint64_t *ticket);
void amnm_commit(struct amnm_slot *, uint64_t ticket);
enum amnm_snapshot_status amnm_snapshot_read(const struct amnm_log *,
    struct amnm_snapshot *);
struct amnm_association amnm_associate(const struct amnm_snapshot *,
    const struct amnm_binding *);
size_t amnm_summary(char *, size_t, const struct amnm_snapshot *,
    const struct amnm_association *);

#endif
