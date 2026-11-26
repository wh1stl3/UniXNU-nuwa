#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#ifdef NUWA_RAM_PID1
#include <sys/mount.h>
#endif

#include <linux/fs.h>
#include <linux/magic.h>
#include "nuwa-data-pins.h"

enum {
    PAGE = 4096, PAGES = 770, BYTES = PAGE * PAGES,
    DISK_BLOCKS = 61850624, PART_FIRST = 3110976, PART_END = 61850619,
    META_FIRST = 57393401, WINDOW_END = 61588475,
};
#define OFFSET ((off_t)(META_FIRST - PART_FIRST) * PAGE)
#define AUTHORIZE "--authorize-nuwa-blank-data-init"

_Static_assert(sizeof(off_t) == 8, "64-bit positioned I/O required");
_Static_assert(META_FIRST > PART_FIRST && META_FIRST + PAGES <= WINDOW_END
               && WINDOW_END <= PART_END, "metadata must fit admitted userdata window");
static _Alignas(65536) unsigned char io[BYTES];
static _Alignas(65536) unsigned char payload[BYTES];
static volatile sig_atomic_t interrupted;
static const char *last_write;
#if defined(NUWA_RAM_PID1) && !NUWA_RAM_ARMED
#define NUWA_STRICT_READ_ONLY
static bool recovery_sb0;
#endif
#ifndef NUWA_HOST_FIXTURE
static int target_fd = -1, disk_fd = -1, receipt_fd = -1;
#endif

static _Noreturn void refuse(const char *why)
{
    fprintf(stderr, "STOP: %s%s%s\n", why, last_write ?
            "; media completion uncertain after attempt: " : "", last_write ?: "");
    exit(1);
}

static void sysfail(const char *why)
{
    if (errno) perror(why);
    refuse(why);
}

static void exact(ssize_t got, size_t want, const char *why)
{
    if (got < 0) sysfail(why);
    if ((size_t)got != want) {
        fprintf(stderr, "%s: got %zd of %zu bytes\n", why, got, want);
        refuse("short I/O");
    }
    if (interrupted) refuse("interrupted");
}

static void stop_signal(int signum)
{
    interrupted = signum;
}

static void check(int result, const char *why)
{
    if (result < 0) sysfail(why);
}

#ifndef NUWA_STRICT_READ_ONLY
static void receipts(int dir, const char *name)
{
    int fd = openat(dir, name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    check(fd, name);
    exact(write(fd, io, BYTES), BYTES, name);
    check(close(fd), "close RAM readback");
}

static void read_meta(int fd, const char *why)
{
    exact(pread(fd, io, BYTES, OFFSET), BYTES, why);
    if (memcmp(io, payload, BYTES)) refuse(why);
}

static void write_meta(int fd, size_t len, const char *why)
{
    if (interrupted) refuse("interrupted before write");
    last_write = why;
    exact(pwrite(fd, payload, len, OFFSET), len, why);
    check(fsync(fd), "target fsync");
    if (interrupted) refuse("interrupted after fsync");
}
#endif

static void gpt_check(int disk)
{
    const struct {
        off_t lba;
        const unsigned char *pin;
    } gpt[] = {
        {1, primary_header}, {2, primary_entries},
        {DISK_BLOCKS - 1, backup_header}, {PART_END, primary_entries},
    };
    for (size_t i = 0; i < sizeof(gpt) / sizeof(gpt[0]); i++) {
        exact(pread(disk, io, PAGE, gpt[i].lba * PAGE), PAGE, "GPT direct read");
        if (memcmp(io, gpt[i].pin, PAGE)) refuse("live dual GPT differs from validated capture");
    }
}

static void transaction(int fd, bool authorize, int dir)
{
#ifdef NUWA_STRICT_READ_ONLY
    (void)dir;
    if (authorize) refuse("read-only recovery build");
    exact(pread(fd, io, BYTES, OFFSET), BYTES, "recovery metadata read");
    recovery_sb0 = !memcmp(io, sb0, PAGE);
    if (memcmp(io + PAGE, payload + PAGE, BYTES - PAGE)
        || (!recovery_sb0 && memcmp(io, payload, PAGE)))
        refuse("recovery metadata neither blank nor exact initial SB0");
#else
    read_meta(fd, "metadata preimage not zero or unreadable");
    if (!authorize) return;
    write_meta(fd, BYTES, "prepare write");
    read_meta(fd, "prepare direct readback");
    receipts(dir, "prepare-readback.bin");
    memcpy(payload, sb0, PAGE);
    write_meta(fd, PAGE, "SB0 write");
    read_meta(fd, "SB0 direct readback");
    receipts(dir, "commit-readback.bin");
#endif
}

#ifndef NUWA_RAM_PID1
static bool mode(int argc, char **argv)
{
    if (argc == 1) return false;
    if (argc == 2 && !strcmp(argv[1], AUTHORIZE)) return true;
    refuse("usage: nuwa-data-init [" AUTHORIZE "]");
}
#endif

static void signals(void)
{
    struct sigaction sa = { .sa_handler = stop_signal };
    sigemptyset(&sa.sa_mask);
    check(sigaction(SIGINT, &sa, NULL), "sigaction INT");
    check(sigaction(SIGTERM, &sa, NULL), "sigaction TERM");
    check(sigaction(SIGHUP, &sa, NULL), "sigaction HUP");
    check(sigaction(SIGQUIT, &sa, NULL), "sigaction QUIT");
}

#ifndef NUWA_HOST_FIXTURE
#define DISK "/dev/block/sda"
#define PART "/dev/block/sda32"
#define PART_SYS "/sys/dev/block/259:16"
#define DISK_SYS "/sys/dev/block/8:0"
#define SCSI "/sys/class/scsi_device/0:0:0:0/device"
#define UFS "/sys/bus/platform/devices/1d84000.ufshc"

static bool fs_magic(const char *path, long magic)
{
    struct statfs fs;
    return statfs(path, &fs) == 0 && fs.f_type == magic;
}

static void attr(const char *path, const char *value)
{
    char got[128];
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    check(fd, path);
    exact(read(fd, got, sizeof(got)), strlen(value), path);
    if (memcmp(got, value, strlen(value))) refuse(path);
    check(close(fd), path);
}

static void resolve(const char *path, char result[PATH_MAX])
{
    if (!realpath(path, result)) sysfail(path);
}

static void topology(void)
{
    char part[PATH_MAX], disk[PATH_MAX], scsi[PATH_MAX], ufs[PATH_MAX], link[PATH_MAX];
    resolve(PART_SYS, part);
    resolve(DISK_SYS, disk);
    resolve(DISK_SYS "/device", scsi);
    resolve(UFS, ufs);
    resolve(SCSI, link);
    if (strcmp(scsi, link) || strncmp(scsi, ufs, strlen(ufs)) || scsi[strlen(ufs)] != '/')
        refuse("sda is not Qualcomm UFS SCSI 0:0:0:0");
    if (strncmp(disk, scsi, strlen(scsi)) || strcmp(disk + strlen(scsi), "/block/sda")
        || strncmp(part, disk, strlen(disk)) || strcmp(part + strlen(disk), "/sda32"))
        refuse("sda32 sysfs parent is not sda/LU0");
    attr(SCSI "/vendor", "KIOXIA  \n");
    attr(SCSI "/model", "THGJFJT1E45BATPC\n");
    attr(SCSI "/rev", "0300\n");
    attr(PART_SYS "/partition", "32\n");
    attr(PART_SYS "/start", "24887808\n");
    attr(PART_SYS "/size", "469917144\n");
    attr(DISK_SYS "/size", "494804992\n");
    attr(DISK_SYS "/queue/logical_block_size", "4096\n");
}

static void device_stat(const struct stat *st, unsigned maj, unsigned min, const char *why)
{
    if (!S_ISBLK(st->st_mode) || st->st_rdev != makedev(maj, min)) refuse(why);
}

static void dev_open(int *slot, const char *path, int flags, unsigned maj, unsigned min, uint64_t blocks)
{
    struct stat st;
    uint64_t size;
    int logical;
    check(lstat(path, &st), path);
    device_stat(&st, maj, min, path);
    int fd = open(path, flags | O_DIRECT | O_CLOEXEC | O_NOFOLLOW);
    check(fd, path);
    *slot = fd;
    check(fstat(fd, &st), path);
    device_stat(&st, maj, min, path);
    check(ioctl(fd, BLKSSZGET, &logical), "BLKSSZGET");
    check(ioctl(fd, BLKGETSIZE64, &size), "BLKGETSIZE64");
    if (logical != PAGE || size != blocks * PAGE) refuse("unexpected fd geometry");
}

static DIR *directory(const char *path)
{
    DIR *d = opendir(path);
    if (!d) sysfail(path);
    return d;
}

static struct dirent *next(DIR *d)
{
    errno = 0;
    struct dirent *e = readdir(d);
    if (!e && errno) sysfail("readdir");
    return e;
}

static bool dots(const char *name)
{
    return !strcmp(name, ".") || !strcmp(name, "..");
}

static FILE *text(const char *path)
{
    FILE *f = fopen(path, "re");
    if (!f) sysfail(path);
    return f;
}

static void empty(const char *path)
{
    DIR *d = directory(path);
    for (struct dirent *e; (e = next(d));)
        if (!dots(e->d_name)) refuse(path);
    check(closedir(d), path);
}

static void mount_check(void)
{
    FILE *f = text("/proc/1/mountinfo");
    char *line = NULL;
    size_t n = 0;
    while (getline(&line, &n, f) >= 0) {
        const char *sep = strstr(line, " - ");
        unsigned maj, min;
        char type[32];
        if (!sep || sscanf(line, "%*u %*u %u:%u", &maj, &min) != 2
            || sscanf(sep + 3, "%31s", type) != 1)
            refuse("malformed mountinfo");
        if (maj != 0 || (strcmp(type, "rootfs") && strcmp(type, "ramfs")
            && strcmp(type, "tmpfs") && strcmp(type, "devtmpfs")
            && strcmp(type, "proc") && strcmp(type, "sysfs") && strcmp(type, "devpts")))
            refuse("mount outside offline RAM allowlist");
    }
    if (!feof(f) || !line) refuse("incomplete mountinfo");
    free(line);
    check(fclose(f), "mountinfo close");
}

static void process_check(void)
{
    DIR *d = directory("/proc");
    for (struct dirent *e; (e = next(d));) {
        if (strspn(e->d_name, "0123456789") != strlen(e->d_name)
            || !strcmp(e->d_name, "1")) continue;
        char path[PATH_MAX], *line = NULL;
        size_t n = 0;
        unsigned long flags;
        snprintf(path, sizeof(path), "/proc/%s/stat", e->d_name);
        FILE *f = text(path);
        if (getline(&line, &n, f) < 0) refuse("unreadable process stat");
        char *end = strrchr(line, ')');
        // Linux 5.15 sched.h: PF_KTHREAD = 0x00200000.
        if (!end || sscanf(end + 1, " %*c %*d %*d %*d %*d %*d %lu", &flags) != 1
            || !(flags & 0x00200000UL)) refuse("another userspace producer is present");
        free(line);
        check(fclose(f), path);
    }
    check(closedir(d), "/proc close");
}

static void inherited_fds(void)
{
    DIR *d = directory("/proc/self/fd");
    unsigned stdio = 0;
    for (struct dirent *e; (e = next(d));) {
        if (dots(e->d_name)) continue;
        int fd = atoi(e->d_name);
        if (fd == dirfd(d)) continue;
        struct stat st;
        check(fstat(fd, &st), "inherited fd");
        // Positive allowlist: excludes raw block aliases, sg, bsg, dm-control,
        // configfs/sysfs fds, sockets and inherited async-I/O handles alike.
        if (fd > 2 || !S_ISCHR(st.st_mode)
            || (st.st_rdev != makedev(5, 1) && (fd != 0 || st.st_rdev != makedev(1, 3))))
            refuse("unexpected inherited fd; only console or null stdio permitted");
        stdio |= 1U << fd;
    }
    check(closedir(d), "fd directory close");
    if (stdio != 7) refuse("offline console stdio missing");
}

static void offline(void)
{
    char self[PATH_MAX];
    ssize_t n = readlink("/proc/self", self, sizeof(self));
    if (getpid() != 1 || n != 1 || self[0] != '1')
        refuse("write requires helper as sole userspace PID 1 in reviewed offline RAM boot");
    if (!fs_magic("/", RAMFS_MAGIC) && !fs_magic("/", TMPFS_MAGIC))
        refuse("root is not RAM");
    if (!fs_magic("/proc", PROC_SUPER_MAGIC) || !fs_magic("/sys", SYSFS_MAGIC))
        refuse("missing procfs/sysfs");
    inherited_fds();
    mount_check();
    process_check();
    FILE *f = text("/proc/swaps");
    char header[256];
    if (!fgets(header, sizeof(header), f) || fgetc(f) != EOF || !feof(f) || ferror(f))
        refuse("swap enabled or unreadable");
    check(fclose(f), "swaps close");
    attr("/sys/class/udc/a600000.dwc3/state", "not attached\n");
}

static void open_receipts(void)
{
    struct statfs fs;
    check(mkdir("/tmp/nuwa-data-init-receipts", 0700), "new RAM receipt directory");
    receipt_fd = open("/tmp/nuwa-data-init-receipts", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    check(receipt_fd, "RAM receipt directory");
    check(fstatfs(receipt_fd, &fs), "RAM receipt fs");
    if (fs.f_type != TMPFS_MAGIC && fs.f_type != RAMFS_MAGIC) refuse("receipts not in RAM");
}

static void close_checked(int *slot, const char *why)
{
    int fd = *slot;
    *slot = -1;
    check(close(fd), why);
}

static void run(bool authorize)
{
#ifdef NUWA_STRICT_READ_ONLY
    if (authorize) refuse("read-only recovery build");
#endif
    struct stat st;
    if (geteuid() != 0) refuse("root recovery required");
    if (authorize) offline();
    topology();
    if (lstat("/dev/block/by-name/userdata", &st) == 0) {
        check(stat("/dev/block/by-name/userdata", &st), "resolve userdata alias");
        device_stat(&st, 259, 16, "userdata alias mismatch");
    } else if (errno != ENOENT || !authorize) {
        sysfail("userdata alias");
    }
    dev_open(&target_fd, PART, O_EXCL | (authorize ? O_RDWR : O_RDONLY),
             259, 16, PART_END - PART_FIRST);
    dev_open(&disk_fd, DISK, O_RDONLY, 8, 0, DISK_BLOCKS);
    gpt_check(disk_fd);
    close_checked(&disk_fd, "close read-only parent");
    if (authorize) {
        int readonly;
        check(ioctl(target_fd, BLKROGET, &readonly), "BLKROGET");
        if (readonly) refuse("partition is read-only");
        empty(DISK_SYS "/holders");
        empty(PART_SYS "/holders");
        open_receipts();
    }
    transaction(target_fd, authorize, receipt_fd);
    if (authorize) close_checked(&receipt_fd, "close receipt directory");
    close_checked(&target_fd, "close target claim");
    if (interrupted) refuse("interrupted");
}

static void hold_pid1(void)
{
    if (getpid() == 1) {
        // On refusal, release any still-open descriptor before parking init.
        if (receipt_fd >= 0) close(receipt_fd);
        if (disk_fd >= 0) close(disk_fd);
        if (target_fd >= 0) close(target_fd);
        fflush(NULL);
        for (;;) pause();
    }
}

#ifdef NUWA_RAM_PID1
#include "nuwa-ufs-ram-pid1.h"
#else
int main(int argc, char **argv)
{
    if (atexit(hold_pid1)) refuse("atexit");
    bool authorize = mode(argc, argv);
    signals();
    run(authorize);
    puts(authorize ? "complete: two matching direct readbacks; durability not certified"
                   : "read-only: pinned GPT and blank metadata");
    return 0;
}
#endif
#else
// Native, separately built test entry: regular files only, inherited direct
// descriptors; never shipped in the recovery ELF.
static int fixture_fd(const char *key)
{
    const char *value = getenv(key);
    if (!value || strspn(value, "0123456789") != strlen(value)) refuse("fixture fd argument");
    int fd = atoi(value);
    if (fd < 3) refuse("fixture fd must not be stdio");
    return fd;
}

int main(int argc, char **argv)
{
    bool authorize = mode(argc, argv);
    signals();
    struct stat st;
    int target = fixture_fd("NUWA_TEST_TARGET"), disk = fixture_fd("NUWA_TEST_DISK");
    int dir = fixture_fd("NUWA_TEST_RECEIPTS");
    check(fstat(target, &st), "fixture target");
    if (!S_ISREG(st.st_mode) || !(fcntl(target, F_GETFL) & O_DIRECT)) refuse("not a direct-file fixture");
    check(fstat(disk, &st), "fixture disk");
    if (!S_ISREG(st.st_mode) || !(fcntl(disk, F_GETFL) & O_DIRECT)) refuse("not a direct-file disk");
    gpt_check(disk);
    transaction(target, authorize, dir);
    return 0;
}
#endif
