/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#include <sys/param.h>
#include <sys/systm.h>
#include <sys/proc.h>
#include <sys/sysproto.h>
#include <sys/fcntl.h>
#include <sys/stat.h>
#include <sys/stdio.h>
#include <sys/unistd.h>
#include <pexpert/pexpert.h>
#include <libkern/libkern.h>

#define DATA "/private/var"
#define PREF DATA "/mobile/Library/Preferences"
#define CACHE DATA "/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches"
#define MG_UPPER "com.apple.MobileGestalt.plist"
#define MG_LOWER "com.apple.mobilegestalt.plist"
#define MG_JOURNAL "nuwa-mg-reset.journal"

/* Zero until a requested run completes. One relaxed sample on the page:
 * bit 8 = complete, bit 9 = journal/setup error, low nibbles = renamed/failed. */
uint32_t nuwa_mg_reset_diag;

struct mg_path {
	const char *dir, *name, *backup;
};
static const struct mg_path paths[] = {
	{ PREF, MG_UPPER, MG_UPPER ".nuwa-bak" },
	{ PREF, MG_LOWER, MG_LOWER ".nuwa-bak" },
	{ CACHE, MG_UPPER, MG_UPPER ".nuwa-bak" },
};

struct mg_result {
	const char *exists, *action;
	int error;
};

static int
mg_close(proc_t p, int fd)
{
	struct close_args cl = { .fd = fd };
	int32_t result;
	return sys_close(p, &cl, &result);
}

static int
mg_fstat(proc_t p, user_addr_t scratch, int fd, struct stat64 *st)
{
	struct fstat64_args sa = { .fd = fd, .ub = scratch + 0x800 };
	int32_t result;
	int error = sys_fstat64(p, &sa, &result);
	return error ? error : copyin(sa.ub, st, sizeof(*st));
}

static int
mg_open(proc_t p, user_addr_t scratch, int parent, const char *path, int flags,
    int *fd, struct stat64 *st)
{
	struct openat_args op = {
		.fd = parent, .path = scratch, .flags = flags | O_NOFOLLOW_ANY, .mode = 0600,
	};
	int32_t result;
	int error = copyout(path, op.path, strlen(path) + 1);
	if (!error) {
		error = openat(p, &op, &result);
	}
	if (!error) {
		error = mg_fstat(p, scratch, result, st);
		if (error) {
			(void)mg_close(p, result);
		} else {
			*fd = result;
		}
	}
	return error;
}

static int
mg_dir(proc_t p, user_addr_t scratch, const char *path, dev_t dev, int *fd,
    struct stat64 *st)
{
	int error = mg_open(p, scratch, AT_FDCWD, path, O_RDONLY | O_DIRECTORY, fd, st);
	if (!error && st->st_dev != dev) {
		(void)mg_close(p, *fd);
		*fd = -1;
		return EXDEV;
	}
	return error;
}

static int
mg_lstat(proc_t p, user_addr_t scratch, int fd, user_addr_t slot, const char *name,
    struct stat64 *st)
{
	struct fstatat64_args sa = {
		.fd = fd, .path = slot, .ub = scratch + 0x800, .flag = AT_SYMLINK_NOFOLLOW,
	};
	int32_t result;
	int error = copyout(name, slot, strlen(name) + 1);
	if (!error) {
		error = fstatat64(p, &sa, &result);
	}
	return error ? error : copyin(sa.ub, st, sizeof(*st));
}

static struct mg_result
mg_move(proc_t p, user_addr_t scratch, int fd, const struct mg_path *path, dev_t dev)
{
	struct stat64 st;
	struct renameatx_np_args rn = {
		.fromfd = fd, .from = scratch, .tofd = fd, .to = scratch + 0x100,
		.flags = RENAME_EXCL | RENAME_NOFOLLOW_ANY,
	};
	int32_t result;
	int error = mg_lstat(p, scratch, fd, rn.from, path->name, &st);
	if (error == ENOENT) {
		return (struct mg_result){ "no", "absent", 0 };
	}
	if (error) {
		return (struct mg_result){ "unknown", "source-stat", error };
	}
	if (!S_ISREG(st.st_mode) || st.st_dev != dev) {
		return (struct mg_result){ "yes", "not-a-local-regular-file",
			st.st_dev != dev ? EXDEV : EINVAL };
	}
	error = mg_lstat(p, scratch, fd, rn.to, path->backup, &st);
	if (!error) {
		return (struct mg_result){ "yes", "backup-exists", 0 };
	}
	if (error != ENOENT) {
		return (struct mg_result){ "yes", "backup-stat", error };
	}
	error = renameatx_np(p, &rn, &result);
	if (error == EEXIST) {
		return (struct mg_result){ "yes", "backup-exists", 0 };
	}
	return (struct mg_result){ "yes", error ? "rename" : "renamed", error };
}

static int
mg_log(proc_t p, user_addr_t scratch, int fd, const char *message)
{
	/* The mount helpers reserve +0x400 and up for the exec environment. */
	struct write_args wr = { .fd = fd, .cbuf = scratch + 0x200, .nbyte = strlen(message) };
	user_ssize_t written;
	int error = copyout(message, wr.cbuf, (size_t)wr.nbyte);
	if (!error) {
		error = write(p, &wr, &written);
	}
	return error ? error : (written == (user_ssize_t)wr.nbyte ? 0 : EIO);
}

void nuwa_mg_reset(proc_t p, user_addr_t scratch, int readonly);

void
nuwa_mg_reset(proc_t p, user_addr_t scratch, int readonly)
{
	unsigned enabled = 0, renamed = 0, failed = 0;
	int root = -1, db = -1, journal = -1, pref = -1, cache = -1;
	int journal_error, pref_error, cache_error, sensitive = 1;
	struct stat64 st;
	dev_t dev;
	int32_t result;

	if (!PE_parse_boot_argn("nuwa-mg-reset", &enabled, sizeof(enabled)) || enabled != 1) {
		return;
	}
	journal_error = readonly ? EROFS :
	    mg_open(p, scratch, AT_FDCWD, DATA, O_RDONLY | O_DIRECTORY, &root, &st);
	if (journal_error) {
		goto done;
	}
	dev = st.st_dev;
	journal_error = mg_dir(p, scratch, DATA "/db", dev, &db, &st);
	if (!journal_error && (st.st_uid != 0 || (st.st_mode & 022))) {
		journal_error = EPERM;
	}
	if (!journal_error) {
		journal_error = mg_open(p, scratch, db, MG_JOURNAL,
		    O_WRONLY | O_CREAT | O_APPEND | O_NONBLOCK, &journal, &st);
	}
	if (!journal_error && (!S_ISREG(st.st_mode) || st.st_uid != 0 ||
	    st.st_nlink != 1 || (st.st_mode & 022))) {
		journal_error = EPERM;
	}
	if (journal_error) {
		goto done;
	}
	journal_error = mg_log(p, scratch, journal, "nuwa-mg-reset: begin\n");
	if (journal_error) {
		goto done;
	}

	pref_error = mg_dir(p, scratch, PREF, dev, &pref, &st);
	if (!pref_error) {
		struct fpathconf_args conf = { .fd = pref, .name = _PC_CASE_SENSITIVE };
		pref_error = sys_fpathconf(p, &conf, &sensitive);
		if (!pref_error && sensitive != 0 && sensitive != 1) {
			pref_error = EINVAL;
		}
	}
	cache_error = mg_dir(p, scratch, CACHE, dev, &cache, &st);
	struct mg_result primary;
	for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
		const struct mg_path *path = &paths[i];
		int dir_error = i == 2 ? cache_error : pref_error;
		struct mg_result r;
		if (dir_error == ENOENT && (i == 2 ? cache : pref) < 0) {
			r = (struct mg_result){ "no", "parent-absent", 0 };
		} else if (dir_error) {
			r = (struct mg_result){ "unknown",
				i != 2 && pref >= 0 ? "case-query" : "parent-open", dir_error };
		} else if (i == 1 && !sensitive) {
			r = (struct mg_result){ primary.exists, "case-alias-see-first", 0 };
		} else if (journal_error) {
			r = (struct mg_result){ "unknown", "journal-error-no-attempt", 0 };
		} else {
			r = mg_move(p, scratch, i == 2 ? cache : pref, path, dev);
		}
		if (i == 0) {
			primary = r;
		}
		renamed += !strcmp(r.action, "renamed");
		failed += r.error != 0;
		char line[256];
		snprintf(line, sizeof(line), "%s/%s exists=%s result=%s errno=%d\n",
		    path->dir, path->name, r.exists, r.action, r.error);
		printf("nuwa: MG %s", line);
		if (!journal_error) {
			journal_error = mg_log(p, scratch, journal, line);
		}
	}
	{
		struct fsync_args sync = { .fd = journal };
		int error = fsync(p, &sync, &result);
		if (!journal_error) {
			journal_error = error;
		}
	}
done:
	if (journal >= 0) {
		int error = mg_close(p, journal);
		if (!journal_error) {
			journal_error = error;
		}
	}
	if (cache >= 0) (void)mg_close(p, cache);
	if (pref >= 0) (void)mg_close(p, pref);
	if (db >= 0) (void)mg_close(p, db);
	if (root >= 0) (void)mg_close(p, root);
	printf("nuwa: MG r=%u/%u journal errno=%d\n", renamed, failed, journal_error);
	__atomic_store_n(&nuwa_mg_reset_diag,
	    0x100u | (journal_error ? 0x200u : 0) | renamed | (failed << 4), __ATOMIC_RELAXED);
}
