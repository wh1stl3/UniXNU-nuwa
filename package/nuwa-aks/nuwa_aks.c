/*
 * r31: board glue for the unchanged UniXNU AppleKeyStoreState component
 * (package/nuwa-aks/SOURCE.md).  The component is an IOKit service plus a user client for the
 * AppleKeyStore selector ABI; it asks the board for six things, all implemented here.
 *
 * Not hardware data protection: the wrap key is SHA-256("UniXNU AppleKeyStore v1" || identity)
 * with the identity the Apple ADT carries in /chosen (the same value every boot), so a keychain
 * item survives a restart and nothing protects the key beyond that identity.  Keybag, passcode
 * and reference-key operations stay unsupported; that is what the component documents.
 *
 * Everything is gated by the boot argument aks=1 (the component's documented switch): with no
 * argument the class is still registered (harmless bookkeeping) but no instance is published,
 * so an r31 image behaves like r30 unless the argument is on the command line.
 */
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/proc.h>
#include <pexpert/pexpert.h>
#include <libkern/libkern.h>

/* Page and console state.  0 = off/not run, 1 = class registered, 2 = service started. */
volatile uint32_t nuwa_aks_state;
volatile uint32_t nuwa_aks_opens;
volatile uint32_t nuwa_aks_open_refused;
volatile uint32_t nuwa_aks_calls;
volatile uint32_t nuwa_aks_last_selector;
volatile int32_t nuwa_aks_last_result;
/* r32: the last four dispatch results, newest at (ring_count - 1) & 3.  The ring is written
 * from native_aks_call(), which the component's user client calls at the END of every
 * externalMethod() with the selector it was given and the IOReturn it returned - i.e. the
 * dispatch point itself, without touching the vendored file.  Together with the page line the
 * ring answers "which selector did keybagd walk up to, and what did it get back". */
volatile uint32_t nuwa_aks_ring_selector[4];
volatile int32_t nuwa_aks_ring_result[4];
volatile uint32_t nuwa_aks_ring_count;
volatile uint32_t nuwa_aks_identity_bytes;

static int nuwa_aks_arg = -1;      /* -1 unknown, 0 off, 1 on */
static int nuwa_aks_registered;
static int nuwa_aks_created;

extern int native_keyevents_register_class(void);
extern int native_keyevents_start_service(void);

int
native_aks_state_enabled(void)
{
	unsigned on = 0;

	if (nuwa_aks_arg < 0) {
		nuwa_aks_arg = (PE_parse_boot_argn("aks", &on, sizeof(on)) && on != 0) ? 1 : 0;
	}
	return nuwa_aks_arg;
}

uint32_t
native_aks_lock_state(void)
{
	/* No passcode and no lock: the component turns 0 into "unlocked since boot" for the
	 * device-state query, and keybagd then needs no systembag.kb. */
	return 0;
}

void
native_aks_call(uint32_t selector, int32_t result)
{
	uint32_t slot = nuwa_aks_ring_count & 3u;

	/* r32: the dispatch-side ring.  Record first, then publish the scalar summary, so a page
	 * read that sees a new last_selector also sees the matching ring entry. */
	nuwa_aks_ring_selector[slot] = selector;
	nuwa_aks_ring_result[slot] = result;
	nuwa_aks_ring_count = nuwa_aks_ring_count + 1;
	nuwa_aks_calls = nuwa_aks_calls + 1;
	nuwa_aks_last_selector = selector;
	nuwa_aks_last_result = result;
}

void
native_aks_opened(void)
{
	nuwa_aks_opens = nuwa_aks_opens + 1;
	if (nuwa_aks_opens == 1) {
		printf("nuwa: aks user client opened\n");
	}
}

void
native_keyevents_open_refused(void)
{
	nuwa_aks_open_refused = nuwa_aks_open_refused + 1;
	if (nuwa_aks_open_refused == 1) {
		printf("nuwa: aks open refused (not started or aks=0)\n");
	}
}

/* Bounded read-only walk of the Apple ADT the loader passed: per node a property count and a
 * child count, then per property a 32-byte name, a length and the value (4-byte aligned); a
 * node's name is its "name" property.  The same layout the Data seed reader walks.  No
 * allocation; the property list of one node is capped at 32 entries. */
struct nuwa_aks_prop {
	uint32_t name_offset;
	uint32_t value_offset;
	uint32_t length;
};

struct nuwa_aks_adt {
	const uint8_t *data;
	uint32_t size;
	const char *want;
	const uint8_t *value;
	uint32_t length;
	int found;
};

static uint32_t
nuwa_aks_adt_u32(const uint8_t *p)
{
	return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
	    ((uint32_t)p[3] << 24);
}

static void
nuwa_aks_adt_walk(struct nuwa_aks_adt *w, uint32_t *offset, unsigned depth, int in_chosen)
{
	struct nuwa_aks_prop props[32];
	uint32_t prop_count, children, index, count = 0;
	const uint8_t *name = NULL;
	uint32_t name_len = 0;
	int is_chosen;

	if (depth > 32 || w->size - *offset < 8) {
		return;
	}
	prop_count = nuwa_aks_adt_u32(w->data + *offset);
	children = nuwa_aks_adt_u32(w->data + *offset + 4);
	*offset += 8;
	if (prop_count > (w->size - *offset) / 36) {
		return;
	}
	for (index = 0; index < prop_count; index++) {
		const uint8_t *prop = w->data + *offset;
		uint32_t len;

		if (w->size - *offset < 36) {
			return;
		}
		len = nuwa_aks_adt_u32(prop + 32);
		*offset += 36;
		if (len > w->size - *offset) {
			return;
		}
		if (count < 32) {
			props[count].name_offset = (uint32_t)(prop - w->data);
			props[count].value_offset = *offset;
			props[count].length = len;
			count++;
		}
		*offset += len;
		*offset = (*offset + 3) & ~3u;
	}
	/* This node's own name decides whether its properties are the ones we want. */
	for (index = 0; index < count; index++) {
		const char *pname = (const char *)(w->data + props[index].name_offset);
		if (!strncmp(pname, "name", 32)) {
			name = w->data + props[index].value_offset;
			name_len = props[index].length;
		}
	}
	is_chosen = (name != NULL && name_len == 7 && !memcmp(name, "chosen", 7));
	if ((depth == 1 && is_chosen) || in_chosen) {
		for (index = 0; index < count && !w->found; index++) {
			const char *pname = (const char *)(w->data + props[index].name_offset);
			if (!strncmp(pname, w->want, 32)) {
				w->value = w->data + props[index].value_offset;
				w->length = props[index].length;
				w->found = 1;
			}
		}
	}
	if (children > (w->size - *offset) / 8) {
		return;
	}
	for (index = 0; index < children; index++) {
		nuwa_aks_adt_walk(w, offset, depth + 1, in_chosen || is_chosen);
	}
}

static int
nuwa_aks_adt_lookup(const char *property, const uint8_t **value, uint32_t *length)
{
	struct nuwa_aks_adt w = { NULL, 0, property, NULL, 0, 0 };
	uint32_t offset = 0;

	if (PE_state.deviceTreeHead == NULL || PE_state.deviceTreeSize < 8) {
		return 0;
	}
	w.data = (const uint8_t *)PE_state.deviceTreeHead;
	w.size = (uint32_t)PE_state.deviceTreeSize;
	nuwa_aks_adt_walk(&w, &offset, 0, 0);
	if (!w.found) {
		return 0;
	}
	*value = w.value;
	*length = w.length;
	return 1;
}

size_t
native_aks_device_id(uint8_t *out, size_t capacity)
{
	const uint8_t *value = NULL;
	uint32_t length = 0;
	size_t n, i;

	if (out == NULL || capacity < 4) {
		return 0;
	}
	/* 8 bytes of unique-chip-id first: that is the identity the payload's ADT carries and it
	 * is the same on every boot, so the key (and the keychain) is stable. */
	if (nuwa_aks_adt_lookup("unique-chip-id", &value, &length) && length == 8) {
		n = 8;
	} else if (nuwa_aks_adt_lookup("chip-id", &value, &length) && length == 4) {
		n = 4;
	} else {
		nuwa_aks_identity_bytes = 0;
		return 0;
	}
	if (n > capacity) {
		n = capacity;
	}
	for (i = 0; i < n; i++) {
		out[i] = value[i];
	}
	nuwa_aks_identity_bytes = (uint32_t)n;
	return n;
}

/* Early: inside the same window as the RamBlock registration (after IOService::setPlatform(),
 * where OSMetaClass::preModLoad()/postModLoad() work). */
void
nuwa_aks_init(void)
{
	if (nuwa_aks_registered) {
		return;
	}
	nuwa_aks_registered = 1;
	if (!native_keyevents_register_class()) {
		printf("nuwa: aks class registration failed\n");
		return;
	}
	nuwa_aks_state = 1;
	printf("nuwa: aks class registered (enabled=%d)\n", native_aks_state_enabled());
}

/* Late: from the Data mount, i.e. after bsd_init()/bsd_autoconf(), before initproc exec. */
int
nuwa_aks_create(void)
{
	int result;

	if (nuwa_aks_created) {
		return 0;
	}
	nuwa_aks_created = 1;
	if (!native_aks_state_enabled()) {
		printf("nuwa: aks not created (aks=1 not given)\n");
		return 0;
	}
	result = native_keyevents_start_service();
	if (result > 0) {
		nuwa_aks_state = 2;
		printf("nuwa: aks started identity_bytes=%u\n", (unsigned)nuwa_aks_identity_bytes);
	} else {
		printf("nuwa: aks create failed rc=%d identity_bytes=%u\n", result,
		    (unsigned)nuwa_aks_identity_bytes);
	}
	return result;
}
