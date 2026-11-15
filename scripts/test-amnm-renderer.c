#define AMNM_RENDERER_TEST 1
#include "../package/diagnostics/amnm-panic-screen.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>

const char amnm_reader_binding[1] = {0}, amnm_flag_binding[1] = {0}, amnm_return_binding[1] = {0};
static jmp_buf parked;
static unsigned char panic_text[PANIC_TEXT_BYTES];
static u32 framebuffer[64 * 128], page;
static struct vc_info vinfo = {128, 64, 32, 64*4, (u64)framebuffer};
void amnm_test_park(void) { longjmp(parked, 1); }
unsigned long amnm_test_vinfo(void) { return (unsigned long)&vinfo; }
unsigned long amnm_test_panic_text(void) { return (unsigned long)panic_text; }
unsigned long amnm_test_page(void) { return (unsigned long)&page; }

int main(void) {
    struct { unsigned char before; unsigned char log[PANIC_TEXT_BYTES]; unsigned char after; } buf;
    struct ctx g = {0};
    memset(&buf, 0, sizeof(buf)); buf.before = 0x71; buf.after = 0x72;
    g.log = buf.log;
    const u64 args[] = {0x22, 7, 0x1234, 3, (u64)"abcdef"};
    format(&g, "x=%04x u=%u p=%p %% s=%.*s", args);
    assert(!strcmp((char *)buf.log, "x=0022 u=7 p=0x1234 % s=abc"));
    char longfmt[2201]; memset(longfmt, 'A', 2200); longfmt[2200] = 0;
    memset(buf.log, 0, sizeof(buf.log)); g.logn = 0;
    format(&g, longfmt, args);
    assert(g.logn == 2000 && buf.log[2000] == 0);
    memset(buf.log, 0, sizeof(buf.log)); g.logn = PANIC_TEXT_BYTES-2;
    format(&g, "abcdef", args);
    assert(g.logn == PANIC_TEXT_BYTES-1 && buf.log[PANIC_TEXT_BYTES-1] == 0);
    assert(buf.before == 0x71 && buf.after == 0x72);
    amnm_panic_winner = 0;
    assert(amnm_claim_panic());
    assert(!amnm_claim_panic());
    amnm_panic_winner = 0;
    if (!setjmp(parked)) panic_screen_main("bad %x %%", args);
    assert(strstr((char *)panic_text, "bad 22 %") == (char *)panic_text);
    assert(strstr((char *)panic_text, "C=0/0") && strstr((char *)panic_text, "I=0"));
    unsigned char saved[PANIC_TEXT_BYTES];
    u32 screen_saved[64 * 128];
    memcpy(saved, panic_text, sizeof(saved));
    memcpy(screen_saved, framebuffer, sizeof(screen_saved));
    if (!setjmp(parked)) panic_screen_main("other", args);
    assert(!memcmp(saved, panic_text, sizeof(saved)));
    assert(!memcmp(screen_saved, framebuffer, sizeof(screen_saved)));
    amnm_panic_winner = 0;
    memset(panic_text, 0, sizeof(panic_text));
    memset(framebuffer, 0, sizeof(framebuffer));
    const u64 longargs[] = {2200, (u64)longfmt};
    if (!setjmp(parked)) panic_screen_main("%.*s", longargs);
    assert(strlen((char *)panic_text) == PANIC_TEXT_BYTES - 1);
    assert(!strstr((char *)panic_text, "C="));
    puts("PASS formatter limits and winner/loser renderer (host shim)");
}
