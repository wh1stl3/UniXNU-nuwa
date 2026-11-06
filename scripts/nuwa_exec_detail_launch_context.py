"""Native exec observations with a boundary armed at the actual task switch."""
import hashlib,types
from pathlib import Path
_frozen=Path(__file__).with_name('nuwa_root_launch_context.py');_source=_frozen.read_bytes()
if hashlib.sha256(_source).hexdigest()!='36bcd82377a57ad97ca7ebe0ecc73b2cd5f21cb66cbb65633ce114a8165063ec':raise ValueError('Frozen root producer changed')
API=types.ModuleType('nuwa_exec_detail_launch_context._pinned');API.__file__=str(_frozen)
exec(compile(_source,str(_frozen),'exec'),API.__dict__)
API.__file__=__file__
API.POLICY=dict(boot_arguments=API.ARGS,halt_before='unreviewed restore task final wait release',halt_site='0xfffffff00769d230',condition='native exec task switch arms tracking; switch observed; matching task; clear_final_wait=2',restore_userspace_allowed=False)
if __name__=='__main__':API.main()
