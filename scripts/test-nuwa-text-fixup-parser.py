#!/usr/bin/env python3
"""Compile the table parser from the committed 8796-native-text-fixup patch and
exercise it on a property that ends exactly at a guard page.

The parser block is extracted from patches/xnu/8796-native-text-fixup.patch, so
this tests the shipped hunk, not a copy. Each scenario places the property bytes
so the last byte sits against a PROT_NONE page: any read past the property end
faults. A canary before the property catches writes outside the table.
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/xnu/8796-native-text-fixup.patch"


def added_block():
    text = PATCH.read_text()
    start = text.index("diff --git a/bsd/kern/ubc_subr.c")
    end = text.index("diff --git a/osfmk/vm/vm_fault.c", start)
    lines = []
    for line in text[start:end].splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    block = "\n".join(lines)
    for needle in ("cs_text_fixup_init", "s + length == end", "unterminated, ignored"):
        if needle not in block:
            raise SystemExit(f"parser block lost {needle!r}")
    return block


STUB_HEADER = """#ifndef TEST_DEVICE_TREE_H
#define TEST_DEVICE_TREE_H
typedef void *DTEntry;
#define kSuccess 0
int SecureDTLookupEntry(const DTEntry searchPoint, const char *pathName, DTEntry *foundEntry);
int SecureDTGetProperty(const DTEntry entry, const char *propertyName,
                        const void **propertyValue, unsigned int *propertySize);
#endif
"""

HARNESS = r"""
#define _GNU_SOURCE
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <pexpert/device_tree.h>

typedef uint64_t memory_object_offset_t;
struct vnode { const char *v_name; };
#define NULLVP ((struct vnode *)0)
#define PAGE_SIZE 4096
#define PAGE_MASK (PAGE_SIZE - 1)
#define os_atomic_inc(p, m) (++*(p))
#define TUNABLE_STR(v, c, a, d) char v[c] = d
#define STARTUP(a, b, c)
#define strnlen test_strnlen
#define strlcpy test_strlcpy

static size_t test_strnlen(const char *s, size_t n) {
    size_t i = 0;
    while (i < n && s[i]) i++;
    return i;
}
static size_t test_strlcpy(char *dst, const char *src, size_t size) {
    size_t len = strlen(src);
    if (size) {
        size_t copy = len < size - 1 ? len : size - 1;
        memcpy(dst, src, copy);
        dst[copy] = 0;
    }
    return len;
}

static const char *g_table;
static unsigned int g_size;
int SecureDTLookupEntry(const DTEntry searchPoint, const char *pathName, DTEntry *foundEntry) {
    (void)searchPoint; (void)pathName; *foundEntry = (DTEntry)1; return 0;
}
int SecureDTGetProperty(const DTEntry entry, const char *propertyName,
                        const void **propertyValue, unsigned int *propertySize) {
    (void)entry; (void)propertyName;
    *propertyValue = g_table; *propertySize = g_size; return 0;
}

BLOCK

static char *guard_place(const char *data, size_t n, char **map, size_t *map_len) {
    long page = sysconf(_SC_PAGESIZE);
    char *base = mmap(NULL, 2 * page, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(base != MAP_FAILED);
    assert(mprotect(base + page, page, PROT_NONE) == 0);
    memset(base, 0xA5, page);
    char *at = base + page - n;
    memcpy(at, data, n);
    *map = base; *map_len = 2 * page;
    return at;
}

static void run(int scenario) {
    static const char valid[] = "good,100,4142,4344\0";
    static const char two[] = "good,100,4142,4344\0good,200,4546,4748\0";
    static const char valid_tail[] = "good,100,4142,4344\0tail,300,494a,4b4c";
    static const char tail_only[] = "tail,300,494a,4b4c";
    static const char malformed[] = "bad,zz,4142,4344\0";
    const char *data; size_t n; unsigned want;
    switch (scenario) {
    case 0: data = valid; n = sizeof(valid) - 1; want = 1; break;
    case 1: data = two; n = sizeof(two) - 1; want = 2; break;
    case 2: data = valid_tail; n = sizeof(valid_tail) - 1; want = 1; break;
    case 3: data = tail_only; n = sizeof(tail_only) - 1; want = 0; break;
    case 4: data = malformed; n = sizeof(malformed) - 1; want = 0; break;
    default: abort();
    }
    char *map; size_t map_len;
    char *at = guard_place(data, n, &map, &map_len);
    g_table = at; g_size = (unsigned int)n;
    cs_text_fixup_init();
    assert(cs_text_fixup_parsed == want);

    for (char *p = map; p < at; p++) {
        if (*p != (char)0xA5) abort();
    }
    if (scenario == 0) {
        char page[PAGE_SIZE];
        memset(page, 'x', sizeof(page));
        page[0x100] = 'A'; page[0x101] = 'B';
        struct vnode vp = { "good" };
        assert(cs_text_fixup_page(&vp, 0, page) == 1);
        assert(page[0x100] == 'C' && page[0x101] == 'D');
        assert(cs_text_fixup_applied == 1);
    }
    munmap(map, map_len);
    printf("scenario %d: parsed=%u ok\n", scenario, cs_text_fixup_parsed);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    run(atoi(argv[1]));
    return 0;
}
""".replace("BLOCK", added_block())


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "pexpert").mkdir()
        (tmp / "pexpert/device_tree.h").write_text(STUB_HEADER)
        source = tmp / "parser.c"
        source.write_text(HARNESS)
        exe = tmp / "parser"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Wno-format",
                        "-I", str(tmp), str(source), "-o", str(exe)], check=True)
        for scenario in range(5):
            subprocess.run([str(exe), str(scenario)], check=True)
    print("text-fixup parser boundary: PASS")


if __name__ == "__main__":
    main()
