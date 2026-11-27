/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#ifndef NUWA_SB_THREADS_H
#define NUWA_SB_THREADS_H

enum { SBTH_LIMIT = 128, SBTH_TOP = 4, SBTH_ROWS = 1 + SBTH_TOP };
enum { SBTH_NONE, SBTH_DENIED, SBTH_OK };

struct sbth_pc {
	uint64_t pc, lr, sp;
	unsigned count;
};

struct sbth_walk {
	unsigned n, distinct;
	struct sbth_pc pc[SBTH_LIMIT];
};

/* Single producer (process monitor). Readers never wait, take a lock or
 * inspect a thread; a panic that interrupts publication can show denied.
 * The SC bracket covers every shared word, including the payload. */
static struct {
	uint64_t seq, summary;
	uint64_t pc[SBTH_TOP], lr[SBTH_TOP], sp[SBTH_TOP], count[SBTH_TOP];
} sbth_snapshot;

#define SBTH_GET(word) __atomic_load_n(&(word), __ATOMIC_SEQ_CST)
#define SBTH_PUT(word, value) __atomic_store_n(&(word), (value), __ATOMIC_SEQ_CST)

static void
sbth_add(struct sbth_walk *w, uint64_t pc, uint64_t lr, uint64_t sp)
{
	++w->n;
	for (unsigned i = 0; i < w->distinct; ++i) {
		if (w->pc[i].pc == pc) {
			++w->pc[i].count;
			return;
		}
	}
	w->pc[w->distinct++] = (struct sbth_pc){ pc, lr, sp, 1 };
}

static void
sbth_publish(unsigned status, struct sbth_walk *w)
{
	struct sbth_pc top[SBTH_TOP] = { 0 };
	unsigned count = 0;
	uint64_t summary = status;
	if (status == SBTH_OK) {
		for (unsigned i = 0; i < w->distinct; ++i) {
			const struct sbth_pc *src = &w->pc[i];
			unsigned j = 0;
			while (j < count && (top[j].count > src->count ||
			    (top[j].count == src->count && top[j].pc < src->pc))) {
				++j;
			}
			if (j == SBTH_TOP) {
				continue;
			}
			if (count < SBTH_TOP) {
				++count;
			}
			for (unsigned k = count - 1; k > j; --k) {
				top[k] = top[k - 1];
			}
			top[j] = *src;
		}
		summary |= (uint64_t)count << 8 | (uint64_t)w->n << 16;
	}
	uint64_t seq = SBTH_GET(sbth_snapshot.seq);
	SBTH_PUT(sbth_snapshot.seq, seq + 1);
	for (unsigned i = 0; i < count; ++i) {
		SBTH_PUT(sbth_snapshot.pc[i], top[i].pc);
		SBTH_PUT(sbth_snapshot.lr[i], top[i].lr);
		SBTH_PUT(sbth_snapshot.sp[i], top[i].sp);
		SBTH_PUT(sbth_snapshot.count[i], top[i].count);
	}
	SBTH_PUT(sbth_snapshot.summary, summary);
	SBTH_PUT(sbth_snapshot.seq, seq + 2);
}

unsigned nuwa_sbth_rows(char (*rows)[120], unsigned limit);

unsigned
nuwa_sbth_rows(char (*rows)[120], unsigned limit)
{
	if (!limit) {
		return 0;
	}
	uint64_t seq = SBTH_GET(sbth_snapshot.seq);
	uint64_t summary = SBTH_GET(sbth_snapshot.summary);
	unsigned count = (summary >> 8) & 0xff;
	struct sbth_pc top[SBTH_TOP];
	if (count >= limit) {
		count = limit - 1;
	}
	for (unsigned i = 0; i < count; ++i) {
		top[i] = (struct sbth_pc){ SBTH_GET(sbth_snapshot.pc[i]),
			SBTH_GET(sbth_snapshot.lr[i]), SBTH_GET(sbth_snapshot.sp[i]),
			(unsigned)SBTH_GET(sbth_snapshot.count[i]) };
	}
	if ((seq & 1) || seq != SBTH_GET(sbth_snapshot.seq) || (summary & 0xff) == SBTH_DENIED) {
		snprintf(rows[0], 120, "SBTH denied");
		return 1;
	}
	if ((summary & 0xff) == SBTH_NONE) {
		snprintf(rows[0], 120, "SBTH none");
		return 1;
	}
	snprintf(rows[0], 120, "SBTH n=%u", (unsigned)(summary >> 16) & 0xff);
	for (unsigned i = 0; i < count; ++i) {
		snprintf(rows[i + 1], 120, "SBTH pc=%llx x%u non-atomic lr=%llx sp=%llx",
		    (unsigned long long)top[i].pc, top[i].count, (unsigned long long)top[i].lr,
		    (unsigned long long)top[i].sp);
	}
	return 1 + count;
}

#undef SBTH_GET
#undef SBTH_PUT
#endif
