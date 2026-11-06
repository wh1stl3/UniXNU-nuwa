"""Measured launch policy for the one-shot post-firmware UFS inspection."""
from nuwa_exec_detail_launch_context import API

API.__file__ = __file__
API.POLICY = dict(boot_arguments=API.ARGS, halt_site='0xfffffff0076729e0',
                  halt_before='bsd_init body; UFS read-only registers and CPU-side IOKit buffer, READ(10) descriptor preparation, cache clean and release; no device DMA',
                  restore_userspace_allowed=False)
if __name__ == '__main__':
    API.main()
