/* Included only by the standalone, statically linked recovery PID 1. */
#include <linux/input.h>
#include <linux/usb/functionfs.h>
#include <poll.h>
#include <stddef.h>

#define RUN_ID NUWA_RAM_RUN_ID
#define FFS "/run/nuwa-ffs"
#define GADGET "/config/usb_gadget/nuwa"
#define REC_DIR "/tmp/nuwa-data-init-receipts/"
_Static_assert(sizeof(RUN_ID) == 33, "32 ASCII hex run ID");

static void tx_bytes(int fd, const void *bytes, size_t size)
{
    // This is the USB stream, not target/media I/O.
    for (const unsigned char *p = bytes; size;) {
        if (interrupted) refuse("export interrupted");
        size_t chunk = size > 16384 ? 16384 : size;
        ssize_t n = write(fd, p, chunk);
        if (n < 0) sysfail("export write");
        if (!n) refuse("empty export write");
        size -= (size_t)n;
        p += n;
    }
}

static void stream_receipt(int fd, bool wrote, bool initialized, const char *prepare, const char *commit)
{
    const char *head = wrote ? "NUWARAM1 WRITE " RUN_ID "\n"
        : (initialized ? "NUWARAM1 CHECK-SB0 " RUN_ID "\n" : "NUWARAM1 CHECK-BLANK " RUN_ID "\n");
    static const char final[] = "NUWARAM1 FINAL " RUN_ID " CLAIM-CLOSED\n";
    tx_bytes(fd, head, strlen(head));
    if (wrote) {
        const char *paths[] = { prepare, commit };
        for (size_t i = 0; i < 2; i++) {
            int input = open(paths[i], O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
            check(input, "open RAM readback for export");
            struct stat s;
            check(fstat(input, &s), "RAM readback fstat");
            if (!S_ISREG(s.st_mode) || s.st_size != BYTES) refuse("invalid exported readback");
            exact(read(input, io, BYTES), BYTES, "read RAM receipt for export");
            check(close(input), "close RAM receipt file");
            tx_bytes(fd, io, BYTES);
        }
    }
    tx_bytes(fd, final, sizeof(final) - 1);
}

#ifdef NUWA_RAM_EXPORT_FIXTURE
int main(int argc, char **argv)
{
    // Separate host binary; validate an actual framer without touching a device.
    if (argc != 3) return 2;
    stream_receipt(STDOUT_FILENO, true, false, argv[1], argv[2]);
    return 0;
}
#else
static int export_ep0 = -1, export_ep1 = -1;
static bool gadget_bound;

static void export_cleanup(void)
{
    if (export_ep1 >= 0) close(export_ep1);
    if (gadget_bound) {
        int fd = open(GADGET "/UDC", O_WRONLY | O_NOFOLLOW | O_CLOEXEC);
        if (fd >= 0) {
            if (write(fd, "\n", 1) != 1) perror("export cleanup unbind");
            close(fd);
        }
    }
    if (export_ep0 >= 0) close(export_ep0);
}

static void directory_new(const char *path, mode_t mode)
{
    if (mkdir(path, mode) < 0 && errno != EEXIST) sysfail(path);
    struct stat s;
    check(lstat(path, &s), path);
    if (!S_ISDIR(s.st_mode)) refuse(path);
}

static void node(const char *path, mode_t kind, unsigned maj, unsigned min)
{
    if (mknod(path, kind | 0600, makedev(maj, min))) sysfail(path);
}

static void setup_ram(void)
{
    if (getpid() != 1 || geteuid() || (!fs_magic("/", RAMFS_MAGIC) && !fs_magic("/", TMPFS_MAGIC)))
        refuse("not RAM recovery PID 1");
    directory_new("/proc", 0555);
    directory_new("/sys", 0555);
    directory_new("/dev", 0755);
    directory_new("/tmp", 0700);
    directory_new("/run", 0700);
    check(mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, ""), "mount proc");
    check(mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, ""), "mount sysfs");
    check(mount("tmpfs", "/dev", "tmpfs", MS_NOSUID | MS_NOEXEC, "mode=0755"), "mount RAM dev");
    check(mount("tmpfs", "/tmp", "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "mode=0700"), "mount RAM tmp");
    node("/dev/console", S_IFCHR, 5, 1);
    int c = open("/dev/console", O_RDWR | O_NOCTTY);
    check(c, "console");
    for (int i = 0; i < 3; i++) check(dup2(c, i), "console dup");
    if (c > 2) check(close(c), "console close");
    directory_new("/dev/block", 0700);
    directory_new("/dev/block/by-name", 0700);
    node(DISK, S_IFBLK, 8, 0);
    node(PART, S_IFBLK, 259, 16);
    check(symlink("../sda32", "/dev/block/by-name/userdata"), "private userdata alias");
}

static void put_attr(const char *path, const char *value)
{
    int fd = open(path, O_WRONLY | O_NOFOLLOW | O_CLOEXEC);
    check(fd, path);
    exact(write(fd, value, strlen(value)), strlen(value), path);
    check(close(fd), path);
}

#if NUWA_RAM_ARMED
static int key_fd(const char *name, int code, const char *private_node)
{
    DIR *d = directory("/sys/class/input");
    int found = -1;
    for (struct dirent *e; (e = next(d));) {
        if (strncmp(e->d_name, "event", 5)) continue;
        char path[PATH_MAX], line[128];
        snprintf(path, sizeof(path), "/sys/class/input/%s/device/name", e->d_name);
        FILE *f = text(path);
        if (!fgets(line, sizeof(line), f)) refuse("unreadable input name");
        check(fclose(f), path);
        line[strcspn(line, "\n")] = 0;
        if (strcmp(line, name)) continue;
        if (found >= 0) refuse("ambiguous confirmation input");
        unsigned maj, min;
        snprintf(path, sizeof(path), "/sys/class/input/%s/dev", e->d_name);
        f = text(path);
        if (fscanf(f, "%u:%u", &maj, &min) != 2) refuse("input devnum");
        check(fclose(f), path);
        node(private_node, S_IFCHR, maj, min);
        found = open(private_node, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
        check(found, "open confirmation input");
        unsigned char bits[(KEY_MAX + 8) / 8] = {0};
        if (ioctl(found, EVIOCGBIT(EV_KEY, sizeof(bits)), bits) <= code / 8
            || !(bits[code / 8] & (1U << (code % 8)))) refuse("physical key capability");
    }
    check(closedir(d), "input dir close");
    if (found < 0) refuse("physical confirmation input not ready");
    return found;
}

static void confirm_keys(void)
{
    // DT: gpio-keys=0x73; pmic_resin=0x72. Fixed down/up/down press-release
    // sequence; simultaneous/held, repeats, lost events and other key input fail.
    const int keys[] = { KEY_VOLUMEDOWN, KEY_VOLUMEUP };
    const int sequence[] = { 0, 1, 0 };
    struct pollfd p[] = {
        {key_fd("pmic_resin", keys[0], "/dev/nuwa-down"), POLLIN, 0},
        {key_fd("gpio-keys", keys[1], "/dev/nuwa-up"), POLLIN, 0},
    };
    for (size_t i = 0; i < 2; i++) {
        unsigned char state[(KEY_MAX + 8) / 8] = {0};
        check(ioctl(p[i].fd, EVIOCGKEY(sizeof(state)), state), "read present key state");
        if (state[keys[i] / 8] & (1U << (keys[i] % 8))) refuse("key held at entry");
    }
    alarm(60);
    for (size_t step = 0; step < 6;) {
        if (interrupted || poll(p, 2, -1) != 1) refuse("confirmation interrupted or ambiguous");
        for (int i = 0; i < 2; i++) {
            if (!p[i].revents) continue;
            if (p[i].revents != POLLIN) refuse("input device lost");
            struct input_event ev;
            exact(read(p[i].fd, &ev, sizeof(ev)), sizeof(ev), "read physical confirmation");
            if (ev.type == EV_SYN && ev.code == SYN_DROPPED) refuse("input events dropped");
            if (ev.type != EV_KEY) continue;
            if (i != sequence[step / 2] || ev.code != keys[i] || ev.value != !(step % 2))
                refuse("physical confirmation mismatch");
            step++;
        }
    }
    check(close(p[0].fd), "close volume down");
    check(close(p[1].fd), "close volume up");
    alarm(0);
    if (interrupted) refuse("confirmation expired");
}
#endif

struct speed_descriptors {
    struct usb_interface_descriptor iface;
    struct usb_endpoint_descriptor_no_audio endpoint;
} __attribute__((packed));

#define SPEED(packet) { \
    { .bLength = USB_DT_INTERFACE_SIZE, .bDescriptorType = USB_DT_INTERFACE, \
      .bNumEndpoints = 1, .bInterfaceClass = USB_CLASS_VENDOR_SPEC, .iInterface = 1 }, \
    { .bLength = USB_DT_ENDPOINT_SIZE, .bDescriptorType = USB_DT_ENDPOINT, \
      .bEndpointAddress = USB_DIR_IN | 1, .bmAttributes = USB_ENDPOINT_XFER_BULK, \
      .wMaxPacketSize = (packet) } }

static void export_once(bool wrote)
{
    // Never expose USB during claim or preflight. Do not give ep0 a command
    // handler, OUT endpoint, mass-storage function, or a shell.
    if (target_fd != -1 || disk_fd != -1 || receipt_fd != -1 || interrupted)
        refuse("export before successful claim close");
    directory_new("/config", 0700);
    directory_new(FFS, 0700);
    check(mount("configfs", "/config", "configfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, ""),
          "mount export configfs");
    directory_new(GADGET, 0700);
    put_attr(GADGET "/idVendor", "0x1d6b");
    put_attr(GADGET "/idProduct", "0x0104");
    put_attr(GADGET "/max_speed", "high-speed");
    directory_new(GADGET "/strings/0x409", 0700);
    put_attr(GADGET "/strings/0x409/serialnumber", RUN_ID);
    put_attr(GADGET "/strings/0x409/product", "nuwa receipt only");
    directory_new(GADGET "/configs/c.1", 0700);
    directory_new(GADGET "/functions/ffs.receipt", 0700);
    check(mount("receipt", FFS, "functionfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, ""),
          "mount receipt FunctionFS");
    export_ep0 = open(FFS "/ep0", O_RDWR | O_CLOEXEC);
    check(export_ep0, "open FunctionFS ep0");
    // The AArch64 ELF is little endian, as are the FunctionFS UAPI fields.
    const struct {
        struct usb_functionfs_descs_head_v2 head;
        uint32_t full_count, high_count;
        struct speed_descriptors full, high;
    } __attribute__((packed)) desc = {
        { FUNCTIONFS_DESCRIPTORS_MAGIC_V2, sizeof(desc),
          FUNCTIONFS_HAS_FS_DESC | FUNCTIONFS_HAS_HS_DESC }, 2, 2, SPEED(64), SPEED(512)
    };
    const struct {
        struct usb_functionfs_strings_head head;
        uint16_t lang;
        char iface[sizeof("nuwa receipt")];
    } __attribute__((packed)) strs = {
        { FUNCTIONFS_STRINGS_MAGIC, sizeof(strs), 1, 1 }, 0x0409, "nuwa receipt"
    };
    exact(write(export_ep0, &desc, sizeof(desc)), sizeof(desc), "install IN-only descriptors");
    exact(write(export_ep0, &strs, sizeof(strs)), sizeof(strs), "install FunctionFS strings");
    check(symlink("../../functions/ffs.receipt", GADGET "/configs/c.1/receipt"),
          "link IN-only configuration");
    struct sigaction sa = { .sa_handler = stop_signal };
    sigemptyset(&sa.sa_mask);
    check(sigaction(SIGALRM, &sa, NULL), "export alarm handler");
    printf("NUWA POST-CLAIM EXPORT %s\n", RUN_ID);
    fflush(stdout);
    alarm(120);
    gadget_bound = true; // cleanup covers ambiguity in the bind/close result
    put_attr(GADGET "/UDC", "a600000.dwc3");
    for (;;) {
        struct usb_functionfs_event event;
        exact(read(export_ep0, &event, sizeof(event)), sizeof(event), "FunctionFS enable event");
        if (event.type == FUNCTIONFS_ENABLE) break;
        if (event.type != FUNCTIONFS_BIND) refuse("unexpected FunctionFS control event");
    }
    export_ep1 = open(FFS "/ep1", O_WRONLY | O_CLOEXEC);
    check(export_ep1, "open IN-only FunctionFS data endpoint");
    stream_receipt(export_ep1, wrote,
#if NUWA_RAM_ARMED
                   false,
#else
                   recovery_sb0,
#endif
                   REC_DIR "prepare-readback.bin", REC_DIR "commit-readback.bin");
    close_checked(&export_ep1, "close receipt endpoint");
    put_attr(GADGET "/UDC", "\n");
    gadget_bound = false;
    close_checked(&export_ep0, "close FunctionFS ep0");
    alarm(0);
}

int main(int argc, char **argv)
{
    (void)argv;
    if (atexit(hold_pid1)) refuse("atexit");
    if (atexit(export_cleanup)) refuse("atexit exporter");
    signals();
    if (argc != 1) refuse("RAM PID 1 has no runtime command arguments");
    setup_ram();
    offline();
    run(false);
#if NUWA_RAM_ARMED
    struct sigaction sa = { .sa_handler = stop_signal };
    sigemptyset(&sa.sa_mask);
    check(sigaction(SIGALRM, &sa, NULL), "confirmation alarm handler");
    printf("NUWA WAITING FOR PHYSICAL CONFIRMATION %s\n", RUN_ID);
    fflush(stdout);
    confirm_keys();
    run(true);
    last_write = NULL;
#endif
    export_once(NUWA_RAM_ARMED);
    return 0;
}
#endif
