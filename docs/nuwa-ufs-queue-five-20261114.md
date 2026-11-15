# nuwa UFS queue-only host candidate

The five values are instantaneous observations only. DBR=0, RSR=0 and BA=0
cannot establish ownership or that the queue was never initialized.

Before a future NOP, establish exclusion of producer re-submission, account for
the task queue, establish the valid DMA domain and cache protocol, retain buffers
for their full device-visible lifetime, and isolate timeout/late-completion paths.
Neither “the kernel is the only CPU” nor repeated zero reads substitutes for
these conditions.

Host candidate only; independent review and verifier remain pending. No packaging
or device action. Register offsets and HCE bit 0 are consistent with the local
ShengUfs `RootQueue.h`; source reuse is ShengUfs@99d8bcd3, BSD-2-Clause
repository / BSD-2-Clause-Patent SPDX, and the existing nuwa r7 marker and builder.
The candidate does not dereference the sampled queue address.
