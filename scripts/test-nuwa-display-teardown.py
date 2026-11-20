#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Deterministic 8796 teardown contract fixture, not a driver or IOKit scheduler."""
from contextlib import contextmanager
import unittest


class Busy(Exception):
    pass


class LockOrder(Exception):
    pass


class Gates:
    def __init__(self):
        self.held = {'display': [], 'provider': []}

    @contextmanager
    def enter(self, gate, actor):
        stack = self.held[gate]
        if stack and stack[-1] != actor:
            raise Busy(gate)
        stack.append(actor)
        try:
            yield
        finally:
            assert stack.pop() == actor

    def has(self, gate, actor):
        return actor in self.held[gate]

    @contextmanager
    def yield_display(self, actor):
        # Model a sender that releases the gate while still on its stack.
        stack = self.held['display']
        assert stack == [actor]
        stack.pop()
        try:
            yield
        finally:
            assert not stack
            stack.append(actor)


class Ledger:
    def __init__(self):
        self.refs = {'owner': set(), 'timer': set(), 'loop': set()}

    def take(self, resource, who):
        assert who not in self.refs[resource]
        self.refs[resource].add(who)

    def drop(self, resource, who):
        self.refs[resource].remove(who)  # Reject duplicate/foreign releases.


class Display:
    SOURCE = 'original timer'

    def __init__(self):
        self.gates = Gates()
        self.refs = Ledger()
        self.refs.take('owner', 'external')
        self.refs.take('loop', 'display')
        self.active = self.retiring = self.armed = False
        self.generation = self.wakes = self.entries = self.sends = 0
        self.pending = self.inflight = None
        self.clients = ['first', 'second']

    def start(self, fail_after_arm=False):
        with self.gates.enter('display', 'start'):
            self.refs.take('loop', 'saved')
            self.refs.take('timer', 'driver')
            self.refs.take('timer', 'event-chain')
            self.active = True
            self.kick('start')
            if fail_after_arm:
                assert self.stop('start')
                return False
            return True

    def kick(self, actor):
        with self.gates.enter('display', actor):
            if self.active and self.clients and not self.armed:
                self.armed = True
                self.generation += 1
                self.wakes += 1
                assert self.pending is None
                self.pending = self.generation
                for resource in ('loop', 'timer'):
                    self.refs.take(resource, 'pending')

    def dispatch(self):  # Callout dequeued, but has not entered the display gate.
        assert self.pending is not None and self.inflight is None
        self.inflight, self.pending = self.pending, None
        for resource in ('loop', 'timer'):
            self.refs.take(resource, 'inflight')
            self.refs.drop(resource, 'pending')

    def deliver(self, source=SOURCE, during_send=None):
        assert self.inflight is not None
        with self.gates.enter('display', 'tick'):
            if self.inflight == self.generation:  # Timer's generation check.
                self.tick(source, during_send)
        self.inflight = None  # Passive callout drops these after opening the gate.
        for resource in ('loop', 'timer'):
            self.refs.drop(resource, 'inflight')

    def tick(self, source, during_send):
        assert self.gates.has('display', 'tick')
        if source != self.SOURCE or not self.active:
            return
        assert self.refs.refs['owner']  # Timer/loop references do not retain owner.
        self.entries += 1
        self.armed = False
        # A candidate sender must revalidate before each send; this loop is not
        # evidence the donor's borrowed-node walk can support that contract.
        self.refs.take('owner', 'sender-lease')
        try:
            for client in tuple(self.clients):
                if not self.active or client not in self.clients:
                    break
                self.sends += 1
                if during_send is not None:
                    callback, during_send = during_send, None
                    callback()
            self.kick('tick')  # Recheck active and clients after a reentrant send.
        finally:
            self.refs.drop('owner', 'sender-lease')

    def remove_clients(self, actor):
        with self.gates.enter('display', actor):
            self.clients.clear()

    def stop(self, actor, fail_unlink=False):
        # Same-loop recursion is allowed. Cross-gate order is not established.
        if self.gates.has('provider', actor):
            raise LockOrder('provider -> display')
        with self.gates.enter('display', actor):
            if not (self.active or self.retiring):
                return True
            self.refs.take('loop', 'action')
            try:
                self.active = self.armed = False
                self.retiring = True
                assert 'saved' in self.refs.refs['loop']
                self.generation += 1
                if self.pending is not None:
                    self.pending = None
                    for resource in ('loop', 'timer'):
                        self.refs.drop(resource, 'pending')
                if fail_unlink:
                    return False  # Keep driver/chain/saved references for retry.
                self.refs.drop('timer', 'event-chain')
                self.refs.drop('timer', 'driver')
                self.refs.drop('loop', 'saved')
                self.retiring = False
                return True
            finally:
                self.refs.drop('loop', 'action')

    def free(self):
        assert not self.active and not self.retiring and not self.armed
        assert 'sender-lease' not in self.refs.refs['owner']
        self.refs.drop('owner', 'external')
        self.refs.drop('loop', 'display')


class TeardownTests(unittest.TestCase):
    def running(self):
        d = Display()
        self.assertTrue(d.start())
        return d

    def assert_drained(self, d):
        self.assertEqual(d.refs.refs, {'owner': set(), 'timer': set(), 'loop': set()})

    def test_queued_cancel_and_repeat_stop(self):
        d = self.running()
        self.assertTrue(d.stop('stop'))
        self.assertTrue(d.stop('stop'))
        d.kick('late kick')
        self.assertEqual((d.pending, d.entries, d.sends, d.wakes), (None, 0, 0, 1))
        d.free()
        self.assert_drained(d)

    def test_dequeued_waiter_can_outlive_owner_without_entering(self):
        d = self.running()
        d.dispatch()
        self.assertTrue(d.stop('stop'))
        d.free()
        self.assertEqual(d.refs.refs, {'owner': set(), 'timer': {'inflight'}, 'loop': {'inflight'}})
        d.deliver()
        self.assertEqual((d.entries, d.sends, d.wakes), (0, 0, 1))
        self.assert_drained(d)

    def test_stop_waits_for_inflight_send_then_cancels_its_rearm(self):
        d = self.running()
        d.dispatch()

        def stop_attempt():
            with self.assertRaisesRegex(Busy, 'display'):
                d.stop('stop')
            self.assertTrue(d.active)

        d.deliver(during_send=stop_attempt)
        self.assertEqual((d.entries, d.sends, d.wakes), (1, 2, 2))
        self.assertIsNotNone(d.pending)
        self.assertTrue(d.stop('stop'))
        d.kick('late kick')
        self.assertEqual((d.pending, d.entries, d.sends, d.wakes), (None, 1, 2, 2))
        d.free()
        self.assert_drained(d)

    def test_same_thread_reentry_stops_before_next_send_or_wake(self):
        d = self.running()
        d.dispatch()

        def nested_stop():
            self.assertTrue(d.stop('tick'))
            self.assertTrue(d.stop('tick'))
            self.assertEqual(d.refs.refs['timer'], {'inflight'})
            self.assertEqual(d.refs.refs['owner'], {'external', 'sender-lease'})
            with self.assertRaises(AssertionError):
                d.free()

        d.deliver(during_send=nested_stop)
        self.assertEqual((d.entries, d.sends, d.wakes), (1, 1, 1))
        d.free()
        self.assert_drained(d)

    def test_sender_yield_keeps_owner_live_but_does_not_restart(self):
        d = self.running()
        d.dispatch()

        def yield_then_stop():
            with d.gates.yield_display('tick'):
                self.assertTrue(d.stop('stop'))
                d.remove_clients('client')
                with self.assertRaises(AssertionError):
                    d.free()

        d.deliver(during_send=yield_then_stop)
        self.assertEqual((d.entries, d.sends, d.wakes), (1, 1, 1))
        d.free()
        self.assert_drained(d)

    def test_unlink_failure_quarantines_until_successful_retry(self):
        d = self.running()
        d.dispatch()
        self.assertFalse(d.stop('stop', fail_unlink=True))
        d.deliver()
        d.kick('late kick')
        self.assertEqual((d.entries, d.sends, d.wakes), (0, 0, 1))
        self.assertEqual(d.refs.refs, {'owner': {'external'}, 'timer': {'event-chain', 'driver'},
                                      'loop': {'display', 'saved'}})
        with self.assertRaises(AssertionError):
            d.free()
        self.assertTrue(d.stop('retry'))
        self.assertTrue(d.stop('retry'))
        d.free()
        self.assert_drained(d)

    def test_reverse_gate_order_is_rejected_before_timer_mutation(self):
        d = self.running()
        # Exhibit the ABBA wait edges without blocking a real thread.
        with d.gates.enter('display', 'tick'), d.gates.enter('provider', 'stop'):
            with self.assertRaisesRegex(Busy, 'provider'):
                with d.gates.enter('provider', 'tick'):
                    self.fail('provider should be held by stop')
            with self.assertRaisesRegex(Busy, 'display'):
                with d.gates.enter('display', 'stop'):
                    self.fail('display should be held by tick')
            with self.assertRaisesRegex(LockOrder, 'provider -> display'):
                d.stop('stop')
            self.assertTrue(d.active and d.armed)
            self.assertEqual((d.generation, d.wakes), (1, 1))
        self.assertTrue(d.stop('explicit caller without provider gate'))
        d.free()
        self.assert_drained(d)

    def test_last_client_removed_before_and_after_tick(self):
        for before in (True, False):
            with self.subTest(before=before):
                d = self.running()
                if before:
                    d.remove_clients('client')
                d.dispatch()
                d.deliver()
                if not before:
                    d.remove_clients('client')
                    d.dispatch()
                    d.deliver()
                self.assertEqual((d.sends, d.wakes), (0, 1) if before else (2, 2))
                self.assertFalse(d.armed)
                self.assertTrue(d.stop('stop'))
                d.free()
                self.assert_drained(d)

    def test_stale_source_cannot_mutate_armed_before_match(self):
        d = self.running()
        d.dispatch()
        d.deliver(source='foreign timer')
        self.assertEqual((d.armed, d.entries, d.sends, d.wakes), (True, 0, 0, 1))
        self.assertTrue(d.stop('stop'))
        d.free()
        self.assert_drained(d)

    def test_start_failure_uses_same_unwind_invariant(self):
        d = Display()
        self.assertFalse(d.start(fail_after_arm=True))
        self.assertEqual((d.pending, d.entries, d.sends, d.wakes), (None, 0, 0, 1))
        d.free()
        self.assert_drained(d)


if __name__ == '__main__':
    unittest.main(verbosity=2)
