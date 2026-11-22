#!/usr/bin/env python3
"""Source-contract checks for the post-handoff process census."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_r35_display_diag import generate

root = Path(__file__).resolve().parents[1]
src = generate((root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes(),
               mg_reset=True).decode()
body = src.split("static void bp_proc_census(void) {", 1)[1].split(
    "static void touch_monitor(", 1)[0]
assert "pid<=4096" in body and "proc_find(pid)" in body
assert "if (!p) continue;" in body and "proc_rele(p);" in body
assert "proc_name(pid,name,sizeof(name))" in body
assert all('strcmp(name,"' + name + '")' in body for name in
           ("SpringBoard", "backboardd", "lsd", "launchd", "lockdownd", "containermanager"))
assert "p->" not in body and "proc_list_lock" not in body
assert body.index("proc_rele(p);") < body.index("__atomic_store_n")
monitor = src.split("static void touch_monitor(", 1)[1].split("static void monitor(", 1)[0]
assert "now-census_at>=10" in monitor
assert monitor.index("bp_proc_census();") < monitor.index("touch_overlay();")
banner = src.split("static void crash_banner(", 1)[1].split(
    "static void touch_overlay_locked(", 1)[0]
assert "PROC n=%d SB=%s bb=%s lsd=%s ld=%s lk=%s cm=%s" in banner
assert "proc_list_lock" not in banner and "ALLPROC_FOREACH" not in banner
assert "__atomic_load_n(&bp_proc_pid[i],__ATOMIC_RELAXED)" in banner
assert len("PROC n=99999 SB=99999 bb=99999 lsd=99999 ld=99999 lk=99999 cm=99999") <= 80
assert len("containermanagerd") == 17
assert "containermanagerd"[:16] == "containermanager"
assert len("mobileactivationd") == 17
assert "mobileactivationd"[:16] == "mobileactivation"
for bit, name in enumerate(("runningboardd", "distnoted", "cfprefsd",
                             "notifyd", "securityd", "mobileactivation")):
    assert f'!strcmp(name,"{name}")) services|=1u<<{bit};' in body
assert '__atomic_store_n(&bp_svc_mask,services,__ATOMIC_RELAXED)' in body
assert '"SVC %02x",__atomic_load_n(&bp_svc_mask,__ATOMIC_RELAXED)' in banner
assert len("SVC 3f") == 6
assert "n+16+6<=cap" in banner and "unsigned room=cap-16-n;" in banner
for row in ("DSP ", "CLI ", "EX", "LOAD ", "UFS ", "SCHED ", "SC "):
    assert row in src
print("handoff process census source contract: self-checked")
