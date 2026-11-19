// SPDX-License-Identifier: BSD-2-Clause-Patent
/*
 * nuwa r12: mount the SystemOS cryptex read-only on /private/preboot and hand the
 * initproc an environment that points dyld at the shared cache inside it, plus the
 * pid 1 status row for the boot progress page.
 *
 * Why: the 20H392 OS window has no /System/Library/Caches/com.apple.dyld and no
 * /usr/lib/libSystem.B.dylib (confirmed on the host with apfs-fuse); both live in the
 * Cryptex1,SystemOS window, which the UFS driver already publishes (published=2) but
 * nothing mounts.  Without it dyld cannot map the shared cache, and iOS resolves
 * libSystem only from that cache.
 *
 * r17: the r16 device run showed that the environment alone is not enough.  The
 * initproc is a platform binary, so dyld ignores DYLD_SHARED_CACHE_DIR and walks its
 * own fixed list; the only entry this root can satisfy is
 * /private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld (the root's
 * /System/Cryptexes/OS symlink resolves to it).  r16 mounted the cryptex *on*
 * /private/preboot, which both hides the real directory and leaves
 * /private/preboot/Cryptexes nonexistent, so the symlink dangled and dyld fell back
 * to /usr/lib/libSystem.B.dylib (r16 panic: "Library not loaded; no such file, no
 * dyld cache").  r17 therefore mounts a writable memory-backed filesystem on
 * /private/preboot first, creates Cryptexes inside it, and mounts the cryptex at
 * /private/preboot/Cryptexes/OS.
 *
 * xnu-8796 has no tmpfs: bsd/miscfs has bindfs, deadfs, devfs, fifofs, mockfs,
 * nullfs, routefs, specfs and union, the build tree only compiles bindfs, devfs and
 * routefs (devfs_vfsops.o/bind_vfsops.o in ios-obj/.../bsd/DEVELOPMENT, no tmpfs
 * source anywhere in .cache/xnu-work), and there is no mount_tmpfs()/mnt_tmpfs
 * symbol in the linked kernel.  mockfs is mountroot-only and has no vfs_mount and no
 * mkdir, union/nullfs are not built.  devfs is the only memory-backed filesystem in
 * this kernel that implements VNOP_MKDIR (bsd/miscfs/devfs/devfs_vnops.c
 * devfs_mkdir), and devfs_kernel_mount() is its in-kernel entry point (used by
 * bsd_init.c for /dev).  r17 uses that instead of tmpfs; the fallback is r16's
 * mount point, recorded, never a panic.
 *
 * Derived from UniXNU patches/xnu/offline-owner-systemos-mount.patch
 * (native_owner_cache_prepare, MIT, sheng), reduced to the non-union form:
 *   * mount point /private/preboot and DYLD_SHARED_CACHE_DIR, exactly the official
 *     non-union shape (XNU_OWNER_UNION_SYSTEMOS is off here),
 *   * no owner boot manifest (XNU_OWNER_BOOT_MANIFEST is off; the nuwa bring-up has no
 *     owner chain) and no dyld_flags/commpage startup selection,
 *   * the mount payload is the same 0x150-byte user-mount payload the official patch
 *     qualified, byte for byte, because that layout is what the apfs kext parses.
 *
 * Failure policy: every step records a stage/status and returns; nothing panics, so the
 * boot progress page can show what happened.  The volume lookup and the root
 * authorization come from the official VirtioMmioBlock component, which delegates a UFS
 * window to ShengUfs' native_ufs_block_authenticates().
 *
 * Not device evidence: this file has never run on hardware.
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
#include <libkern/libkern.h>
#include <mach/mach_time.h>
#include <kern/clock.h>

#ifndef NUWA_SYSTEMOS_VOLUME_UUID
/* Measured from the SystemOS window of 087-86593-047.dmg (APSB block, +240):
 * volume name SydneyUpdate20H392.D22D221SystemCryptex, role 0.  Deliberately not
 * XNU_OWNER_CACHE_VOLUME_UUID: the build's -include owner-data-volume.h defaults that
 * one to sheng's 8846FE78-2910-4297-AF97-D59BB6F8FC16, which is not this image. */
#define NUWA_SYSTEMOS_VOLUME_UUID "96096B28-B6DC-4BC7-9D3A-2632A0FE53F1"
#endif
/* r18: the cryptex is union-mounted on "/" (official shape).  dyld has no preboot-cryptex
 * search path; the only fixed cache location it can use here is
 * /System/Library/Caches/com.apple.dyld on the root, which only a union of the SystemOS
 * volume over "/" can provide.  xnu-8796 implements union mounts in VFS itself
 * (CONFIG_UNION_MOUNTS: mount(2) keeps MNT_UNION in mnt_flag, vfs_syscalls.c:1273-1281;
 * ENOENT inside such a mount falls through to the covered vnode, vfs_lookup.c:1327-1344)
 * and mounting on the root vnode moves rootvnode (checkdirs(), vfs_syscalls.c:2549-2560,
 * called from place_mount_and_checkdirs()).  MNT_ROOTFS is rejected by mount(2)
 * (vfs_syscalls.c:429-431), so it must not be set. */
#define NUWA_SYSTEMOS_MOUNT_POINT "/"
/* Fallback only, when the union mount on "/" is refused: r17's shape, a memory-backed
 * filesystem on /private/preboot with Cryptexes/OS as the cryptex mount point. */
#define NUWA_PREBOOT_MOUNT_POINT "/private/preboot"
#define NUWA_CRYPTEX_DIR NUWA_PREBOOT_MOUNT_POINT "/Cryptexes"
#define NUWA_SYSTEMOS_CRYPTEX_POINT NUWA_CRYPTEX_DIR "/OS"
#define NUWA_SYSTEMOS_FALLBACK_POINT NUWA_PREBOOT_MOUNT_POINT
/* r22: the initproc is exec'd with NO environment at all.  An earlier revision set
 * DYLD_SHARED_CACHE_DIR=/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld; that
 * path does not exist in this namespace (the kernel probe recorded p3=2), and dyld4's
 * CacheFinder treats an override directory that cannot be opened as fatal for the search:
 * it returns early instead of falling back to /System/Library/Caches/com.apple.dyld, so the
 * cache was never loaded even though the default path resolves (p1=0, p2=0).  The variable
 * is a security override that platform binaries are not supposed to use; removing it lets
 * dyld use its own default path, which the union mount serves. */

/* r19 cache probe.  The image carries the cache as "dyld_shared_cache_arm64" (the name the
 * /usr/lib/dyld in this build is hard-coded to), so the probe asks for exactly that file
 * and for its directory.  Six paths, in the order the diagnostics report them (p1..p6):
 *   p1 the directory dyld names,
 *   p2 the file inside it on the root (what a union of / is meant to provide),
 *   p3/p4 its .01 and .42 sub-caches,
 *   p5 the same file through /System/Cryptexes/OS,
 *   p6 the same file through the preboot path r17/r17c used. */
#define NUWA_CACHE_DIR "/System/Library/Caches/com.apple.dyld"
#define NUWA_CACHE_FILE NUWA_CACHE_DIR "/dyld_shared_cache_arm64"
#define NUWA_CACHE_FILE_01 NUWA_CACHE_FILE ".01"
#define NUWA_CACHE_FILE_42 NUWA_CACHE_FILE ".42"
/* r22: six paths.  The main cache header declares subCacheArrayCount=42, and dyld treats a
 * missing sub-cache as a failed load, so the two names it needs most (.01 and .42) are
 * probed explicitly and reported as p3/p4. */
static const char *const nuwa_cache_probe_paths[6] = {
	NUWA_CACHE_DIR,
	NUWA_CACHE_FILE,
	NUWA_CACHE_FILE_01,
	NUWA_CACHE_FILE_42,
	"/System/Cryptexes/OS" NUWA_CACHE_FILE,
	"/private/preboot/Cryptexes/OS" NUWA_CACHE_FILE,
};
/* r23: the first 16 bytes of any dyld shared cache are this header magic and nothing else:
 * "dyld_v1" + three spaces + "arm64" + NUL, which is exactly 16 bytes (dyld4 writes it with
 * strlcpy into char magic[16]).  r22 compared "dyld_v1" at offset 0 and "arm64" at offset 8,
 * i.e. the wrong offset, and reported mg=bad for a cache that dyld loaded and mapped. */
static const char nuwa_cache_magic_expected[16] = "dyld_v1   arm64";

/* r20 code-signing observation.  amfi is the interface pointer the AMFI kext installs
 * through amfi_interface_register() (libkern/libkern/amfi/amfi.h; NULL until it runs), and
 * nuwa_cs_config() is the opt-in accessor added to kern_codesigning.c by
 * patches/xnu/8796-nuwa-cs-observe.patch (cs_config itself is file-static, so it cannot be
 * referenced from here).  Both are weak: a build without them reports 0/-1 instead of
 * failing to link. */
extern const void *amfi __attribute__((weak_import));
extern uint32_t nuwa_cs_config(void) __attribute__((weak_import));
/* r22: what kern_exec wrote into the commpage dyld flags and what the commpage holds after
 * that write (patches/xnu/8796-nuwa-r22-dyld-flags-readback.patch). */
extern volatile uint32_t nuwa_dyld_flags_value __attribute__((weak_import));
extern volatile uint64_t nuwa_dyld_flags_read __attribute__((weak_import));

extern int native_verified_block_volume_device(const char *, dev_t *, char *, size_t);
extern int native_verified_block_root_authorized(dev_t);
extern int native_verified_block_manifest_sha384(dev_t, const char *, uint8_t[48]);
/* miscfs/devfs/devfs_proto.h, used by bsd_init.c to mount /dev from the kernel:
 * kernel_mount("devfs", ...), a memory-backed filesystem with VNOP_MKDIR. */
extern int devfs_kernel_mount(char *);
/* BootProgress.c (r17c): synchronous repaint, so the frame that survives the initproc
 * panic already carries this mount's result.  Absent in older renderers -> NULL. */
extern void boot_progress_sync_draw(void) __attribute__((weak_import));

/* The VirtioMmioBlock object is compiled with NATIVE_VERIFIED_BLOCK=1 here.  It references
 * the owner manifest from configureVerification(), which only runs if a virtio-mmio
 * personality ever starts (it never does on this board), and the lookup/authorization
 * functions used here do not read it.  The nuwa link carries no owner manifest, so provide
 * a weak empty one instead of pulling in the owner chain. */
__attribute__((weak)) const uint8_t verified_root_manifest[1] = { 0 };
__attribute__((weak)) const uint64_t verified_root_manifest_bytes = 0;

/* Screen/selfcheck observables.  stage: 0 not run, 1 root device, 2 volume resolved,
 * 3 preboot scratch filesystem ready (fallback path only), 4 mount() called, 5 mount
 * verified, 6 environment handed to exec.  r17/r18: the per-step results are separate so a
 * failed fork (union mount, scratch mount, mkdir, cryptex mount) is readable without
 * decoding the stage. */
volatile uint32_t nuwa_systemos_stage;
volatile int32_t nuwa_systemos_status = -1;
volatile int32_t nuwa_systemos_mount_result = -1;
volatile int32_t nuwa_systemos_verify_result = -1;
volatile int32_t nuwa_systemos_root_authorized = -1;
volatile uint32_t nuwa_systemos_volume_found;
volatile dev_t nuwa_systemos_device = NODEV;
volatile uint32_t nuwa_systemos_mount_flags;
/* r18: 1 = the mount carries MNT_UNION, 1 = rootvnode now is the mounted root (checkdirs
 * moved it).  -1 = not evaluated (mount or lookup failed). */
volatile int32_t nuwa_systemos_union_flag = -1;
volatile int32_t nuwa_systemos_root_moved = -1;
/* r17: 0 = devfs mounted on /private/preboot, errno = it failed; the two mkdir errnos,
 * -1 when not attempted (the fallback path only - the union path on "/" needs neither). */
volatile int32_t nuwa_systemos_preboot_result = -1;
volatile int32_t nuwa_systemos_mkdir_result = -1;
volatile int32_t nuwa_systemos_mkdir_os_result = -1;
volatile uint32_t nuwa_systemos_scratch_filesystem;
/* r19: kernel-side lookups of the six dyld shared-cache paths, run right after a verified
 * mount.  error = vnode_lookup()'s errno (-1 = not run), device = the device of the mount
 * the vnode belongs to, size = va_data_size in bytes (0 when not a regular file). */
volatile int32_t nuwa_systemos_cache_error[6] = { -1, -1, -1, -1, -1, -1 };
volatile uint32_t nuwa_systemos_cache_device[6];
volatile uint64_t nuwa_systemos_cache_size[6];
/* r20: amfi = the AMFI interface pointer is installed (1) or not (0), -1 = not observed;
 * cs = the code-signing configuration record from nuwa_cs_config(), 0xffffffff = the
 * accessor is not linked or the observation did not run. */
volatile int32_t nuwa_systemos_amfi_installed = -1;
volatile uint32_t nuwa_systemos_cs_config = 0xffffffffu;
/* r22: 1 = the main cache starts with the dyld_v1/arm64 magic, 0 = it does not, -1 = the
 * read did not happen.  r23: the 16 bytes that were read are kept verbatim so the console
 * line can carry them as hex (the page row only has room for ok/bad/-). */
volatile int32_t nuwa_systemos_cache_magic_ok = -1;
char nuwa_systemos_cache_magic[16];
/* The path the cryptex was mounted on, and the f_mntonname the mounted volume reports. */
char nuwa_systemos_mount_point[64];
char nuwa_systemos_mount_reported[64];
/* Counted by the cache-location exception in bsd/vm/vm_unix.c (nuwa r12). */
volatile uint32_t nuwa_shared_cache_location_bypass;
char nuwa_systemos_device_path[64];
/* 224: with both mkdir errnos the row reaches ~192 bytes; line_or_wrap puts the remainder
 * on row 4 (120 columns per row), so the buffer must stay above that but the text must
 * stay below ~200 to fit two rows. */
char nuwa_pid1_row[224];
/* devfs_kernel_mount() takes a writable buffer (namei, UIO_SYSSPACE). */
static char nuwa_preboot_scratch_point[] = NUWA_PREBOOT_MOUNT_POINT;

static const char nuwa_pid1_stat_names[] = "?IDL RUN SLP STP ZMB";

/* Prototypes for the entry points (kern_exec.c and the boot progress stubs call them). */
int nuwa_systemos_prepare(proc_t, user_addr_t, user_addr_t *);
void nuwa_pid1_sample(void);
const char *nuwa_systemos_row(void);
const char *nuwa_systemos_row2(void);
const char *nuwa_systemos_row3(void);

/* r17c: refresh the pid1 row and repaint synchronously before the initproc exec, so the
 * frame that survives a sub-second initproc panic already carries this mount's result. */
static void
nuwa_systemos_flush(void)
{
	nuwa_pid1_sample();
	if (&boot_progress_sync_draw) {
		boot_progress_sync_draw();
	}
}

/*
 * The SystemOS part of the page: stage, errno, device, root-auth record, then the mount
 * chain - pb/mk/mos are the fallback path's memory filesystem and two mkdirs (all -1 on
 * the union path, which needs none), ap is mount()'s errno, mnt is the path we asked for,
 * dst is the f_mntonname the mounted volume reports, uni is the MNT_UNION bit and rv is
 * "rootvnode is now the mounted root" (checkdirs moved it).  r19 adds p1..p6, the errno of
 * the six cache-path lookups (see nuwa_cache_probe_paths; -1 = not run) and csz, the size of
 * /System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64 in KiB (0 when not found).
 * r20 adds amfi (the AMFI interface is installed) and cs (the cs_config record, or
 * 0xffffffff when the accessor is not linked).  r21 drops mnt/dst from the row: the row is
 * drawn in the two rows (3 and 4) that survive a panic, and they have to hold the whole
 * record, so the mount point (which is "/" on the union path and "/private/preboot/
 * Cryptexes/OS" only on the fallback, already implied by pb/mk/mos) stays in the console
 * lines.  The console lines "nuwa: cs ..." and "nuwa: cache probe ..." carry the same
 * results with the full mount point, and remain authoritative for anything else.
 * One formatter, used by both the pid1 row and (r17) the SystemOS-only row the renderer
 * draws when the process probe never ran.
 */
/* Line 1 of the record: stage and errno.  Bounded to 24 characters with worst-case values
 * ("SYSOS st=6 err=22"), so it always fits next to the pid 1 state on one 80-column row. */
static void
nuwa_systemos_fields1(char *buf, size_t size)
{
	snprintf(buf, size, "SYSOS st=%u err=%d",
	    nuwa_systemos_stage, (int)nuwa_systemos_status);
}

/* Line 2: the device, the root authorization record and the mount path/union results.
 * Worst case 69 characters (see the build's width check). */
static void
nuwa_systemos_fields2(char *buf, size_t size)
{
	snprintf(buf, size, "dev=%s rauth=%d pb=%d mk=%d mos=%d ap=%d uni=%d rv=%d mg=%s",
	    nuwa_systemos_device_path[0] ? nuwa_systemos_device_path : "-",
	    (int)nuwa_systemos_root_authorized, (int)nuwa_systemos_preboot_result,
	    (int)nuwa_systemos_mkdir_result, (int)nuwa_systemos_mkdir_os_result,
	    (int)nuwa_systemos_mount_result,
	    (int)nuwa_systemos_union_flag, (int)nuwa_systemos_root_moved,
	    nuwa_systemos_cache_magic_ok < 0 ? "-" :
	    nuwa_systemos_cache_magic_ok ? "ok" : "bad");
}

/* Line 3: the AMFI / code-signing view, the six cache probes and the cache size.
 * Worst case 78 characters (see the build's width check). */
static void
nuwa_systemos_fields3(char *buf, size_t size)
{
	snprintf(buf, size,
	    "amfi=%d cs=0x%x flg=%d rd=%lld p1=%d p2=%d p3=%d p4=%d p5=%d p6=%d csz=%u",
	    (int)nuwa_systemos_amfi_installed, (unsigned)nuwa_systemos_cs_config,
	    (&nuwa_dyld_flags_value) ? (int)nuwa_dyld_flags_value : -1,
	    (&nuwa_dyld_flags_read) ? (long long)nuwa_dyld_flags_read : -1LL,
	    (int)nuwa_systemos_cache_error[0], (int)nuwa_systemos_cache_error[1],
	    (int)nuwa_systemos_cache_error[2], (int)nuwa_systemos_cache_error[3],
	    (int)nuwa_systemos_cache_error[4], (int)nuwa_systemos_cache_error[5],
	    (unsigned)(nuwa_systemos_cache_size[1] >> 10));
}

/* r21: the record is published as three lines so each fits one 80-column page row and the
 * rows that survive a panic (rows 3, 4 and 5) carry every field, in priority order:
 *   3: PID1 state + SYSOS st/err
 *   4: dev/rauth/pb/mk/mos/ap/uni/rv
 *   5: amfi/cs/flg/rd/p1..p6/csz
 */
char nuwa_systemos_row_buf[128];
char nuwa_systemos_row2_buf[128];
char nuwa_systemos_row3_buf[128];

/* r19: one probe.  Records the errno, and on success the vnode's mount device and file
 * size.  Never panics and never leaves a vnode referenced.
 *
 * r23: exactly one vnode_lookup() per path and exactly one vnode_put() for it (none when the
 * lookup fails), and no call that takes a usecount.  r22 read the header through a second
 * lookup with vnode_open()/vnode_close(); vnode_close() ends in vnode_rele_ext(), the
 * function this port panicked in on the device (vfs_subr.c:2691, usecount -1) once launchd
 * started, so the header is now read with vn_rdwr() on the vnode this function already holds
 * an iocount on - the same shape ubc_cs_blob_add() uses, and the only reference the read
 * needs.  The put that pairs with vfs_devvp() belongs to that call's own vnode_get(). */
static void
nuwa_systemos_cache_probe_one(unsigned index)
{
	vnode_t vp = NULLVP;
	struct vnode_attr va;
	vnode_t devvp = NULLVP;
	dev_t device = NODEV;
	int error;

	if (index >= sizeof(nuwa_cache_probe_paths) / sizeof(nuwa_cache_probe_paths[0])) {
		return;
	}
	nuwa_systemos_cache_error[index] = -1;
	nuwa_systemos_cache_device[index] = 0;
	nuwa_systemos_cache_size[index] = 0;
	error = vnode_lookup(nuwa_cache_probe_paths[index], 0, &vp, vfs_context_current());
	nuwa_systemos_cache_error[index] = error;
	if (error) {
		/* namei released the path's own vnodes; no vnode was returned to us. */
		return;
	}
	devvp = vfs_devvp(vnode_mount(vp));
	if (devvp) {
		device = vnode_specrdev(devvp);
		vnode_put(devvp);
	}
	VATTR_INIT(&va);
	VATTR_WANTED(&va, va_data_size);
	if (vnode_getattr(vp, &va, vfs_context_current()) == 0) {
		nuwa_systemos_cache_size[index] = (uint64_t)va.va_data_size;
	}
	nuwa_systemos_cache_device[index] = (uint32_t)device;

	/* r23: for the cache file itself, read the first 16 bytes through this same vnode and
	 * compare all 16 with the header dyld writes.  The raw bytes are kept for the console
	 * line so a wrong header (say the arm64e spelling) is read off the record. */
	if (index == 1) {
		char head[16] = { 0 };
		int resid = 0;
		vfs_context_t ctx = vfs_context_current();

		nuwa_systemos_cache_magic_ok = -1;
		if (vn_rdwr(UIO_READ, vp, head, sizeof(head), 0, UIO_SYSSPACE, 0,
		    vfs_context_ucred(ctx), &resid, current_proc()) == 0 && resid == 0) {
			memcpy(nuwa_systemos_cache_magic, head, sizeof(head));
			nuwa_systemos_cache_magic_ok =
			    memcmp(head, nuwa_cache_magic_expected, sizeof(head)) == 0 ? 1 : 0;
		}
	}
	vnode_put(vp);
	vp = NULLVP;
}

/* r23: the 16 header bytes as lowercase hex, for the console line. */
static void
nuwa_systemos_magic_hex(char *buf, size_t size)
{
	unsigned i;
	size_t used = 0;

	for (i = 0; i < sizeof(nuwa_systemos_cache_magic) && used + 2 < size; i++) {
		used += (size_t)snprintf(buf + used, size - used, "%02x",
		    (unsigned)(uint8_t)nuwa_systemos_cache_magic[i]);
	}
	buf[used] = 0;
}

/* r19: probe all six cache paths and print one console line with the full result (the page
 * row only carries the errnos and the file size, the console carries device, bytes, the
 * magic verdict and the 16 bytes it compared). */
static void
nuwa_systemos_cache_probe(void)
{
	char magic[33];
	unsigned i;

	for (i = 0; i < 6; i++) {
		nuwa_systemos_cache_probe_one(i);
	}
	if (nuwa_systemos_cache_magic_ok < 0) {
		magic[0] = 0;
	} else {
		nuwa_systemos_magic_hex(magic, sizeof(magic));
	}
	/* printf is kprintf in the kernel (libkern/stdio.h); same console stream as the
	 * other nuwa lines. */
	printf("nuwa: cache probe p1=%d/%llu/%x p2=%d/%llu/%x p3=%d/%llu/%x p4=%d/%llu/%x"
	    " p5=%d/%llu/%x p6=%d/%llu/%x mg=%d\n",
	    (int)nuwa_systemos_cache_error[0], (unsigned long long)nuwa_systemos_cache_size[0],
	    (unsigned)nuwa_systemos_cache_device[0],
	    (int)nuwa_systemos_cache_error[1], (unsigned long long)nuwa_systemos_cache_size[1],
	    (unsigned)nuwa_systemos_cache_device[1],
	    (int)nuwa_systemos_cache_error[2], (unsigned long long)nuwa_systemos_cache_size[2],
	    (unsigned)nuwa_systemos_cache_device[2],
	    (int)nuwa_systemos_cache_error[3], (unsigned long long)nuwa_systemos_cache_size[3],
	    (unsigned)nuwa_systemos_cache_device[3],
	    (int)nuwa_systemos_cache_error[4], (unsigned long long)nuwa_systemos_cache_size[4],
	    (unsigned)nuwa_systemos_cache_device[4],
	    (int)nuwa_systemos_cache_error[5], (unsigned long long)nuwa_systemos_cache_size[5],
	    (unsigned)nuwa_systemos_cache_device[5],
	    (int)nuwa_systemos_cache_magic_ok);
	/* r23: the 16 bytes the magic check compared, on their own line, so a console capture
	 * says what the header actually was without decoding the mg verdict. */
	printf("nuwa: cache magic=%s\n", magic[0] ? magic : "-");
}

/* r20: is the AMFI interface installed, and what code-signing configuration is in force.
 * Read-only; one console line.  If the opt-in cs accessor is not linked the cfg field stays
 * 0xffffffff, which is itself the answer ("not observable in this build"). */
static void
nuwa_systemos_cs_probe(void)
{
	uint32_t cs = 0xffffffffu;

	nuwa_systemos_amfi_installed = (&amfi != NULL && amfi != NULL) ? 1 : 0;
	if (&nuwa_cs_config) {
		cs = nuwa_cs_config();
	}
	nuwa_systemos_cs_config = cs;
	printf("nuwa: cs amfi=%d cfg=0x%x\n",
	    (int)nuwa_systemos_amfi_installed, (unsigned)cs);
}

/* Row 3 when the pid 1 sample has not run yet (then the renderer draws this instead of the
 * PID1 line). */
const char *
nuwa_systemos_row(void)
{
	nuwa_systemos_fields1(nuwa_systemos_row_buf, sizeof(nuwa_systemos_row_buf));
	return nuwa_systemos_row_buf;
}

const char *
nuwa_systemos_row2(void)
{
	nuwa_systemos_fields2(nuwa_systemos_row2_buf, sizeof(nuwa_systemos_row2_buf));
	return nuwa_systemos_row2_buf;
}

const char *
nuwa_systemos_row3(void)
{
	nuwa_systemos_fields3(nuwa_systemos_row3_buf, sizeof(nuwa_systemos_row3_buf));
	return nuwa_systemos_row3_buf;
}

/*
 * The pid 1 status row: state, comm, whether the process is initproc, the process count,
 * then the SystemOS record above.  Called from the boot progress renderer's two-second
 * process probe (boot_process_capture stub), i.e. from a normal kernel thread context,
 * never from an interrupt.
 */
/* r30: milliseconds from bsd_init() to the first sighting of keybagd, for the early-boot
 * watchdog question (iOS boot watchdogs fire in the 100-240 s range).  The 2 s process probe
 * walks allproc while the value is still zero and stops as soon as it has seen the process;
 * the exec itself is earlier by at most one poll interval.  nuwa_bsd_init_time is recorded at
 * the top of bsd_init() by 8796-nuwa-boot-time.patch. */
extern volatile uint64_t nuwa_bsd_init_time __attribute__((weak_import));
volatile uint32_t nuwa_keybagd_ms;
static int nuwa_keybagd_pid;

static int
nuwa_keybagd_cb(proc_t candidate, void *arg)
{
	(void)arg;
	if (nuwa_keybagd_pid == 0 && candidate->p_comm[0] == 'k' &&
	    candidate->p_comm[1] == 'e' && candidate->p_comm[2] == 'y' &&
	    candidate->p_comm[3] == 'b' && candidate->p_comm[4] == 'a' &&
	    candidate->p_comm[5] == 'g') {
		nuwa_keybagd_pid = candidate->p_pid;
	}
	return PROC_RETURNED;
}

void
nuwa_keybagd_sample(void)
{
	uint64_t now, ns = 0;

	if (nuwa_keybagd_ms || !(&nuwa_bsd_init_time)) {
		return;
	}
	proc_iterate(PROC_ALLPROCLIST | PROC_NOWAITTRANS, nuwa_keybagd_cb, NULL, NULL, NULL);
	if (nuwa_keybagd_pid == 0) {
		return;
	}
	now = mach_absolute_time();
	absolutetime_to_nanoseconds(now - nuwa_bsd_init_time, &ns);
	nuwa_keybagd_ms = (uint32_t)(ns / 1000000ull);
	printf("nuwa: keybagd pid=%d exec_ms=%u\n", nuwa_keybagd_pid,
	    (unsigned)nuwa_keybagd_ms);
}

void
nuwa_pid1_sample(void)
{
	proc_t p = proc_find(1);
	char state[4] = "?";
	char head[96];
	size_t used;

	if (p == PROC_NULL) {
		used = snprintf(head, sizeof(head), "PID1 absent (proc_find(1)) nprocs=%d | ", nprocs);
	} else {
		if (p->p_stat >= SIDL && p->p_stat <= SZOMB) {
			state[0] = nuwa_pid1_stat_names[(p->p_stat - SIDL) * 4 + 0];
			state[1] = nuwa_pid1_stat_names[(p->p_stat - SIDL) * 4 + 1];
			state[2] = nuwa_pid1_stat_names[(p->p_stat - SIDL) * 4 + 2];
			state[3] = 0;
		}
		used = snprintf(head, sizeof(head),
		    "PID1 st=%u(%s) comm=%.12s init=%d nprocs=%d | ",
		    (unsigned)(uint8_t)p->p_stat, state, p->p_comm, p == initproc ? 1 : 0, nprocs);
		proc_rele(p);
	}
	if (used >= sizeof(head)) {
		used = sizeof(head) - 1;
	}
	memcpy(nuwa_pid1_row, head, used);
	nuwa_systemos_fields1(nuwa_pid1_row + used, sizeof(nuwa_pid1_row) - used);
	/* r30: same 2 s cadence: time bsd_init -> keybagd for the watchdog question. */
	nuwa_keybagd_sample();
}

/* r17c/r18 fallback path: a writable memory-backed filesystem on /private/preboot (devfs;
 * xnu-8796 has no tmpfs) and the two directories the cryptex is mounted through.  Records
 * pb/mk/mos; returns the first errno.  Only reached when the union mount on "/" is
 * refused. */
static int
nuwa_systemos_prepare_preboot(proc_t p, user_addr_t scratch, int32_t *result)
{
	struct mkdir_args dir_request = {
		.path = scratch + 0x300,
		.mode = 0755,
	};
	int error = devfs_kernel_mount(nuwa_preboot_scratch_point);

	nuwa_systemos_preboot_result = error;
	if (error) {
		return error;
	}
	nuwa_systemos_scratch_filesystem = 1;
	nuwa_systemos_stage = 3;

	error = copyout(NUWA_CRYPTEX_DIR, dir_request.path, sizeof(NUWA_CRYPTEX_DIR));
	if (!error) {
		error = mkdir(p, &dir_request, result);
	}
	nuwa_systemos_mkdir_result = error;
	if (error) {
		return error;
	}
	error = copyout(NUWA_SYSTEMOS_CRYPTEX_POINT, dir_request.path,
	    sizeof(NUWA_SYSTEMOS_CRYPTEX_POINT));
	if (!error) {
		error = mkdir(p, &dir_request, result);
	}
	nuwa_systemos_mkdir_os_result = error;
	return error;
}

/*
 * Mount the SystemOS cryptex on the fixed dyld path - r18 unions it on "/", r17's shape
 * (through a memory-backed filesystem on /private/preboot) is the fallback - and build the
 * initproc environment.  Returns 0 when the environment was written, an errno otherwise;
 * the caller records it and continues (never panics).  `scratch` is the page
 * load_init_program() allocated in the initproc address space; the offsets below are the
 * official patch's, inside one page.
 */
int
nuwa_systemos_prepare(proc_t p, user_addr_t scratch, user_addr_t *envp)
{
	uint8_t payload[0x150] = { 0 };
	user64_addr_t spec = scratch + 0x160;
	/* r22: no environment is handed to exec; see the NUWA_SYSTEMOS_* comment above. */
	uint16_t mode = 1;
	uint32_t anonymous_owner = 99;
	uint64_t mount_flags = MNT_RDONLY;
	int32_t result = 0;
	int error = 0;
	dev_t root_dev = NODEV;
	dev_t device = NODEV;
	vnode_t rootdev_vp = NULLVP;
	vnode_t vp = NULLVP;
	vnode_t devvp = NULLVP;
	mount_t mp = NULL;
	const char *why = "not run";

	nuwa_systemos_stage = 0;
	if (!envp) {
		nuwa_systemos_status = EINVAL;
		return EINVAL;
	}

	/* 1. The root volume's device, for the authorization record only.  The r11 bring-up
	 *    bypasses root authentication (8796-nuwa-root-auth-skip), so this value is
	 *    recorded and shown but does not gate the mount. */
	rootdev_vp = vfs_devvp(vnode_mount(rootvnode));
	if (rootdev_vp) {
		root_dev = vnode_specrdev(rootdev_vp);
		vnode_put(rootdev_vp);
	}
	nuwa_systemos_root_authorized = (root_dev == NODEV) ? -1 : native_verified_block_root_authorized(root_dev);
	nuwa_systemos_stage = 1;

	/* 2. Resolve the SystemOS volume to a device node.  native_verified_block_volume_device()
	 *    matches IOMedia by UUID, requires the window's own verified-block authorization and
	 *    returns "/dev/<bsdname>" (VirtioMmioBlock, delegated to ShengUfs for UFS windows). */
	if (!native_verified_block_volume_device(NUWA_SYSTEMOS_VOLUME_UUID, &device,
	    nuwa_systemos_device_path, sizeof(nuwa_systemos_device_path))) {
		why = "verified-block volume lookup failed";
		error = ENOENT;
		goto done;
	}
	nuwa_systemos_volume_found = 1;
	nuwa_systemos_device = device;
	nuwa_systemos_stage = 2;

	/* 3. r18: the SystemOS cryptex union-mounted on "/" (official shape).  The only fixed
	 *    dyld cache location this OS can use is /System/Library/Caches/com.apple.dyld on
	 *    the root, and only the cryptex has it; MNT_UNION keeps the boot volume visible
	 *    underneath.  If mount() refuses the union, fall back once to r17c's shape (devfs
	 *    on /private/preboot, Cryptexes/OS as the mount point) and record it. */
	const char *mount_point = NUWA_SYSTEMOS_MOUNT_POINT;   /* "/" */

	uint64_t request_flags = MNT_RDONLY | MNT_UNION;

prepare_fallback:
	/* Union attempt only on the first pass; the fallback resets request_flags. */
	if ((request_flags & MNT_UNION) == 0) {
		error = nuwa_systemos_prepare_preboot(p, scratch, &result);
		if (error) {
			why = "fallback preboot filesystem/directories failed";
			goto done;
		}
	}

	/* 3b. The qualified user-mount payload (0x150 bytes): [0..8) device path pointer,
	 *    [8..16) mount flags, [16..18) mode 1, [0x144)/[0x148) anonymous owner 99. */
	mount_flags = request_flags;
	memcpy(payload, &spec, sizeof(spec));
	memcpy(payload + 8, &mount_flags, sizeof(mount_flags));
	memcpy(payload + 16, &mode, sizeof(mode));
	memcpy(payload + 0x144, &anonymous_owner, sizeof(anonymous_owner));
	memcpy(payload + 0x148, &anonymous_owner, sizeof(anonymous_owner));
	strlcpy(nuwa_systemos_mount_point, mount_point, sizeof(nuwa_systemos_mount_point));

	struct mount_args request = {
		.type = scratch + 0x100,
		.path = scratch + 0x120,
		.flags = (int)request_flags,
		.data = scratch + 0x200,
	};
	error = copyout("apfs", request.type, 5);
	if (!error) {
		error = copyout(mount_point, request.path, strlen(mount_point) + 1);
	}
	if (!error) {
		error = copyout(nuwa_systemos_device_path, spec, strlen(nuwa_systemos_device_path) + 1);
	}
	if (!error) {
		error = copyout(payload, request.data, sizeof(payload));
	}
	if (error) {
		why = "copyout of the mount request failed";
		goto done;
	}
	nuwa_systemos_stage = 4;
	error = mount(p, &request, &result);
	nuwa_systemos_mount_result = error;
	if (error) {
		if (request_flags & MNT_UNION) {
			/* The union mount was refused and nothing was attached: r17c's shape. */
			why = "mount(apfs, /, MNT_UNION) refused; r17c fallback";
			printf("nuwa: %s (%d)\n", why, error);
			mount_point = NUWA_SYSTEMOS_FALLBACK_POINT;
			request_flags = MNT_RDONLY;
			goto prepare_fallback;
		}
		why = "mount(apfs) failed";
		goto done;
	}

	/* 4. Verify what was mounted: same device, apfs, read-only, and the volume reports
	 *    the path we asked for (dst in the SYSOS row). */
	error = vnode_lookup(mount_point, 0, &vp, vfs_context_current());
	if (error) {
		why = "lookup of the new mount point failed";
		goto done;
	}
	mp = vnode_mount(vp);
	devvp = vfs_devvp(mp);
	dev_t actual = devvp ? vnode_specrdev(devvp) : NODEV;
	if (devvp) {
		vnode_put(devvp);
		devvp = NULLVP;
	}
	nuwa_systemos_mount_flags = (uint32_t)vfs_flags(mp);
	int readonly = (vfs_flags(mp) & MNT_RDONLY) != 0;
	int right_fs = !strcmp(vfs_statfs(mp)->f_fstypename, "apfs");
	strlcpy(nuwa_systemos_mount_reported, vfs_statfs(mp)->f_mntonname,
	    sizeof(nuwa_systemos_mount_reported));
	int right_place = !strcmp(nuwa_systemos_mount_reported, mount_point);
	/* r18: the union bit the mount actually carries, and whether mounting moved
	 * rootvnode (checkdirs() in vfs_syscalls.c:2549-2560, called from
	 * place_mount_and_checkdirs()).  vp is the mounted root after the lookup crossed the
	 * mount, so rv compares it with rootvnode. */
	int union_flag = (vfs_flags(mp) & MNT_UNION) != 0;
	int root_moved = (rootvnode == vp) ? 1 : 0;
	nuwa_systemos_union_flag = union_flag;
	nuwa_systemos_root_moved = root_moved;
	/* A union mount must keep both bits: without MNT_UNION the mount would hide the boot
	 * volume, and without the moved root the union is not the visible namespace. */
	int union_ok = (request_flags & MNT_UNION) ? (union_flag && root_moved) : 1;
	nuwa_systemos_verify_result =
	    (actual == device && readonly && right_fs && right_place && union_ok) ? 1 : 0;
	if (!nuwa_systemos_verify_result) {
		why = "mounted volume failed verification (device/apfs/read-only/path/union)";
		error = EINVAL;
		vnode_put(vp);
		vp = NULLVP;
		goto done;
	}
	vnode_put(vp);
	vp = NULLVP;
	nuwa_systemos_stage = 5;

	/* 4b. r19: the mount verified (union on "/" or the fallback), so now ask the namespace
	 *     itself whether dyld's cache is reachable: the six lookups above and one console
	 *     line.  This is observation only - no policy, no retry. */
	nuwa_systemos_cs_probe();
	nuwa_systemos_cache_probe();

	/* 5. r22: no environment.  dyld must use its own default cache path
	 *    (/System/Library/Caches/com.apple.dyld), which the union mount serves; an override
	 *    directory that does not exist makes CacheFinder give up instead of falling back. */
	*envp = USER_ADDR_NULL;
	nuwa_systemos_stage = 6;
	nuwa_systemos_status = 0;
	/* One console line on success as well: the page's console block is the only place a
	 * frozen frame can still show which step ran. */
	printf("nuwa: SYSOS mounted at %s (pb=%d mk=%d mos=%d ap=%d uni=%d rv=%d st=%u)\n",
	    mount_point, (int)nuwa_systemos_preboot_result, (int)nuwa_systemos_mkdir_result,
	    (int)nuwa_systemos_mkdir_os_result, (int)nuwa_systemos_mount_result,
	    (int)nuwa_systemos_union_flag, (int)nuwa_systemos_root_moved,
	    nuwa_systemos_stage);
	nuwa_systemos_flush();
	return 0;

done:
	if (vp) {
		vnode_put(vp);
	}
	nuwa_systemos_status = error;
	printf("nuwa: SystemOS mount not completed at stage %u: %s (%d)\n",
	    nuwa_systemos_stage, why, error);
	nuwa_systemos_flush();
	return error;
}
