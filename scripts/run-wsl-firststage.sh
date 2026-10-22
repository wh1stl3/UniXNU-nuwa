#!/bin/sh
# Approved first-stage scope: own tests, text-only compiler probes and MIG C/header output.
# No installs, Git, kernel build, source view, firmware image or device command.
set -u
root=/mnt/d/Code/UniXNU-nuwa
python=/mnt/d/Code/PortingiOS/.venv-wsl/bin/python
report="$root/reports/wsl-firststage"
mkdir -p "$report"
cd "$root" || exit 1
date -Iseconds > "$report/run.log"
"$python" -B -m unittest discover -s tests -p test_wsl_kernel_adapter.py -v > "$report/tests.log" 2>&1
test_exit=$?
cat "$report/tests.log"
printf 'tests_exit=%s\n' "$test_exit" >> "$report/run.log"
if [ "$test_exit" -ne 0 ]; then exit "$test_exit"; fi
"$python" -B scripts/wsl_kernel_adapter.py plan > "$report/console.log" 2>&1
preflight_exit=$?
cat "$report/console.log"
printf 'preflight_exit=%s\n' "$preflight_exit" >> "$report/run.log"
case "$preflight_exit" in
    0|2) printf 'first-stage probe finished; full kernel execution remains disabled\n' ;;
    *) exit "$preflight_exit" ;;
esac
