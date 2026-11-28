// SPDX-License-Identifier: BSD-2-Clause-Patent
/*
 * nuwa r13: mount the ram-disk Data volume at /private/var, and the one-shot
 * initializer call for the NativeRamBlock driver object.
 *
 * Shape (same as package/nuwa-systemos/nuwa_systemos.c, i.e. the r12 pattern, not the
 * official offline-owner-systemos-mount.patch body):
 *   * obtain the Data volume from the typed provider
 *     native_ram_block_volume_seed(uuid, ...) - that call also opens the persistent
 *     store window and, on the first boot with sheng-data-reset=1, formats the overlay
 *     header, so it must happen before mount();
 *   * mount("apfs", "/private/var", 0, <0x150-byte user-mount payload>);
 *   * verify device identity, f_fstypename == "apfs", and the read/write direction;
 *   * every failure records a stage/errno and returns - no panic.  The boot progress
 *     page shows it in boot_progress_ext[0..1].
 *
 * boot-arg `nuwa-data-ro=1` mounts the volume read-only: that proves Apple's APFS
 * accepts the seed without letting APFS write anything to the overlay.  launchd cannot
 * make progress on a read-only /private/var, so this is a diagnostic mode only.
 *
 * The mount payload offsets are the ones the official patch qualified:
 * [0..8) device path pointer, [8..16) mount flags, [16..18) mode = 1,
 * [0x144)/[0x148) anonymous owner = 99.  The scratch page is the one load_init_program()
 * allocated; the SystemOS mount (when built in) uses the same page, sequentially.
 *
 * Nothing here runs before load_init_program(): no constructor, no __mod_init_func.
 */
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/proc.h>
#include <sys/proc_internal.h>
#include <sys/mount.h>
#include <sys/mount_internal.h>
#include <sys/vnode.h>
#include <sys/vnode_internal.h>
#include <sys/sysproto.h>
#include <sys/errno.h>
#include <pexpert/pexpert.h>
#include <libkern/libkern.h>

#ifndef XNU_NUWA_DATA_VOLUME_UUID
/* Data seed volume of out/nuwa-data-seed-linux-20261115-r1/data.dbr (APSB +0xC0). */
#define XNU_NUWA_DATA_VOLUME_UUID "C7DE20F1-3A70-482B-B14F-801EE1513E3D"
#endif
#define NUWA_DATA_MOUNT_POINT "/private/var"

/* Provided by the RamBlock component (drivers/RamBlock/NativeRamBlock.cpp:456). */
extern int native_ram_block_volume_seed(const char *uuid, dev_t *device, char *path, size_t size,
    uint64_t *base, uint64_t *bytes, uint8_t digest[32]);
/* r18 observation: is the RamBlock disk object built at all (its own readiness flag), and
 * how big the seed the driver published is.  Both are weak: a build without the driver
 * still links, the row just shows pub=0. */
extern volatile uint32_t native_ram_block_ready __attribute__((weak_import));
extern volatile uint64_t native_ram_block_bytes __attribute__((weak_import));
/* r24: why the seed lookup failed, from the forked RamBlock driver (package/nuwa-ramblock):
 * 1 = the disk object is not ready, 2 = no IOMedia matched the volume UUID, 3 = a match lacks
 * its UUID/BSD properties, 4 = no NativeRamBlock in the provider chain, 5 = the disk has no
 * usable seed.  Weak: a build without the fork reports 1, i.e. the old two-state answer. */
extern volatile uint32_t native_ram_block_seed_reason __attribute__((weak_import));

/* r25: the same facts, published as globals for the diagnostic page.  On this board the
 * console is not captured by the progress page, so anything that only goes to printf() is
 * lost; these are what the renderer draws.  ramdisk_* comes from the ADT walk below
 * (found = -1 until it ran), seed_rc is the lookup's 0/1 return, and the reason code is
 * native_ram_block_seed_reason (the DATA row prints it as serr=). */
volatile uint64_t nuwa_ramdisk_pa;
volatile uint64_t nuwa_ramdisk_bytes;
volatile int32_t nuwa_ramdisk_found = -1;
volatile int32_t nuwa_data_seed_rc = -1;

/* r26: the forked driver can create and start its one instance itself (the IOResources
 * persona never produced one).  Called from nuwa_ram_block_create(), not from the class
 * registration - see the comment there for why the early call crashed. */
extern int native_ram_block_start_service(void);
/* The fork's page code: 10..15 are its creation path, 1..9/14 start()'s own refusals. */
extern volatile int32_t nuwa_ram_block_reject;
/* r27: bounded wait for the media after the explicit create (bootstrap thread). */
extern void IOSleep(unsigned int);
extern int native_ram_block_volume_device(const char *uuid, dev_t *device, char *path,
    size_t size);

/* The renderer's extension rows (BootProgress.c: char boot_progress_ext[8][48]). */
extern char boot_progress_ext[8][48];

/* r28: the fork registers the class inside OSMetaClass::preModLoad()/postModLoad(); calling
 * the static initializer bare left the metaclass name a raw string and the class unregistered
 * (r26/r27 crashed in getClassName because of that).  Returns 1 when postModLoad succeeded. */
extern int native_ram_block_register_class(void);
/* r31: the AppleKeyStore service (package/nuwa-aks).  nuwa_aks_init() registers the class in
 * the same early window as the RamBlock bracket; nuwa_aks_create() runs from the Data mount,
 * after bsd_init()/bsd_autoconf(), so keybagd finds the service when launchd starts it. */
extern void nuwa_aks_init(void);
extern int nuwa_aks_create(void);
/* r34: launchd's disabled list (package/nuwa-watchdog), written once the Data volume is up. */
extern int nuwa_boot_watchdog_policy(void *process, uint64_t scratch);
volatile int32_t nuwa_ram_block_register_result = -1;

/* BootProgress.c (r17c): synchronous repaint.  The initproc exec can panic in the same
 * second as this mount, so the frame that survives must already carry the Data result.
 * Absent in older renderers -> NULL, then this is a no-op. */
extern void boot_progress_sync_draw(void) __attribute__((weak_import));

static void
nuwa_data_flush(void)
{
	if (&boot_progress_sync_draw) {
		boot_progress_sync_draw();
	}
}

/* r24: the 1..5 seed failure reason the DATA row carries as serr.  0 only when the lookup
 * succeeded; without the forked driver every failure is 1 (the old two-state answer). */
static int
nuwa_data_seed_reason(void)
{
	int reason = (&native_ram_block_seed_reason) ? (int)native_ram_block_seed_reason : 0;

	return (reason >= 1 && reason <= 5) ? reason : 1;
}

/* r24: what the kernel's own device tree says about the packed ramdisk.  Only the loader
 * writes this entry: DarwinBoot copies the menu entry's initrd next to the ADT it hands over
 * and stores {pa,size} in /chosen/memory-map/PackedRAMDisk, which it requires to be the
 * packaged {0,0} placeholder beforehand.  A zero pair here therefore says the kernel never
 * received a usable seed, whatever the payload contains.  Read-only walk of the Apple ADT the
 * loader passes in the boot args (per node: property count, child count; a node's name is its
 * "name" property; per property: name[32] + length + value, 4-byte aligned), bounded by
 * PE_state.deviceTreeSize, no allocation. */
struct nuwa_packed_ramdisk {
	int found;
	uint64_t pa;
	uint64_t bytes;
};

static uint32_t
nuwa_adt_u32(const uint8_t *p)
{
	return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
	    ((uint32_t)p[3] << 24);
}

static uint64_t
nuwa_adt_u64(const uint8_t *p)
{
	return (uint64_t)nuwa_adt_u32(p) | ((uint64_t)nuwa_adt_u32(p + 4) << 32);
}

static void
nuwa_adt_walk(const uint8_t *data, vm_size_t size, uint32_t *offset, unsigned depth,
    unsigned parent_path, struct nuwa_packed_ramdisk *out)
{
	const uint8_t *name = NULL;
	uint32_t name_len = 0;
	uint32_t props, children, index, path;
	int candidate = 0;
	uint64_t candidate_pa = 0, candidate_bytes = 0;

	if (depth > 32 || size - *offset < 8) {
		return;
	}
	props = nuwa_adt_u32(data + *offset);
	children = nuwa_adt_u32(data + *offset + 4);
	*offset += 8;
	if (props > (size - *offset) / 36) {
		return;
	}
	for (index = 0; index < props; index++) {
		const uint8_t *prop = data + *offset;
		uint32_t len;

		if (size - *offset < 36) {
			return;
		}
		len = nuwa_adt_u32(prop + 32);
		*offset += 36;
		if (len > size - *offset) {
			return;
		}
		if (name == NULL && prop[4] == 0 && !strncmp((const char *)prop, "name", 4)) {
			name = data + *offset;
			name_len = len;
		}
		if (!strncmp((const char *)prop, "PackedRAMDisk", 13) && prop[13] == 0 && len == 16) {
			candidate = 1;
			candidate_pa = nuwa_adt_u64(data + *offset);
			candidate_bytes = nuwa_adt_u64(data + *offset + 8);
		}
		*offset += len;
		*offset = (*offset + 3) & ~3u;
	}
	path = 3;
	if (depth == 0) {
		path = 0;
	} else if (depth == 1 && parent_path == 0 && name != NULL && name_len == 7 &&
	    !memcmp(name, "chosen", 7)) {
		path = 1;
	} else if (depth == 2 && parent_path == 1 && name != NULL && name_len == 11 &&
	    !memcmp(name, "memory-map", 11)) {
		path = 2;
	}
	if (path == 2 && candidate) {
		out->found = 1;
		out->pa = candidate_pa;
		out->bytes = candidate_bytes;
	}
	if (children > (size - *offset) / 8) {
		return;
	}
	for (index = 0; index < children; index++) {
		nuwa_adt_walk(data, size, offset, depth + 1, path, out);
	}
}

/* One console line, printed before the seed lookup so it is adjacent to its result. */
static void
nuwa_data_packed_ramdisk_report(void)
{
	struct nuwa_packed_ramdisk packed = { 0, 0, 0 };

	if (PE_state.deviceTreeHead != NULL && PE_state.deviceTreeSize >= 8) {
		uint32_t offset = 0;

		nuwa_adt_walk((const uint8_t *)PE_state.deviceTreeHead, PE_state.deviceTreeSize,
		    &offset, 0, 3, &packed);
	}
	/* r25: the page reads these, the console line is the same information for a serial log. */
	nuwa_ramdisk_pa = packed.pa;
	nuwa_ramdisk_bytes = packed.bytes;
	nuwa_ramdisk_found = packed.found;
	printf("nuwa: packed ramdisk pa=%#llx bytes=%#llx found=%d\n", packed.pa, packed.bytes,
	    packed.found);
}

/* stage: 0 not run, 1 seed/paths resolved, 2 mount() called, 3 mount verified,
 * 4 diagnostics written.  status: mount()'s errno (or the local error). */
volatile uint32_t nuwa_data_stage;
/* r30: the three directories keybagd needs, checked once right after the mount verified.
 * One vnode_lookup + one vnode_getattr per path, no create and no write: o = directory with
 * a write bit, r = directory without one, m = not found (ENOENT), e = any other failure.
 * The letters are keybags/db/tmp in that order, drawn on the page as kb=<letters>. */
volatile uint8_t nuwa_data_kb_code[3];
volatile int32_t nuwa_data_kb_errno[3];
volatile char nuwa_data_kb_text[4];
volatile int32_t nuwa_data_status = -1;
volatile int32_t nuwa_data_readonly = -1;
volatile int32_t nuwa_data_verify_result = -1;
volatile dev_t nuwa_data_device = NODEV;
volatile uint32_t nuwa_data_seed_ok;
volatile int32_t nuwa_data_seed_error = -1;
/* Diagnostic only (NUWA-POSTEVENT-20261127): the completed first mount attempt,
 * latched before initproc exec so the panic-safe page row can distinguish a
 * finished attempt ("first-attempt") from a sampled in-progress stage ("now").
 * Nothing reads these for a mount, storage or write decision. */
volatile uint32_t nuwa_data_attempted;
volatile uint32_t nuwa_data_first_done;
static uint32_t nuwa_data_first_stage;
static int32_t nuwa_data_first_status;
static int32_t nuwa_data_first_readonly;
static uint32_t nuwa_data_first_device;
static uint32_t nuwa_data_first_seed;
volatile uint32_t nuwa_data_mount_flags;
volatile uint32_t nuwa_ram_block_init_calls;
uint64_t nuwa_data_seed_base;
uint64_t nuwa_data_seed_bytes;
uint8_t nuwa_data_seed_digest[32];
char nuwa_data_device_path[64];

static int nuwa_ram_block_initialized;
static int nuwa_ram_block_create_done;
volatile int32_t nuwa_ram_block_create_rc = -1;
volatile uint32_t nuwa_ram_block_wait_rounds;

/* r27: create and start the one disk.  r26 did this earlier, inside
 * IOPlatformExpertDevice::startIOServiceMatching().  Both r26 and r27 aborted in
 * OSMetaClass::getClassName() (pc OSMetaClass::getClassName+0xc, far reading the
 * "NativeRamBlock" literal) because the class registration itself was wrong: the static
 * initializer was called without OSMetaClass::preModLoad()/postModLoad(), so the metaclass kept
 * its name as a raw string and was never registered (fixed in r28 by
 * native_ram_block_register_class).  This function stays at the data mount: the bootstrap
 * thread reaches it after bsd_init()/bsd_autoconf(), i.e. after IOBSD is published and with
 * IOResources attached to the registry root, which is also where the media has to appear.  One
 * shot, and start()'s own atomic claim keeps a late persona match from creating a second
 * disk. */
void
nuwa_ram_block_create(void)
{
	dev_t device = NODEV;
	char path[64];
	unsigned i;

	if (nuwa_ram_block_create_done) {
		return;
	}
	nuwa_ram_block_create_done = 1;
	nuwa_ram_block_create_rc = native_ram_block_start_service();
	if (nuwa_ram_block_create_rc <= 0) {
		/* the factory sets 10..13 on its own failures; 15 means it was not linked at all */
		if (nuwa_ram_block_reject == 0) {
			nuwa_ram_block_reject = 15;
		}
		return;
	}
	/* The disk is up; IOStorageFamily publishes the media and APFS probes the container
	 * asynchronously.  Give that a bounded window (bootstrap thread, before the initproc
	 * exists) so the seed lookup below sees the volume, instead of racing it. */
	for (i = 0; i < 100; i++) {
		if (native_ram_block_volume_device(XNU_NUWA_DATA_VOLUME_UUID, &device, path,
		    sizeof(path))) {
			break;
		}
		IOSleep(20);
		nuwa_ram_block_wait_rounds = i + 1;
	}
	printf("nuwa: ram block created rc=%d rounds=%u\n", (int)nuwa_ram_block_create_rc,
	    (unsigned)nuwa_ram_block_wait_rounds);
}

void
nuwa_ram_block_init(void)
{
	if (nuwa_ram_block_initialized) {
		return;
	}
	nuwa_ram_block_initialized = 1;
	nuwa_ram_block_init_calls = nuwa_ram_block_init_calls + 1;
	nuwa_ram_block_register_result = native_ram_block_register_class();
	printf("nuwa: ram block class registered=%d\n", (int)nuwa_ram_block_register_result);
	/* r31: the same window (after IOService::setPlatform()) is where OSMetaClass accepts a
	 * class registration, so the keystore class is registered next to the disk class. */
	nuwa_aks_init();
	/* r27: registration only.  The instance is created later (nuwa_ram_block_create), when
	 * IOKit is ready for it; see the comment there. */
}

static void
nuwa_data_rows(int stage, int status, int readonly, dev_t device, uint32_t seed_ok)
{
	if (stage < 0) {
		return;
	}
	snprintf(boot_progress_ext[0], 48, "DATA mnt st=%u err=%d ro=%u dev=%x",
	    (unsigned)stage, status, (unsigned)readonly, (unsigned)device);
	snprintf(boot_progress_ext[1], 48, "DATA seed ok=%u id=%02x%02x%02x%02x blk=%u",
	    seed_ok, nuwa_data_seed_digest[0], nuwa_data_seed_digest[1],
	    nuwa_data_seed_digest[2], nuwa_data_seed_digest[3],
	    (unsigned)(nuwa_data_seed_bytes >> 12));
}

/* Diagnostic only: latch the completed first mount attempt.  Called once from the
 * success and failure exits of nuwa_data_mount_prepare(), before initproc exec. */
static void
nuwa_data_first_record(unsigned stage, int status, int readonly, dev_t device, uint32_t seed)
{
	if (__atomic_load_n(&nuwa_data_first_done, __ATOMIC_ACQUIRE)) {
		return;
	}
	nuwa_data_first_stage = stage;
	nuwa_data_first_status = status;
	nuwa_data_first_readonly = readonly;
	nuwa_data_first_device = (uint32_t)device;
	nuwa_data_first_seed = seed;
	__atomic_store_n(&nuwa_data_first_done, 1, __ATOMIC_RELEASE);
}

/* Page row for the post-event summary: DATA0 is the completed first attempt
 * (st/err/ro/dev/seed), DATA now is the sampled in-progress stage.  Returns
 * 2 when the first attempt completed, 1 while it is running, 0 when it never
 * started; the text is always written. */
int
nuwa_data_mount_summary(char *buf, size_t size)
{
	if (__atomic_load_n(&nuwa_data_first_done, __ATOMIC_ACQUIRE)) {
		snprintf(buf, size, "DATA0 st=%u err=%d ro=%d dev=%x seed=%u first-attempt",
		    nuwa_data_first_stage, nuwa_data_first_status,
		    nuwa_data_first_readonly, nuwa_data_first_device, nuwa_data_first_seed);
		return 2;
	}
	if (!__atomic_load_n(&nuwa_data_attempted, __ATOMIC_RELAXED)) {
		snprintf(buf, size, "DATA0 not run");
		return 0;
	}
	snprintf(buf, size, "DATA now st=%u (sampled; first attempt running)",
	    (unsigned)nuwa_data_stage);
	return 1;
}

/* r30: after the Data mount verified, record whether /private/var/keybags, /private/var/db
 * and /private/var/tmp exist and look writable.  Read-only by design: a write probe would
 * need a create + remove on the volume launchd is about to use, and the mode bits answer the
 * question the reboot triage needs (missing vs present vs no write bit). */
static const char *const nuwa_kb_paths[3] = {
	"/private/var/keybags",
	"/private/var/db",
	"/private/var/tmp",
};

static void
nuwa_data_kb_check(void)
{
	vfs_context_t ctx = vfs_context_kernel();
	int i;

	for (i = 0; i < 3; i++) {
		struct vnode_attr va;
		vnode_t vp = NULLVP;
		int error;

		error = vnode_lookup(nuwa_kb_paths[i], 0, &vp, ctx);
		if (error) {
			nuwa_data_kb_code[i] = (error == ENOENT) ? 'm' : 'e';
			nuwa_data_kb_errno[i] = error;
			continue;
		}
		VATTR_INIT(&va);
		VATTR_WANTED(&va, va_mode);
		VATTR_WANTED(&va, va_type);
		error = vnode_getattr(vp, &va, ctx);
		if (error) {
			nuwa_data_kb_code[i] = 'e';
			nuwa_data_kb_errno[i] = error;
		} else if (va.va_type != VDIR) {
			nuwa_data_kb_code[i] = 'e';
			nuwa_data_kb_errno[i] = ENOTDIR;
		} else {
			nuwa_data_kb_code[i] = (va.va_mode & 0222) ? 'o' : 'r';
			nuwa_data_kb_errno[i] = 0;
		}
		vnode_put(vp);
	}
	nuwa_data_kb_text[0] = (char)nuwa_data_kb_code[0];
	nuwa_data_kb_text[1] = (char)nuwa_data_kb_code[1];
	nuwa_data_kb_text[2] = (char)nuwa_data_kb_code[2];
	nuwa_data_kb_text[3] = 0;
	printf("nuwa: data kb keybags=%c(%d) db=%c(%d) tmp=%c(%d)\n",
	    nuwa_data_kb_text[0], (int)nuwa_data_kb_errno[0],
	    nuwa_data_kb_text[1], (int)nuwa_data_kb_errno[1],
	    nuwa_data_kb_text[2], (int)nuwa_data_kb_errno[2]);
}

int
nuwa_data_mount_prepare(proc_t p, user_addr_t scratch)
{
	uint8_t payload[0x150] = { 0 };
	user64_addr_t spec = scratch + 0x160;
	uint16_t mode = 1;
	uint32_t anonymous_owner = 99;
	uint64_t mount_flags = 0;
	int32_t result = 0;
	int readonly_probe = 0;
	int error = 0;
	dev_t device = NODEV;
	vnode_t vp = NULLVP;
	vnode_t devvp = NULLVP;
	const char *why = "not run";

	nuwa_data_stage = 0;
	__atomic_store_n(&nuwa_data_attempted, 1, __ATOMIC_RELAXED);
	if (PE_parse_boot_argn("nuwa-data-ro", &readonly_probe, sizeof(readonly_probe)) && readonly_probe) {
		mount_flags = MNT_RDONLY;
	}

	/* 1. Seed/volume: this also opens the persistent store window (and formats the
	 *    overlay header on a reset boot) before mount() touches APFS.  r18 records the
	 *    reason separately: seedpub/seederr in the Data row tell "the Data volume was
	 *    never published by the RamBlock driver" apart from "the lookup worked but the
	 *    /dev node is missing" (which shows up as mount() ENOENT).
	 *    r24 adds the two lines that say which of those it is: what the kernel's own
	 *    device tree says the loader handed over (packed ramdisk pa/bytes), then the
	 *    driver's readiness, the lookup result and a 1..5 reason code.
	 *    r27 creates the ram disk here first: this runs on the bootstrap thread after
	 *    bsd_init()/bsd_autoconf(), i.e. after IOBSD and with the registry connected. */
	nuwa_ram_block_create();
	nuwa_data_packed_ramdisk_report();
	printf("nuwa: data seed uuid=%s ready=%u ic=%u\n", XNU_NUWA_DATA_VOLUME_UUID,
	    (&native_ram_block_ready) ? (unsigned)native_ram_block_ready : 0u,
	    (unsigned)nuwa_ram_block_init_calls);
	int seed_ok = native_ram_block_volume_seed(XNU_NUWA_DATA_VOLUME_UUID, &device,
	    nuwa_data_device_path, sizeof(nuwa_data_device_path), &nuwa_data_seed_base,
	    &nuwa_data_seed_bytes, nuwa_data_seed_digest);
	nuwa_data_seed_rc = seed_ok ? 1 : 0;
	nuwa_data_seed_error = seed_ok ? 0 : nuwa_data_seed_reason();
	printf("nuwa: data seed rc=%d dev=%x path=%s serr=%d\n", seed_ok, (unsigned)device,
	    nuwa_data_device_path[0] ? nuwa_data_device_path : "-",
	    (int)nuwa_data_seed_error);
	if (!seed_ok) {
		why = "ram-block volume/seed lookup failed";
		error = ENOENT;
		goto done;
	}
	nuwa_data_device = device;
	nuwa_data_seed_ok = 1;
	nuwa_data_stage = 1;

	/* 2. The qualified user-mount payload. */
	memcpy(payload, &spec, sizeof(spec));
	memcpy(payload + 8, &mount_flags, sizeof(mount_flags));
	memcpy(payload + 16, &mode, sizeof(mode));
	memcpy(payload + 0x144, &anonymous_owner, sizeof(anonymous_owner));
	memcpy(payload + 0x148, &anonymous_owner, sizeof(anonymous_owner));

	struct mount_args request = {
		.type = scratch + 0x100,
		.path = scratch + 0x120,
		.flags = (int)mount_flags,
		.data = scratch + 0x200,
	};
	error = copyout("apfs", request.type, 5);
	if (!error) {
		error = copyout(NUWA_DATA_MOUNT_POINT, request.path, sizeof(NUWA_DATA_MOUNT_POINT));
	}
	if (!error) {
		error = copyout(nuwa_data_device_path, spec, strlen(nuwa_data_device_path) + 1);
	}
	if (!error) {
		error = copyout(payload, request.data, sizeof(payload));
	}
	if (error) {
		why = "copyout of the mount request failed";
		goto done;
	}
	nuwa_data_stage = 2;
	error = mount(p, &request, &result);
	nuwa_data_status = error;
	if (error) {
		why = "mount(apfs, /private/var) failed";
		goto done;
	}

	/* 3. Verify: same device, apfs, and the read-only flag we asked for. */
	error = vnode_lookup(NUWA_DATA_MOUNT_POINT, 0, &vp, vfs_context_current());
	if (error) {
		why = "lookup of /private/var failed";
		goto done;
	}
	mount_t mp = vnode_mount(vp);
	devvp = vfs_devvp(mp);
	dev_t actual = devvp ? vnode_specrdev(devvp) : NODEV;
	if (devvp) {
		vnode_put(devvp);
		devvp = NULLVP;
	}
	nuwa_data_mount_flags = (uint32_t)vfs_flags(mp);
	int readonly = (vfs_flags(mp) & MNT_RDONLY) != 0;
	int right_fs = !strcmp(vfs_statfs(mp)->f_fstypename, "apfs");
	nuwa_data_readonly = readonly;
	nuwa_data_verify_result = (actual == device && right_fs && readonly == (mount_flags != 0)) ? 1 : 0;
	if (!nuwa_data_verify_result) {
		why = "mounted volume failed verification (device/apfs/read-only)";
		error = EINVAL;
		vnode_put(vp);
		vp = NULLVP;
		goto done;
	}
	vnode_put(vp);
	vp = NULLVP;
	nuwa_data_stage = 3;
	nuwa_data_status = 0;
	nuwa_data_rows(3, 0, readonly, device, nuwa_data_seed_ok);
	/* r31: the keystore service is published before initproc exec, i.e. long before keybagd. */
	(void)nuwa_aks_create();
	nuwa_data_kb_check();
	/* r34: watchdogd would trap without an IOWatchdog backend, so its launchd job is disabled
	 * here (disabled.plist + disabled.migrated) before the initproc is exec'd.  The same scratch
	 * page the mount used is free at +0x200 and +0x800. */
	(void)nuwa_boot_watchdog_policy(p, scratch);
	nuwa_data_stage = 4;
	nuwa_data_first_record(4, 0, readonly, device, nuwa_data_seed_ok);
	nuwa_data_flush();
	return 0;

done:
	if (vp) {
		vnode_put(vp);
	}
	nuwa_data_status = error;
	nuwa_data_first_record(nuwa_data_stage, error, nuwa_data_readonly,
	    nuwa_data_device, nuwa_data_seed_ok);
	nuwa_data_rows(nuwa_data_stage, error, nuwa_data_readonly, nuwa_data_device, nuwa_data_seed_ok);
	printf("nuwa: Data mount not completed at stage %u: %s (%d)\n", nuwa_data_stage, why, error);
	nuwa_data_flush();
	return error;
}
