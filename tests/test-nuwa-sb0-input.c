// SPDX-License-Identifier: BSD-2-Clause
#include <assert.h>
#include <stdio.h>
#include "../package/nuwa-sb0-input/Session.h"

static void repeat(struct InputSession *s, unsigned n, int level) {
  while (n--) InputSample(s, level);
}

int main(void) {
  struct InputSession s = {InitialRelease, 0};
  repeat(&s, 3, 0);
  assert(s.stage == FreshPress);
  repeat(&s, 2, 1);
  repeat(&s, 1, 0); // Bounce cannot complete a press.
  repeat(&s, 3, 1);
  assert(s.stage == FinalRelease);
  repeat(&s, 3, 0);
  assert(s.stage == Observed);
  repeat(&s, 5, 1);
  assert(s.stage == Observed); // Terminal; no second result.
  puts("PASS stable fresh release/press/release and bounce; terminal");

  s = (struct InputSession){InitialRelease, 0}; // New attempt after reboot.
  repeat(&s, 1500, 0);
  assert(s.stage == FreshPress);
  puts("PASS ordinary reboot and queued console/SDAM key without GPIO transition cannot pass");

  s = (struct InputSession){InitialRelease, 0};
  repeat(&s, 1, 1);
  repeat(&s, 3, 0);
  assert(s.stage == Refused);
  puts("PASS initially held fails closed even if later released");

  s = (struct InputSession){InitialRelease, 0};
  repeat(&s, 3, 0);
  repeat(&s, 1497, 1);
  assert(s.stage == FinalRelease);
  puts("PASS continuous hold never completes before timeout");

  s = (struct InputSession){InitialRelease, 0};
  repeat(&s, 3, 0);
  repeat(&s, 1, -1);
  repeat(&s, 3, 1);
  repeat(&s, 3, 0);
  assert(s.stage == Refused);
  puts("PASS invalid sample terminates and old progress cannot be reused");
}
