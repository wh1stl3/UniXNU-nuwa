#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Run the pinned donor sender's instructions against synthetic client queues.

These tests document a blocker, not a safe implementation.  The synchronous
send is mocked; nested client removal/free and stop are injected rather than
claimed to have happened on IOKit or hardware.
"""

import argparse
import importlib.util
from pathlib import Path
import struct
import unittest

import unicorn as uc
from unicorn import arm64_const as arm


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('display_abi', ROOT / 'scripts/derive-nuwa-display-abi.py')
ABI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ABI)

CODE = ABI.va('5c1b000')
ENTRY = ABI.va('5c1b838')
ZERO_CALL = ABI.va('5c1b8e8')
SEND_CALL = ABI.va('5c1b980')
NEXT_LOAD = ABI.va('5c1b9b4')
DISPLAY, FIRST, SECOND, STACK, RETURN = 0x100000, 0x200000, 0x202000, 0x400000, 0x500000
COUNT, TIMESTAMP, INTERVAL = 0x1122334455667788, 0x23456789abcdef01, 0x9876543212345678


def qword(value):
    return struct.pack('<Q', value)


class DonorSender:
    def __init__(self, image, *, head=FIRST, on_send=None):
        self.machine = uc.Uc(uc.UC_ARCH_ARM64, uc.UC_MODE_ARM)
        self.sent = []
        self.on_send = on_send
        self.stopped = False
        self.returned = False
        self.machine.mem_map(CODE, 4096)
        self.machine.mem_write(CODE, image.read(CODE, 4096))
        for address, size in ((DISPLAY, 8192), (FIRST, 4096), (SECOND, 4096),
                              (STACK, 8192), (RETURN, 4096)):
            self.machine.mem_map(address, size)
        self.machine.mem_write(DISPLAY + ABI.INSTANCE['vsync_clients'], qword(head))
        self.machine.mem_write(FIRST, qword(SECOND))
        self.machine.mem_write(SECOND, qword(0))
        for register, value in ((arm.UC_ARM64_REG_X0, DISPLAY),
                                (arm.UC_ARM64_REG_X1, COUNT),
                                (arm.UC_ARM64_REG_X2, TIMESTAMP),
                                (arm.UC_ARM64_REG_X3, INTERVAL),
                                (arm.UC_ARM64_REG_SP, STACK + 8192),
                                (arm.UC_ARM64_REG_LR, RETURN)):
            self.machine.reg_write(register, value)
        self.machine.hook_add(uc.UC_HOOK_CODE, self.hook)

    def hook(self, machine, pc, _size, _data):
        if pc == ZERO_CALL:
            # Freshly mapped stack is zero; skip the external memset call.
            machine.reg_write(arm.UC_ARM64_REG_PC, pc + 4)
        elif pc == SEND_CALL:
            address = machine.reg_read(arm.UC_ARM64_REG_X0)
            words = struct.unpack('<6Q', machine.mem_read(machine.reg_read(arm.UC_ARM64_REG_X2), 48))
            assert machine.reg_read(arm.UC_ARM64_REG_W3) == 6
            assert machine.reg_read(arm.UC_ARM64_REG_W4) == 1
            self.sent.append((address, words, self.stopped))
            if self.on_send:
                self.on_send(self)
            machine.reg_write(arm.UC_ARM64_REG_W0, 0)
            machine.reg_write(arm.UC_ARM64_REG_PC, pc + 4)
        elif pc == RETURN:
            self.returned = True
            machine.emu_stop()

    def run(self):
        self.machine.emu_start(ENTRY, 0, count=500)
        assert self.returned, 'sender did not return within the instruction limit'


class DonorVsyncTests(unittest.TestCase):
    image = None

    def test_six_message_scalars_from_three_64_bit_arguments(self):
        sender = DonorSender(self.image)
        sender.run()
        words = tuple(part for value in (COUNT, TIMESTAMP, INTERVAL)
                      for part in (value & 0xffffffff, value >> 32))
        self.assertEqual(sender.sent, [(FIRST + 0x18, words, False),
                                       (SECOND + 0x18, words, False)])

    def test_removal_before_entry(self):
        for head, expected in ((0, []), (SECOND, [SECOND + 0x18])):
            with self.subTest(head=head):
                sender = DonorSender(self.image, head=head)
                sender.run()
                self.assertEqual([entry[0] for entry in sender.sent], expected)

    def test_nested_removal_and_free_invalidates_borrowed_node(self):
        def remove_current(sender):
            if len(sender.sent) == 1:
                sender.machine.mem_write(DISPLAY + ABI.INSTANCE['vsync_clients'], qword(SECOND))
                sender.machine.mem_unmap(FIRST, 4096)

        sender = DonorSender(self.image, on_send=remove_current)
        with self.assertRaises(uc.UcError) as caught:
            sender.run()
        self.assertEqual(caught.exception.errno, uc.UC_ERR_READ_UNMAPPED)
        self.assertEqual(sender.machine.reg_read(arm.UC_ARM64_REG_PC), NEXT_LOAD)
        self.assertEqual(len(sender.sent), 1)

    def test_nested_stop_flag_is_not_rechecked_between_sends(self):
        def stop(sender):
            if len(sender.sent) == 1:
                sender.stopped = True

        sender = DonorSender(self.image, on_send=stop)
        sender.run()
        self.assertEqual([(entry[0], entry[2]) for entry in sender.sent],
                         [(FIRST + 0x18, False), (SECOND + 0x18, True)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT.parents[1] / 'UniXNU')
    parser.add_argument('--kernelcache', type=Path)
    args = parser.parse_args()
    kernelcache = args.kernelcache or args.base / 'out/ipsw/20H392/kernelcache.decompressed'
    DonorVsyncTests.image = ABI.Image(args.base, kernelcache)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DonorVsyncTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
