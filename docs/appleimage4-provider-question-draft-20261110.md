# Draft: supported AppleImage4 provider contract for a non-Apple boot chain

Local draft only — not sent or published. Please review before authorizing contact.

We are bringing up iOS 16.7.16 / XNU 8796 on a non-Apple boot chain. An
AppleImage4 initialization panic, `failed to get mix-n-match policy: 2`, was
traced to a missing chosen property. We explicitly selected
`mix-n-match-prevention-status=0` (AMNM=true) as a bring-up software policy,
not as a donor/fuse fact or a claim of Apple secure boot; AMFI remains enabled.

Our host-only intermediate is not approved for device boot: the selected
`sha2-384 arm ap` environment has secure-boot-level=0 and no BNCH property,
which would panic during initialization. The current bare-kernel loading path
has neither an authenticated manifest nor a nonce producer. We need provider
source or a supported compatible provider contract, rather than guessed inputs.

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

Please provide the relevant source, supported interface documentation, or a
compatible implementation and its security/test requirements. We will not
resume builds or device tests without a supported contract and appropriate review.
