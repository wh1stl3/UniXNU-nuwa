#!/usr/bin/env python3
"""One host-reviewed continuation of the SID run; no device I/O by default."""
import argparse
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXECUTOR = REPO / 'scripts/run-pmap-ret-once.py'
EXECUTOR_SHA = 'e9b984eebb12065e1a1f209cdbfa071abe514b4496e1d7975bba6575b1f82c9d'
RUN_ID = 'ufs-sid-domain-20261114-01'
PROFILE = 'ufs-sid-domain-20261114-r1'
EVENT_SHA = (
    '04b1f00b0f04ddf3543b3a62f39337e7b7115aee71d576ef0f7a1ead0bb4705b',
    'aacd2f1c24b88d875b1cd50fb6d5dc105bfd9a081693aaa9708e05b5b24827e6',
    'da74fbaa75c489c51222e76d7a1faf97898b6cdd3076cad637ecf80155a2f56a',
    '9b650ad5d2873a8a6e42fd5a9db66b670ae44036eb51826f9372fa307853c255',
    '61ff554d14db04bc42041c613511cb98e149ae6878c8e31280d0c1cc2deabbeb',
)


def load_executor():
    import hashlib
    if EXECUTOR.is_symlink() or hashlib.sha256(EXECUTOR.read_bytes()).hexdigest() != EXECUTOR_SHA:
        raise RuntimeError('frozen executor hash mismatch')
    spec = importlib.util.spec_from_file_location('frozen_pmap_executor', EXECUTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def regular_json(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing or linked evidence: ' + path.name)
    return json.loads(path.read_text(encoding='utf-8'))


def host_gate(run, executor):
    executor.require(run.run_id == RUN_ID and run.profile == PROFILE, 'wrong run/profile')
    d = run.directory
    executor.require(not d.is_symlink() and not d.parent.is_symlink() and d.is_dir(),
                     'linked or missing run directory')
    run.require_identity()
    run.check_file(run.backup, run.size, run.stock_sha256)
    executor.require(regular_json(d / 'restore.claim') == {'phase': 'restore', 'authorized': True},
                     'original restore claim mismatch')
    executor.require(regular_json(d / 'boot-attempt.claim') == {'consumed_before_boot': True},
                     'boot claim mismatch')
    executor.require(regular_json(d / 'prepare-writer-closed.json') == {'dd_returncode': 0},
                     'prepare writer not closed')
    executor.require(regular_json(d / 'staging-created.json') == {'path': run.remote, 'owner': 2000},
                     'staging provenance mismatch')
    expected_states = executor.STATES[:6]
    states = sorted(p.name for p in d.glob('state-*.json'))
    executor.require(states == sorted('state-' + s + '.json' for s in expected_states),
                     'unexpected state set')
    previous = None
    for state in expected_states:
        executor.require(regular_json(d / ('state-' + state + '.json')) ==
                         {'state': state, 'previous': previous}, 'state history mismatch')
        previous = state
    for name in ('restore-writer.claim', 'restore-writer-closed.json', 'restore-complete.json',
                 'restore-readback.img', 'restore-attempt-02.claim'):
        executor.require(not (d / name).exists() and not (d / name).is_symlink(),
                         'restore already attempted or writer evidence exists')
    events = sorted(p.name for p in d.glob('event-*.json'))
    executor.require(events == ['event-%04d.json' % i for i in range(68)],
                     'event sequence changed; manual review required')
    for i, digest in enumerate(EVENT_SHA, 63):
        path = d / ('event-%04d.json' % i)
        executor.require(path.is_file() and not path.is_symlink() and executor.file_hash(path) == digest,
                         'original restore failure evidence mismatch')


def resume(run, executor, authorized=False):
    if not authorized:
        return {'dry_run': True, 'device_commands_executed': 0, 'run_id': RUN_ID}
    host_gate(run, executor)
    # Same cross-phase lock protocol as Run.execute; an abandoned lock remains a stop.
    run.create('active.lock', {'phase': 'restore-attempt-02'})
    try:
        host_gate(run, executor)
        run.create('restore-attempt-02.claim', {'phase': 'restore', 'authorized': True,
                                                 'original_claim_preserved': True})
        run.phase = 'restore'
        message = run.restore()
        run.create('restore-complete.json', {'state': run.state(), 'message': message})
        return {'self_checked': True, 'state': run.state(), 'message': message}
    finally:
        run.phase = None
        (run.directory / 'active.lock').unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-restore-attempt-02', action='store_true')
    parser.add_argument('--adb', default='D:/AndroidPhoneStuff/platform-tools/adb.exe')
    parser.add_argument('--fastboot', default='D:/AndroidPhoneStuff/platform-tools/fastboot.exe')
    args = parser.parse_args()
    if not args.authorize_restore_attempt_02:
        print(json.dumps({'dry_run': True, 'device_commands_executed': 0, 'run_id': RUN_ID}))
        return 0
    try:
        executor = load_executor()
    except (OSError, RuntimeError) as error:
        print('STOP: ' + str(error))
        return 1
    try:
        run = executor.Run(REPO, RUN_ID, args.adb, args.fastboot, profile=PROFILE)
        print(json.dumps(resume(run, executor, True)))
        return 0
    except (executor.Stop, OSError, ValueError, RuntimeError) as error:
        print('STOP: ' + str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
