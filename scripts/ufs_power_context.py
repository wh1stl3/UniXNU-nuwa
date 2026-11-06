"""Measured launch policy for the one-shot post-firmware UFS inspection."""
from nuwa_exec_detail_launch_context import API

API.__file__ = __file__
API.POLICY = dict(boot_arguments=API.ARGS, halt_site='0xfffffff0076729e0',
                  halt_before='bsd_init body; conditional single Device WLUN ACTIVE transition after READ ATTRIBUTE 0x02, power readback, bounded TUR settling; bounded slot-0 NOP, TUR, CAPACITY10, two LU0 READ10 LBA1, bounded primary GPT entries CRC; TUR reset-UA retry at most once; known CRC and repeat compare; restore firmware queue or quarantine; no media writes',
                  restore_userspace_allowed=False)
if __name__ == '__main__':
    API.main()
