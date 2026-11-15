#!/usr/bin/env python3
"""Offline fresh-tree AMNM stage-one native link; output is NOT runnable."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True
BASE_REVISION = '693f5d9cae8a408dd18b39f3f9fdc4228c934241'


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def artifact(path):
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--cache-feeds', type=Path, required=True)
    parser.add_argument('--soc', type=Path, required=True)
    parser.add_argument('--kernelcache', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--offline-seed', type=Path, required=True,
                        help='existing nuwa tree; copy only pinned Linux source and header metadata caches')
    parser.add_argument('--bindings', type=Path, help='stage-one discovery JSON for second native link')
    parser.add_argument('--resume-offline-headers', type=Path,
                        help='existing nuwa tree: resume ONLY initial source-header failure before compilation')
    parser.add_argument('--resume-offline-libs', type=Path,
                        help='existing nuwa tree: stage pinned compiler-rt/Libc sources after bootstrap libs failure')
    options = parser.parse_args()
    base, out = options.base.resolve(), options.out.resolve()
    device = Path(__file__).resolve().parents[1]
    assert not any(c in str(out) for c in ' ,\t\n')
    assert git(base, 'rev-parse', 'HEAD') == BASE_REVISION
    assert git(options.soc, 'rev-parse', 'HEAD') == 'a9f45dc60c035084b95463781538380f4c3606c9'
    # This runner is only used inside a private network namespace.
    assert Path('/proc/self/ns/net').readlink() != Path('/proc/1/ns/net').readlink()
    resume = options.resume_offline_headers or options.resume_offline_libs
    assert not (options.resume_offline_headers and options.resume_offline_libs)
    if resume:
        assert out.is_dir()
    else:
        out.mkdir(parents=True, exist_ok=False)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    os.environ['GIT_ALLOW_PROTOCOL'] = 'file'
    if options.bindings:
        os.environ['AMNM_BINDINGS_JSON'] = str(options.bindings.resolve())
    os.environ['PATH'] = '/home/wh1stl3/.local/bin:/opt/unixnu-linux/bin:/opt/unixnu-linux/llvm/bin:' + os.environ['PATH']
    report = dict(status='self-checked', argv=sys.argv, cwd=str(Path.cwd()),
                  base_revision=BASE_REVISION, device_revision=git(device, 'rev-parse', 'HEAD'),
                  network_namespace=str(Path('/proc/self/ns/net').readlink()), stages={}, references=[])
    if resume:
        previous = json.loads((out / 'build-result.json').read_text())
        assert previous['stages']['kernel']['exit'] == 1
        assert (previous.get('previous_attempt', previous))['stages']['assemble']['exit'] == 0
        assert 'native' not in previous and 'prelink' not in previous['stages']
        saved = out / ('build-result-bootstrap-libs-failure.json' if options.resume_offline_libs
                       else 'build-result-first-header-failure.json')
        assert not saved.exists()
        saved.write_text(json.dumps(previous, indent=2) + '\n')
        report['previous_attempt'] = previous
    def save():
        (out / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n')
    def stage(name, function):
        entry = dict(started=datetime.now(timezone.utc).isoformat())
        report['stages'][name] = entry
        save()
        print('START ' + name, flush=True)
        try:
            result = function()
        except Exception as error:
            entry.update(exit=1, error=str(error), finished=datetime.now(timezone.utc).isoformat())
            save()
            raise
        entry.update(exit=0, finished=datetime.now(timezone.utc).isoformat())
        save()
        print('DONE ' + name, flush=True)
        return result
    try:
        sys.path.insert(0, str(base / 'scripts'))
        from unixnu import cli, config, feeds, tree, kernel, patches
        build_config = out / 'build-input.toml'
        build_config.write_text('[build]\n')
        common = ['-D', str(device), '--out', str(out), '--config', str(build_config),
                  '--local-module', f'soc:sm8550={options.soc.resolve()}',
                  '--kernelcache', str(options.kernelcache.resolve()), '-j', str(options.jobs)]
        args = cli.parser().parse_args(['defconfig', 'nuwa_amnm_defconfig', *common])
        ctx = config.Context(args)
        # Local Context only: do not edit the device board or any pin.
        ctx.board['kernel']['archives'] = [*ctx.board['kernel']['archives'], 'build-nuwa-amnm-observer.py']
        if not resume:
            stage('defconfig', lambda: cli.cmd_defconfig(ctx))
        effective = ctx.need_config()
        assert effective['XNU_BUILD_ARCHIVES'] is True
        assert effective['XNU_NUWA_AMNM_OBSERVER'] is True
        assert ctx.board['kernel']['archives'][-1] == 'build-nuwa-amnm-observer.py'
        report['config'] = artifact(ctx.config_path)
        report['board'] = artifact(device / 'board.toml')
        report['kernelcache'] = artifact(options.kernelcache.resolve())
        report['archive_plan'] = ctx.board['kernel']['archives']
        report['work'] = str(ctx.work)
        report['extra_link_flags'] = kernel.xnu_env(ctx)['XNU_EXTRA_LD_ARCHIVES']
        modules = feeds.resolve(ctx)
        def cache_references():
            for name in cli.REFERENCES['kernel']:
                module = modules[('refer', name)]
                assert module.origin == 'git', (name, module.origin)
                revision = feeds.pinned_revision(ctx, module, feeds.lock_read(ctx))
                target = feeds._clone_dir(ctx, module.source, revision)
                source = options.cache_feeds.resolve() / target.name
                assert source.is_dir(), f'existing offline source missing: {source}'
                assert git(source, 'rev-parse', 'HEAD') == revision, name
                assert not git(source, 'status', '--porcelain', '--untracked-files=no'), name
                assert not target.exists(), target
                print(f'offline copy {name}: {source} -> {target}', flush=True)
                shutil.copytree(source, target, symlinks=True)
                assert git(target, 'rev-parse', 'HEAD') == revision
                report['references'].append(dict(name=name, revision=revision, source=str(source), copy=str(target)))
            save()
        if not resume:
            stage('offline-cache-copy', cache_references)
        modules = feeds.resolve(ctx)
        for module in modules.values():
            if module.kind != 'refer' or module.name in cli.REFERENCES['kernel']:
                assert module.path is not None, f'uncached module: {module.kind}:{module.name}'
        if not resume:
            stage('assemble', lambda: tree.assemble(ctx, modules))
            def seed_caches():
                old = options.offline_seed.resolve()
                for name, revision in [('llvm-project', '58c46bae21181fb4240cf964461bea738d96d50e'),
                                       ('Libc', '899a3b2d52d95d75e05fb286a5e64975ec3de757')]:
                    source = old / '.cache/linux' / name
                    assert git(source, 'rev-parse', 'HEAD') == revision
                    assert not git(source, 'status', '--porcelain', '--untracked-files=no')
                    target = ctx.tree / '.cache/linux' / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source, target, symlinks=True)
                    report['references'].append(dict(name=name, revision=revision, source=str(source), copy=str(target)))
                for name in ('xnu-driverkit-10063.121.3.json', 'xnu-driverkit-crypto-10063.121.3.json',
                             'xnu-trustcache-8796.101.5.json', 'xnu-driverkit-8796.141.3.json',
                             'xnu-driverkit-crypto-8796.141.3.json'):
                    source = old / '.cache/sources' / name
                    target = ctx.tree / '.cache/sources' / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            stage('offline-cache-seed', seed_caches)
        native = ctx.tree / ctx.board['kernel']['prelink']['kernel']
        assert not native.exists(), 'first native must not already exist'
        assert not (ctx.tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/osfmk/DEVELOPMENT/startup.o.json').exists()
        if options.resume_offline_libs:
            def restore_offline_libs():
                cached = options.resume_offline_libs.resolve() / '.cache/linux'
                roots = [('llvm-project', '58c46bae21181fb4240cf964461bea738d96d50e'),
                         ('Libc', '899a3b2d52d95d75e05fb286a5e64975ec3de757')]
                for name, revision in roots:
                    source = cached / name
                    assert git(source, 'rev-parse', 'HEAD') == revision
                    assert not git(source, 'status', '--porcelain', '--untracked-files=no')
                    target = ctx.tree / '.cache/linux' / name
                    if target.exists():
                        target.rename(target.with_name(name + '-failed-fetch-preserved'))
                    shutil.copytree(source, target, symlinks=True)
                    assert git(target, 'rev-parse', 'HEAD') == revision
                    report['references'].append(dict(name=name, revision=revision, source=str(source), copy=str(target)))
            stage('resume-offline-linux-lib-sources', restore_offline_libs)
        if options.resume_offline_headers:
            def restore_offline_headers():
                # Recover only the failed source-preparation step. All patches
                # were already applied before its missing cache error. Do not
                # copy old objects, fakeroot, generated source edits or a kernel.
                old = options.resume_offline_headers.resolve()
                work = ctx.tree / '.cache/xnu-work'
                assert git(work, 'rev-parse', 'HEAD') == modules[('refer', 'xnu')].commit
                assert not (ctx.work / 'xnu-inputs.json').exists()
                selected = patches.plan(ctx, modules)
                signature = dict(source=str(modules[('refer', 'xnu')].path),
                                 commit=git(work, 'rev-parse', 'HEAD'),
                                 patches=[dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                                          for path in selected])
                # First failed invocation runs before version_env is supplied;
                # preserve its actual default tags, as prepare-xnu-source does.
                files = [('xnu-driverkit-10063.121.3.json', 'iokit/DriverKit'),
                         ('xnu-driverkit-crypto-10063.121.3.json', 'iokit/DriverKit/crypto'),
                         ('xnu-trustcache-8796.101.5.json', 'EXTERNAL_HEADERS/TrustCache'),
                         ('xnu-driverkit-8796.141.3.json', 'iokit/DriverKit'),
                         ('xnu-driverkit-crypto-8796.141.3.json', 'iokit/DriverKit/crypto')]
                copied = []
                for filename, directory in files:
                    cached = old / '.cache/sources' / filename
                    target_cache = ctx.tree / '.cache/sources' / filename
                    target_cache.parent.mkdir(parents=True, exist_ok=True)
                    target_cache.write_bytes(cached.read_bytes())
                    for entry in json.loads(cached.read_text()):
                        if entry['type'] != 'file' or not entry['name'].endswith('.h'):
                            continue
                        target = work / directory / entry['name']
                        if target.exists():
                            continue
                        source = old / '.cache/xnu-work' / directory / entry['name']
                        raw = source.read_bytes()
                        digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                        assert digest == entry['sha'], f'offline header blob mismatch: {source}'
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(raw)
                        copied.append(dict(path=str(target), source=str(source), git_blob=digest))
                subprocess.run(['python3', str(ctx.tree / 'scripts/prepare-xnu-source.py')],
                               cwd=ctx.tree, check=True)
                # Commit the exact normal preparer's stamp only after its
                # failed final command has now completed with verified cache.
                (ctx.work / 'xnu-inputs.json').write_text(json.dumps(signature, indent=2) + '\n')
                report['offline_restored_headers'] = copied
            stage('resume-offline-header-preparation', restore_offline_headers)
        # Same normal build/prelink functions as cli.cmd_build, without the
        # shared submodule updater or any feed fetch/checkout side effects.
        stage('kernel', lambda: kernel.build(ctx, modules))
        report['native'] = artifact(native)
        report['link_map'] = artifact(ctx.tree / 'build/nuwa-amnm-observer/native-link.map')
        save()
        report['warning'] = ('STAGE TWO REQUIRES FINAL-LAYOUT AUDIT' if options.bindings else 'STAGE ONE TRAP PLACEHOLDERS') + '; NOT DEVICE APPROVED'
        assert report['board'] == artifact(device / 'board.toml'), 'board changed during build'
        save()
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
