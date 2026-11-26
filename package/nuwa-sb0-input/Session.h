// SPDX-License-Identifier: BSD-2-Clause
#pragma once

enum InputStage { InitialRelease, FreshPress, FinalRelease, Observed, Refused };
struct InputSession { enum InputStage stage; unsigned consecutive; };

// Each call represents one fresh real-time sample, never a queued key.
static inline void InputSample(struct InputSession *s, int level) {
  if (s->stage == Observed || s->stage == Refused) return;
  if (level < 0 || level > 1 || (s->stage == InitialRelease && level == 1)) {
    s->stage = Refused;
    return;
  }
  if (level != (s->stage == FreshPress)) {
    s->consecutive = 0;
    return;
  }
  if (++s->consecutive == 3) {
    s->consecutive = 0;
    s->stage = (enum InputStage)(s->stage + 1);
  }
}
