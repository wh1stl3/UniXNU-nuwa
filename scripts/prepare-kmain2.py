"""Generate the bounded coarse-stage observer from the frozen KMAIN-1 source."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
old = (ROOT/'package/kernel-mainline/MetadataEntry.S').read_text()
save = old[old.index('    sub sp,sp,#256'):old.index('    mov w1,#1')]
restore = old[old.index('    ldr x9,[sp,#248]', old.index('resume:')):old.index('    sub sp,sp,#0xb0', old.index('resume:'))]
source = old.replace('    mov w1,#1\n', ''.join(
    f'    mov w0,#{row}\n    mov w1,#0xffffffff\n    bl draw\n'
    for row in range(8,12))+'    mov w1,#1\n', 1)
for index, (name, replay) in enumerate((
    ('root_wait', '    movz x30,#0x37ac\n    movk x30,#0x078e,lsl #16\n    movk x30,#0xfff0,lsl #32\n    movk x30,#0xffff,lsl #48\n    .jump root_wait_target\n'),
    ('root_return', '    cbnz w0,root_return_error\n    .jump root_return_zero\nroot_return_error:\n    .jump root_return_resume\n'),
    ('mount_return', '    cbnz w0,mount_return_error\n    .jump mount_return_zero\nmount_return_error:\n    .jump mount_return_resume\n'),
    ('init_entry', '    sub sp,sp,#0x130\n    .jump init_entry_resume\n'),
)):
    # A dedicated latch per serialized boot-stage site. No shared draw scratch
    # between these stages; all integer state and flags restored before replay.
    source += f'\n.global coarse_{name}\ncoarse_{name}:\n'+save
    source += f'    .addr x9,coarse_state\n    ldr w10,[x9,#{index*4}]\n    cbnz w10,coarse_{name}_done\n    mov w10,#1\n    str w10,[x9,#{index*4}]\n'
    source += '    mov w1,#1\n' if index in (0,3) else '    ldr w1,[sp,#0]\n'
    source += f'    mov w0,#{index+8}\n    bl draw\ncoarse_{name}_done:\n'+restore+replay
(ROOT/'package/kernel-mainline/CoarseStages.S').write_text(source, newline='\n')

builder = (ROOT/'scripts/build-ufs-iokit-mainline.py').read_text()
builder = builder.replace('MetadataEntry.S', 'CoarseStages.S').replace('KMAIN-1 r1', 'KMAIN-2 r1').replace('boot-kmain-1-r1.img', 'boot-kmain-2-r1.img').replace('iOS16 NativeUfs IOKit publication', 'iOS16 UFS kernel milestones')
builder = builder.replace('    targets = dict(linked_symbols)', '    coarse_state = end\n    end += 4096  # Dedicated zero-initialized RW/NX first-visit latches.\n    targets = dict(linked_symbols)')
builder = builder.replace('    code, local = compile_observer(work, targets)', '''    targets.update(coarse_state=coarse_state,
        root_wait_resume=0xfffffff0078e37ac, root_wait_target=0xfffffff0078652c8,
        root_return_zero=0xfffffff0076730cc, root_return_resume=0xfffffff00767309c,
        mount_return_zero=0xfffffff007673114, mount_return_resume=0xfffffff0076730ec,
        init_entry_resume=0xfffffff00769d2a8)
    assert targets['root_wait_target'] == macho['symbols']['__ZN9IOService14waitForServiceEP12OSDictionaryP13mach_timespec']
    code, local = compile_observer(work, targets)''')
builder = builder.replace('    offset = builder.backed(macho, trace.START, len(code))', '''    for address, before, name in (
        (0xfffffff0078e37a8, 'c806fe97', 'root_wait'),
        (0xfffffff007673098, 'a0010034', 'root_return'),
        (0xfffffff0076730e8, '76653914', 'mount_return'),
        (0xfffffff00769d2a4, '44f83814', 'init_entry')):
        replace(address, bytes.fromhex(before), builder.branch(address, local['coarse_'+name]),
                'first-visit coarse milestone: '+name)
    offset = builder.backed(macho, trace.START, len(code))''')
(ROOT/'scripts/build-ufs-kmain2.py').write_text(builder, newline='\n')
print('Generated CoarseStages.S and KMAIN-2 builder')
