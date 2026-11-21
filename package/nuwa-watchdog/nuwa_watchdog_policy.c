/*
 * r34: launchd disabled.plist policy for nuwa, ported from the upstream
 * package/BootWatchdogPolicy.c (see SOURCE.md for the repository, commit and licence).
 *
 * Why it exists here: this board has no IOWatchdog.  When watchdogd starts and finds no
 * watchdog backend it traps (`brk #1`), which panics the kernel - the same failure the donor
 * boards recorded.  launchd reads /private/var/db/com.apple.xpc.launchd/disabled.plist before
 * it starts a job, so writing com.apple.watchdogd = true there (plus disabled.migrated, which
 * selects the modern override loader) keeps watchdogd from ever starting.
 *
 * The function runs after the Data volume is mounted writable and before the initproc is
 * exec'd (nuwa_data_mount_prepare's stage 4, which load_init_program reaches after
 * bsd_init()/bsd_autoconf()).  It uses the same in-kernel syscall helpers and the initproc
 * scratch page the SystemOS/Data mounts use: copyout a path to `scratch`, then mkdir/open/
 * write/fchown/fchmod/fsync/fstat/close with that process.
 *
 * Differences from upstream (all recorded in SOURCE.md):
 *   - no Gunyah/uke watchdog petting (this board has neither the backend nor an autoreset);
 *   - no sheng-setup / sheng-data-reset handling (the Data seed is written on the host);
 *   - the boot arguments are the unprefixed names this kernel documents - disable-watchdogd
 *     and disable-jobs - with the sheng- prefixed spellings still accepted as aliases.
 */
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/proc.h>
#include <sys/sysproto.h>
#include <sys/fcntl.h>
#include <sys/stat.h>
#include <pexpert/pexpert.h>
#include <libkern/libkern.h>

#define NUWA_POLICY_DIR   "/private/var/db/com.apple.xpc.launchd"
#define NUWA_POLICY_PATH  NUWA_POLICY_DIR "/disabled.plist"
#define NUWA_POLICY_MARK  NUWA_POLICY_DIR "/disabled.migrated"

static const char nuwa_policy_head[] =
    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
    "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
    "<plist version=\"1.0\"><dict>";
static const char nuwa_policy_tail[] = "</dict></plist>\n";
/* UniXNU/UniXNU-sheng 460179565a018c741b93e0b1efa07c55d4de497a,
 * package/BootWatchdogPolicy.c, MIT. */
static const char nuwa_lite_jobs[] =
    "com.apple.identityservicesd,com.apple.locationd,com.apple.CommCenter,com.apple.bluetoothd,"
    "com.apple.photoanalysisd,com.apple.mediaanalysisd,com.apple.mediastream.mstreamd,com.apple.icloud.searchpartyd,"
    "com.apple.findmy.findmybeaconingd,com.apple.familycircled,com.apple.financed,com.apple.softwareupdateservicesd,"
    "com.apple.ndoagent,com.apple.biomesyncd,com.apple.email.maild,com.apple.amsengagementd,com.apple.adid,com.apple.eyereliefd,"
    "com.apple.fairplayd.A2,com.apple.passd,com.apple.mobile.obliteration,com.apple.coreduetd,"
    "com.apple.PerfPowerServices,com.apple.PerfPowerServicesExtended,com.apple.perfpowermetricd,com.apple.siriinferenced,"
    "com.apple.siriknowledged,com.apple.siriactionsd,com.apple.duetexpertd,com.apple.modelcatalogd";

static char nuwa_policy[2048];
static char nuwa_policy_jobs[400];

volatile int32_t nuwa_watchdog_policy_status = -1;
volatile uint32_t nuwa_watchdog_policy_labels;

/* "<label>" for one comma-separated entry; label characters are restricted the way upstream
 * restricts them, so a boot argument cannot inject plist markup. */
static int
nuwa_policy_append(const char **cursor)
{
	const char *label = *cursor;
	size_t length = 0;

	while (label[length] && label[length] != ',') {
		char c = label[length];
		if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
		    (c >= '0' && c <= '9') || c == '.' || c == '-')) {
			return EINVAL;
		}
		length++;
	}
	if (length == 0 || length > 127) {
		return EINVAL;
	}
	/* Keys already emitted by this builder are safe to compare literally. */
	for (const char *key = nuwa_policy + strlen(nuwa_policy_head);
	    (key = strstr(key, "<key>")) != NULL; key += 5) {
		if (strncmp(key + 5, label, length) == 0 &&
		    strncmp(key + 5 + length, "</key>", 6) == 0) {
			*cursor = label + length;
			if (**cursor == ',') {
				(*cursor)++;
			}
			return 0;
		}
	}
	{
		size_t used = strlen(nuwa_policy);

		if (used + 5 + length + 13 + 1 > sizeof(nuwa_policy)) {
			return ENAMETOOLONG;
		}
		memcpy(nuwa_policy + used, "<key>", 5);
		used += 5;
		memcpy(nuwa_policy + used, label, length);
		used += length;
		memcpy(nuwa_policy + used, "</key><true/>", 13);
		used += 13;
		nuwa_policy[used] = 0;
	}
	nuwa_watchdog_policy_labels++;
	*cursor = label + length;
	if (**cursor == ',') {
		(*cursor)++;
	}
	return 0;
}

/* Build completely before touching the persistent plist. */
static int
nuwa_policy_build(unsigned disable_watchdogd, unsigned lite, const char *jobs)
{
	int error;
	const char *cursor;

	nuwa_policy[0] = 0;
	nuwa_watchdog_policy_labels = 0;
	if (strlcat(nuwa_policy, nuwa_policy_head, sizeof(nuwa_policy)) >= sizeof(nuwa_policy)) {
		return ENAMETOOLONG;
	}
	if (disable_watchdogd) {
		cursor = "com.apple.watchdogd,com.apple.watchdog";
		while (*cursor) {
			if ((error = nuwa_policy_append(&cursor)) != 0) return error;
		}
	}
	if (lite == 1 || lite == 2) {
		cursor = nuwa_lite_jobs;
		while (*cursor) {
			if ((error = nuwa_policy_append(&cursor)) != 0) return error;
		}
	}
	if (lite == 2) {
		cursor = "com.apple.iconservices.iconservicesagent";
		if ((error = nuwa_policy_append(&cursor)) != 0) return error;
	}
	while (*jobs) {
		if ((error = nuwa_policy_append(&jobs)) != 0) return error;
	}
	if (strlcat(nuwa_policy, nuwa_policy_tail, sizeof(nuwa_policy)) >= sizeof(nuwa_policy)) {
		return ENAMETOOLONG;
	}
	return 0;
}

static int
nuwa_policy_parse_uint(const char *name, unsigned *value)
{
	unsigned v = 0;

	*value = 0;
	if (PE_parse_boot_argn(name, &v, sizeof(v))) {
		*value = v;
		return 1;
	}
	return 0;
}

/* Returns 0 when the policy was written or nothing was asked for, an errno otherwise.
 * `process` is the initproc and `scratch` its one-page scratch area; both come from
 * load_init_program() exactly as the SystemOS and Data mounts receive them. */
int
nuwa_boot_watchdog_policy(void *process, uint64_t scratch)
{
	proc_t p = process;
	unsigned disable_watchdogd = 0;
	unsigned lite = 0;
	int error = 0, fd = -1;
	int32_t result = 0;

	if (p == PROC_NULL) {
		return EINVAL;
	}
	/* Unprefixed names first; the sheng- spellings stay accepted so an image built with the
	 * upstream argument list behaves the same. */
	if (!nuwa_policy_parse_uint("disable-watchdogd", &disable_watchdogd)) {
		(void)nuwa_policy_parse_uint("sheng-disable-watchdogd", &disable_watchdogd);
	}
	if (!PE_parse_boot_argn("disable-jobs", nuwa_policy_jobs, sizeof(nuwa_policy_jobs))) {
		if (!PE_parse_boot_argn("sheng-disable-jobs", nuwa_policy_jobs,
		    sizeof(nuwa_policy_jobs))) {
			nuwa_policy_jobs[0] = 0;
		}
	}
	nuwa_policy_jobs[sizeof(nuwa_policy_jobs) - 1] = 0;
	(void)nuwa_policy_parse_uint("nuwa-lite", &lite);
	if (lite != 1 && lite != 2) {
		lite = 0;
	}

	if (disable_watchdogd != 1) {
		disable_watchdogd = 0;
	}
	if (!disable_watchdogd && !lite && nuwa_policy_jobs[0] == 0) {
		nuwa_watchdog_policy_labels = 0;
		nuwa_watchdog_policy_status = 0;
		return 0;
	}

	if ((error = nuwa_policy_build(disable_watchdogd, lite, nuwa_policy_jobs)) != 0) {
		nuwa_watchdog_policy_status = error;
		printf("nuwa: launchd disabled policy build failed: %d labels=%u\n",
		    error, (unsigned)nuwa_watchdog_policy_labels);
		return error;
	}

	if ((error = copyout(NUWA_POLICY_DIR, scratch, sizeof(NUWA_POLICY_DIR))) != 0) {
		goto done;
	}
	{
		struct mkdir_args md = { .path = scratch, .mode = 0755 };
		error = mkdir(p, &md, &result);
		if (error && error != EEXIST) {
			goto done;
		}
	}
	if ((error = copyout(NUWA_POLICY_PATH, scratch, sizeof(NUWA_POLICY_PATH))) != 0) {
		goto done;
	}
	{
		/* Rewritten in place on every boot (the policy must follow the boot arguments);
		 * O_NOFOLLOW and the fstat check below insist on a root-owned regular file. */
		struct open_args op = {
			.path = scratch,
			.flags = O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW,
			.mode = 0644,
		};
		if ((error = open(p, &op, &result)) != 0) {
			goto done;
		}
		fd = result;
	}
	{
		/* The scratch page keeps the cache-mount environment slots at +0x400, so the
		 * policy goes out through the 0x200 bytes at +0x200. */
		size_t sent = 0, total = strlen(nuwa_policy);
		while (sent < total) {
			size_t piece = total - sent < 0x1f0 ? total - sent : 0x1f0;
			struct write_args wr;
			user_ssize_t written = 0;

			if ((error = copyout(nuwa_policy + sent, scratch + 0x200, piece)) != 0) {
				goto done;
			}
			wr.fd = fd;
			wr.cbuf = scratch + 0x200;
			wr.nbyte = piece;
			if ((error = write(p, &wr, &written)) != 0) {
				goto done;
			}
			if (written != (user_ssize_t)piece) {
				error = EIO;
				goto done;
			}
			sent += piece;
		}
	}
	{
		struct fchown_args owner = { .fd = fd, .uid = 0, .gid = 0 };
		struct fchmod_args mode = { .fd = fd, .mode = 0644 };
		struct fsync_args sync = { .fd = fd };
		struct fstat64_args sa;
		struct stat64 st;

		if ((error = fchown(p, &owner, &result)) != 0 ||
		    (error = fchmod(p, &mode, &result)) != 0 ||
		    (error = fsync(p, &sync, &result)) != 0) {
			goto done;
		}
		memset(&st, 0, sizeof(st));
		sa.fd = fd;
		sa.ub = scratch + 0x800;
		if ((error = sys_fstat64(p, &sa, &result)) != 0 ||
		    (error = copyin(sa.ub, &st, sizeof(st))) != 0) {
			goto done;
		}
		if (st.st_uid != 0 || st.st_gid != 0 || !S_ISREG(st.st_mode) ||
		    (st.st_mode & 0777) != 0644 || st.st_size != (off_t)strlen(nuwa_policy)) {
			error = EINVAL;
			goto done;
		}
	}
done:
	if (fd >= 0) {
		struct close_args cl = { .fd = fd };
		int e = sys_close(p, &cl, &result);
		if (!error) {
			error = e;
		}
	}
	/* A real empty migration marker selects the qualified modern override loader. */
	if (!error) {
		if ((error = copyout(NUWA_POLICY_MARK, scratch, sizeof(NUWA_POLICY_MARK))) == 0) {
			struct open_args mark = {
				.path = scratch,
				.flags = O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW,
				.mode = 0644,
			};
			error = open(p, &mark, &result);
			if (!error) {
				struct close_args cl = { .fd = result };
				error = sys_close(p, &cl, &result);
			} else if (error == EEXIST) {
				error = 0;
			}
		}
	}
	nuwa_watchdog_policy_status = error;
	printf("nuwa: launchd disabled policy: %d labels=%u (watchdogd=%u)\n", error,
	    (unsigned)nuwa_watchdog_policy_labels, disable_watchdogd);
	return error;
}
