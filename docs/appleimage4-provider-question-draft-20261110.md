# Draft: supported AppleImage4 provider contract for a non-Apple boot chain

Local question checklist only — retained English draft, not for external contact
or publication. Public material is read-only. The general publication task was
cancelled; no comment/issue was sent and no external write occurred.

We are bringing up iOS 16.7.16 / XNU 8796 on a non-Apple boot chain. An
AppleImage4 initialization panic, `failed to get mix-n-match policy: 2`, was
traced to a missing chosen property. We explicitly selected
`mix-n-match-prevention-status=0` (AMNM=true) as a bring-up software policy,
not as a donor/fuse fact or a claim of Apple secure boot; AMFI remains enabled.

Our host-only intermediate is not approved for device boot: the selected
`sha2-384 arm ap` environment has secure-boot-level=0 and no BNCH property,
which would panic during initialization. The current bare-kernel loading path
has neither an authenticated manifest nor a nonce producer. The earlier claim
that only AppleImage4 source or an external provider could unblock work is
historical and withdrawn by the completed user-requested Deep re-review.
A complete Apple production security chain is not an official bring-up stage 5
prerequisite. Research may define an explicit experimental software domain,
with bounded consumer closure and sufficient authentication negative-test
evidence; closed-source code is not necessarily required. No BNCH runtime
candidate is currently approved. Arbitrary values are not real hardware/donor
nonces, and passing initialization is not authentication success.

1. Does this provider version support operation without an AP token and without
   shadow state? If so, what exact entry points, interface versions and call
   ordering are required, including their timing relative to initialization?
2. Does that supported mode cover initialization's built-in BNCH handling,
   internal shadow state and built-in PMAP_CS, rather than only a separately
   registered runtime? What are the one-shot registration constraints?
3. How should unsupported configurations propagate safe errors? In particular,
   what is the defined behavior of nonce set/roll operations that provide no
   return value, and how must callers detect rejection without continuing with
   invalid state?
4. What authentication scope is supported when no token is available, and which
   signature/manifest negative tests are required to demonstrate rejection of
   unauthenticated, mismatched or otherwise invalid inputs?

Local next action: assess available source, supported interface documentation or
a compatible implementation against this list, and define the experimental
domain, bounded consumers and authentication negative tests before seeking release.
The independently reviewed/verifier-PASS offline fixtures now reach only
constructed-state initialization and malformed-manifest parse rejection, not
nonce/authentication. Establish a parseable manifest, matching apin payload and
real-state preconditions next; if absent, state that input/interface boundary.
Do not treat trst as an apin positive or the parse errno as a signature negative.
See image4-bnch-offline-20261110.md; no signed positive or device release exists.
PR187 only transports typed manifest properties; its NX769J / 20F66 report does
not disclose BNCH provenance or the exact test configuration and does not resolve
the nuwa / 20H392 provider gate (details in mix-n-match-host-20261110.md).
Without new contract evidence, do not repeat guessed BNCH or ineffective candidate
builds/device attempts. Independent local fixes, analysis and host validation may
continue under applicable review gates. AMNM-only remains self-checked and barred
from device release; future device tests require user confirmation.
