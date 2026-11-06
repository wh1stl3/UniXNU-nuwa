"""Measured launch policy for the one-shot post-firmware UFS inspection."""
from nuwa_exec_detail_launch_context import API

API.__file__ = __file__
API.POLICY = dict(boot_arguments=API.ARGS, halt_site='0xfffffff0076729e0',
                  halt_before='bsd_init body; legacy UFS bounded stop, owned transfer-list base readback, original base and RSR restoration; quarantine on uncertainty; no doorbell or SCSI submission',
                  restore_userspace_allowed=False)
if __name__ == '__main__':
    API.main()
