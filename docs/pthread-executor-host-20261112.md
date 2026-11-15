# Pthread executor profile — self-checked

Parent reports pthread+CHMH packaging ordinary review PASS and independent
verifier PASS, including fresh outer/FAT, 21 negatives, actual outer four-member
audit/zero padding, AST 2/2 and correct-base record check. Evidence
`out/pthread-chmh-verifier-20261112-r1/audit-r2/audit.json`. The audit key
`members_sha256.parent-adt` is the **derived** ADT SHA256
`4099834dedf4e3ee0b20bc9bbbedf7ad1402d1cdd70afe0ddf7c7adf1e40dfe8`; the
original parent `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4`
is separately bound in record inputs and digest material.

The explicit executor profile `pthread-chmh-20261112-r1` fixes the r4 package,
kernel/FAT/ADT, args, parent inputs, digest material, renderer/prelink
provenance, source, report, layout, loader and stock identities. It uses the
existing strict WSL/Windows repository record-path mapping. The existing four
profiles/default, exact device whitelist, one-shot and restore logic are
unchanged. Prepare and boot use the host gate before claims/device; restore uses
only run identity and that run's backup, without candidate or evidence.

Executor source SHA256
`324b007dd9146968651570d273f4bbfa779a826823bf01cd30f4adbe5c54c786`
(prior `d9a0c9fe5b488451849f4fbea44738847b91df0f9c36d4149466b74322c57bfd`).
Windows WorkBuddy Python and WSL Python 3.11 each executed **real** new-profile
`host_inputs` with subprocess trapped, exit 0, no device commands/run directory.
The single Windows unified self-check exited 0: 104 synthetic groups, including
new bad candidate/r4/kernel/FAT/ADT/source/evidence/path/material, cross-run/
profile and restore-without-assets. Evidence
`out/pthread-executor-selfcheck-20261112.json`, SHA256
`275813499782482950f518eb7a3ba697731d1d1d55b6db25685029b9a7fe4b8c`.
Fifteen actual Windows CLI calls (five profiles × three phases, no authorization)
all exited 0 with no device commands or run directories; evidence
`out/pthread-executor-dry15-20261112.json`, SHA256
`3f789c7a4381594fb8d35db65ff4035ad41930eed8bc2db28706a6c5f43a60cb`.

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`; actual host-input command,
exit 0 (WSL equivalent used `/home/wh1stl3/.local/bin/python3.11` from the same
repository and also exited 0):

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -B -c 'import importlib.util,pathlib; p=pathlib.Path("scripts/run-pmap-ret-once.py").resolve(); s=importlib.util.spec_from_file_location("executor",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.subprocess.run=lambda *a,**k: (_ for _ in ()).throw(AssertionError("process forbidden")); r=m.Run(m.REPO,"pthread-hostcheck-no-run","forbidden-adb","forbidden-fastboot",profile=m.PTHREAD_PROFILE); assert not r.directory.exists(); r.host_inputs(); assert not r.directory.exists(); print("windows actual pthread host_inputs OK; commands=0; run absent")'
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -B scripts/run-pmap-ret-once.py --self-check
```

The Windows self-check output was captured with PowerShell into the named JSON.
Actual WSL cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, exit 0:

```sh
/home/wh1stl3/.local/bin/python3.11 -B -c 'import importlib.util,pathlib; p=pathlib.Path("scripts/run-pmap-ret-once.py").resolve(); s=importlib.util.spec_from_file_location("executor",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.subprocess.run=lambda *a,**k: (_ for _ in ()).throw(AssertionError("process forbidden")); r=m.Run(m.REPO,"pthread-hostcheck-no-run","forbidden-adb","forbidden-fastboot",profile=m.PTHREAD_PROFILE); assert not r.directory.exists(); r.host_inputs(); assert not r.directory.exists(); print("WSL actual pthread host_inputs OK; commands=0; run absent")'
```

The 15-call matrix ran this Windows PowerShell command, exit 0:

```powershell
$code = @'
import json, pathlib, subprocess, sys
root = pathlib.Path.cwd()
profiles = ["pmap-ret-stop-20261111-r1", "pmap-ret-continue-20261111-r1", "amnm-observe-20261111-r1", "chmh-only-20261112-r1", "pthread-chmh-20261112-r1"]
results = []
for i, profile in enumerate(profiles):
    for phase in ("prepare", "boot", "restore"):
        runid = "pthread-drycheck-%d-%s" % (i, phase)
        path = root / "out" / ("pmap-ret-run-" + runid)
        assert not path.exists()
        argv = [sys.executable, "-B", "scripts/run-pmap-ret-once.py", "--profile", profile, "--phase", phase, "--run-id", runid, "--adb", "forbidden-adb", "--fastboot", "forbidden-fastboot"]
        p = subprocess.run(argv, cwd=root, capture_output=True, text=True)
        assert p.returncode == 0, (profile, phase, p.stderr, p.stdout)
        data = json.loads(p.stdout)
        assert data["dry_run"] is True and data["device_commands_executed"] == 0 and data["profile"] == profile and data["phase"] == phase and not path.exists()
        results.append({"profile":profile, "phase":phase, "exit":p.returncode, "device_commands":data["device_commands_executed"], "run_absent":not path.exists()})
report={"status":"self-checked", "cwd":str(root), "python":sys.executable, "groups":len(results), "runs":results}
(root / "out/pthread-executor-dry15-20261112.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":"self-checked","cli_dry_runs":len(results),"device_commands":0,"run_dirs_created":0}))
'@; & 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -B -c $code; exit $LASTEXITCODE
```

Verifier should rerun the host-input checks, one self-check and that 15-call
matrix independently, writing new evidence paths rather than overwriting these.
Windows in-memory syntax check and tracked `git diff --check` exited 0. For the
three relevant untracked files, `git diff --no-index --check /dev/null <file>`
returned 1 for differences with no diagnostics; a wrapper checked all three and
exited 0. WSL cwd `/mnt/d/Code/PortingiOS/UniXNU`, exit 0 / 14 areas:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/porting-record.py check --device /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --base origin/feat/step7-kernel-patches-8796
```

Future dry template: `scripts/run-pmap-ret-once.py --profile
pthread-chmh-20261112-r1 --phase <prepare|boot|restore> --run-id <RUN_ID>`.
Any future actual prepare, boot and restore each need new phase-specific user
authorization. Observe whether execution naturally gets beyond pthread; identify
the next panic. No output is inconclusive, not success. CHMH is experimental,
unauthenticated; runtime, UFS persistence and device behavior remain unproved.
No device access, real run/claim, packaging modification, commit or push occurred.
