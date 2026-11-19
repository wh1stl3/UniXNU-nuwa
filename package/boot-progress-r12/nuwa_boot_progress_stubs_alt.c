// SPDX-License-Identifier: BSD-2-Clause-Patent
/*
 * r12: this file is the r11 stubs file (package/boot-progress/nuwa_boot_progress_stubs.c,
 * unchanged there) with two nuwa r12 differences:
 *
 *  * the four native_virtio_* counters are no longer defined here: the official
 *    VirtioMmioBlock component is linked in r12 and owns them (it also provides the
 *    native_verified_block_* lookup/authorization the SystemOS mount uses).  Keeping
 *    both definitions would be a duplicate symbol.
 *  * boot_process_capture() now samples the pid 1 status row (nuwa_pid1_sample), so the
 *    renderer's existing two-second process probe fills the new row without a new thread.
 *
 * nuwa only: definitions for the symbols package/boot-progress-r12/BootProgress.c
 * references that this kernel has no producer for.  The renderer is unmodified.
 * Its own model is "a weak import that resolves to nothing is 0", which a
 * -static Mach-O image cannot express (ld64 refuses undefined weak imports), so
 * the definitions here reproduce that value instead of faking a component:
 *
 *  * data symbols: absolute 0, so every "&symbol" test in the renderer is false
 *    and its absent-component branch is taken - no row of the screen claims a
 *    display/adreno/touch/ramblock/process/trace component that does not exist.
 *  * the four native_virtio_* counters and native_owner_root_accepted are read
 *    without an address test, so they are real zero variables (the renderer must
 *    never read address 0).
 *  * function symbols: real no-op functions (a call cannot target address 0);
 *    the renderer's monitor thread calls some of them once per second.
 *
 * Delete an entry here when the component that owns it lands in this image.
 *
 * Not defined here on purpose: native_ufs_block_reads / native_ufs_verified_blocks
 * / native_ufs_block_failures / native_ufs_integrity_failures /
 * native_ufs_blocks_published / native_ufs_progress_text() and the
 * native_ufs_root_* observers come from drivers/ShengUfs/NativeUfs.cpp with the
 * same types, so the renderer reads the live counters.
 */
#include <stdint.h>

/* native_owner_root_accepted is read without an address test (0 = absent).  The four
 * native_virtio_* counters are provided by the VirtioMmioBlock component in r12; the
 * r12a/r12b control builds have no component, so they define them here with
 * -DNUWA_VIRTIO_STUBS=1. */
volatile int native_owner_root_accepted;

/* r12: filled from the bsd object package/nuwa-systemos/nuwa_systemos.c.
 * r12b control: -DNUWA_PID1_STUB=1 provides a constant row instead, so the control
 * build carries no SystemOS code at all. */
#if defined(NUWA_PID1_STUB) && NUWA_PID1_STUB
char nuwa_pid1_row[120] = "PID1 row: r12b control build (no systemos code)";
void nuwa_pid1_sample(void) { }
#else
void nuwa_pid1_sample(void);
#endif

#if defined(NUWA_VIRTIO_STUBS) && NUWA_VIRTIO_STUBS
volatile uint32_t native_virtio_ready;
volatile uint32_t native_virtio_read_requests;
volatile uint32_t native_virtio_read_failures;
volatile uint64_t native_virtio_verified_blocks;
#endif

/* Absent components: absolute symbols at address 0. */
__asm__(
	"\t.globl _boot_process_attempts\n"
	"\t.set _boot_process_attempts, 0\n"
	"\t.globl _boot_process_busy\n"
	"\t.set _boot_process_busy, 0\n"
	"\t.globl _boot_process_passes\n"
	"\t.set _boot_process_passes, 0\n"
	"\t.globl _boot_process_rows\n"
	"\t.set _boot_process_rows, 0\n"
	"\t.globl _boot_process_seen\n"
	"\t.set _boot_process_seen, 0\n"
	"\t.globl _boot_progress_throw_text\n"
	"\t.set _boot_progress_throw_text, 0\n"
	"\t.globl _boot_ui_trace_index\n"
	"\t.set _boot_ui_trace_index, 0\n"
	"\t.globl _boot_ui_trace_label\n"
	"\t.set _boot_ui_trace_label, 0\n"
	"\t.globl _boot_ui_trace_phase\n"
	"\t.set _boot_ui_trace_phase, 0\n"
	"\t.globl _boot_ui_trace_ready\n"
	"\t.set _boot_ui_trace_ready, 0\n"
	"\t.globl _boot_ui_trace_rows\n"
	"\t.set _boot_ui_trace_rows, 0\n"
	"\t.globl _native_adreno_audit_attr\n"
	"\t.set _native_adreno_audit_attr, 0\n"
	"\t.globl _native_adreno_audit_ticks\n"
	"\t.set _native_adreno_audit_ticks, 0\n"
	"\t.globl _native_adreno_cache_stats\n"
	"\t.set _native_adreno_cache_stats, 0\n"
	"\t.globl _native_adreno_coherence\n"
	"\t.set _native_adreno_coherence, 0\n"
	"\t.globl _native_adreno_reassert_ticks\n"
	"\t.set _native_adreno_reassert_ticks, 0\n"
	"\t.globl _native_adreno_wc_audit\n"
	"\t.set _native_adreno_wc_audit, 0\n"
	"\t.globl _native_adreno_wc_distrusted\n"
	"\t.set _native_adreno_wc_distrusted, 0\n"
	"\t.globl _native_cpufreq_row\n"
	"\t.set _native_cpufreq_row, 0\n"
	"\t.globl _native_cpufreq_stage\n"
	"\t.set _native_cpufreq_stage, 0\n"
	"\t.globl _native_data_persist_errors\n"
	"\t.set _native_data_persist_errors, 0\n"
	"\t.globl _native_data_persist_first_lba\n"
	"\t.set _native_data_persist_first_lba, 0\n"
	"\t.globl _native_data_persist_gpt\n"
	"\t.set _native_data_persist_gpt, 0\n"
	"\t.globl _native_data_persist_gpt_after\n"
	"\t.set _native_data_persist_gpt_after, 0\n"
	"\t.globl _native_data_persist_header\n"
	"\t.set _native_data_persist_header, 0\n"
	"\t.globl _native_data_persist_loaded\n"
	"\t.set _native_data_persist_loaded, 0\n"
	"\t.globl _native_data_persist_present\n"
	"\t.set _native_data_persist_present, 0\n"
	"\t.globl _native_data_persist_state\n"
	"\t.set _native_data_persist_state, 0\n"
	"\t.globl _native_data_persist_syncs\n"
	"\t.set _native_data_persist_syncs, 0\n"
	"\t.globl _native_data_persist_writes\n"
	"\t.set _native_data_persist_writes, 0\n"
	"\t.globl _native_gop_gpu_abandoned\n"
	"\t.set _native_gop_gpu_abandoned, 0\n"
	"\t.globl _native_gop_gpu_completions\n"
	"\t.set _native_gop_gpu_completions, 0\n"
	"\t.globl _native_gop_gpu_failures\n"
	"\t.set _native_gop_gpu_failures, 0\n"
	"\t.globl _native_gop_gpu_offers\n"
	"\t.set _native_gop_gpu_offers, 0\n"
	"\t.globl _native_hid_input_events\n"
	"\t.set _native_hid_input_events, 0\n"
	"\t.globl _native_hid_input_results\n"
	"\t.set _native_hid_input_results, 0\n"
	"\t.globl _native_legacy_client_calls\n"
	"\t.set _native_legacy_client_calls, 0\n"
	"\t.globl _native_legacy_client_class\n"
	"\t.set _native_legacy_client_class, 0\n"
	"\t.globl _native_legacy_client_pid\n"
	"\t.set _native_legacy_client_pid, 0\n"
	"\t.globl _native_legacy_client_status\n"
	"\t.set _native_legacy_client_status, 0\n"
	"\t.globl _native_legacy_client_type\n"
	"\t.set _native_legacy_client_type, 0\n"
	"\t.globl _native_legacy_copy_bytes_last\n"
	"\t.set _native_legacy_copy_bytes_last, 0\n"
	"\t.globl _native_legacy_copy_bytes_sum\n"
	"\t.set _native_legacy_copy_bytes_sum, 0\n"
	"\t.globl _native_legacy_copy_last\n"
	"\t.set _native_legacy_copy_last, 0\n"
	"\t.globl _native_legacy_copy_max\n"
	"\t.set _native_legacy_copy_max, 0\n"
	"\t.globl _native_legacy_copy_n\n"
	"\t.set _native_legacy_copy_n, 0\n"
	"\t.globl _native_legacy_copy_sum\n"
	"\t.set _native_legacy_copy_sum, 0\n"
	"\t.globl _native_legacy_early_failures\n"
	"\t.set _native_legacy_early_failures, 0\n"
	"\t.globl _native_legacy_early_retires\n"
	"\t.set _native_legacy_early_retires, 0\n"
	"\t.globl _native_legacy_frame_color_counts\n"
	"\t.set _native_legacy_frame_color_counts, 0\n"
	"\t.globl _native_legacy_frame_color_other\n"
	"\t.set _native_legacy_frame_color_other, 0\n"
	"\t.globl _native_legacy_frame_colors\n"
	"\t.set _native_legacy_frame_colors, 0\n"
	"\t.globl _native_legacy_frame_count\n"
	"\t.set _native_legacy_frame_count, 0\n"
	"\t.globl _native_legacy_frame_kind\n"
	"\t.set _native_legacy_frame_kind, 0\n"
	"\t.globl _native_legacy_frame_stats\n"
	"\t.set _native_legacy_frame_stats, 0\n"
	"\t.globl _native_legacy_frame_time\n"
	"\t.set _native_legacy_frame_time, 0\n"
	"\t.globl _native_legacy_gop_bytes\n"
	"\t.set _native_legacy_gop_bytes, 0\n"
	"\t.globl _native_legacy_gop_physical\n"
	"\t.set _native_legacy_gop_physical, 0\n"
	"\t.globl _native_legacy_gop_virtual\n"
	"\t.set _native_legacy_gop_virtual, 0\n"
	"\t.globl _native_legacy_gpu_fallbacks\n"
	"\t.set _native_legacy_gpu_fallbacks, 0\n"
	"\t.globl _native_legacy_gpu_last_status\n"
	"\t.set _native_legacy_gpu_last_status, 0\n"
	"\t.globl _native_legacy_guard_slot\n"
	"\t.set _native_legacy_guard_slot, 0\n"
	"\t.globl _native_legacy_pm_callbacks\n"
	"\t.set _native_legacy_pm_callbacks, 0\n"
	"\t.globl _native_legacy_pm_calls\n"
	"\t.set _native_legacy_pm_calls, 0\n"
	"\t.globl _native_legacy_pm_stage\n"
	"\t.set _native_legacy_pm_stage, 0\n"
	"\t.globl _native_legacy_prepare_attempts\n"
	"\t.set _native_legacy_prepare_attempts, 0\n"
	"\t.globl _native_legacy_prepare_calls\n"
	"\t.set _native_legacy_prepare_calls, 0\n"
	"\t.globl _native_legacy_prepare_reason\n"
	"\t.set _native_legacy_prepare_reason, 0\n"
	"\t.globl _native_legacy_rej_class\n"
	"\t.set _native_legacy_rej_class, 0\n"
	"\t.globl _native_legacy_rej_reason\n"
	"\t.set _native_legacy_rej_reason, 0\n"
	"\t.globl _native_legacy_rej_size\n"
	"\t.set _native_legacy_rej_size, 0\n"
	"\t.globl _native_legacy_rej_state\n"
	"\t.set _native_legacy_rej_state, 0\n"
	"\t.globl _native_legacy_rej_surface\n"
	"\t.set _native_legacy_rej_surface, 0\n"
	"\t.globl _native_legacy_rej_surfaces\n"
	"\t.set _native_legacy_rej_surfaces, 0\n"
	"\t.globl _native_legacy_retirement_calls\n"
	"\t.set _native_legacy_retirement_calls, 0\n"
	"\t.globl _native_legacy_stage\n"
	"\t.set _native_legacy_stage, 0\n"
	"\t.globl _native_legacy_swap_accepted_count\n"
	"\t.set _native_legacy_swap_accepted_count, 0\n"
	"\t.globl _native_legacy_swap_rejected_count\n"
	"\t.set _native_legacy_swap_rejected_count, 0\n"
	"\t.globl _native_legacy_swap_validation_calls\n"
	"\t.set _native_legacy_swap_validation_calls, 0\n"
	"\t.globl _native_legacy_swap_validation_reason\n"
	"\t.set _native_legacy_swap_validation_reason, 0\n"
	"\t.globl _native_legacy_swap_validation_result\n"
	"\t.set _native_legacy_swap_validation_result, 0\n"
	"\t.globl _native_legacy_transfer_bytes\n"
	"\t.set _native_legacy_transfer_bytes, 0\n"
	"\t.globl _native_legacy_transfer_calls\n"
	"\t.set _native_legacy_transfer_calls, 0\n"
	"\t.globl _native_legacy_transfer_status\n"
	"\t.set _native_legacy_transfer_status, 0\n"
	"\t.globl _native_ram_block_bytes\n"
	"\t.set _native_ram_block_bytes, 0\n"
	"\t.globl _native_ram_block_resident_bytes\n"
	"\t.set _native_ram_block_resident_bytes, 0\n"
	"\t.globl _native_ram_block_sparse\n"
	"\t.set _native_ram_block_sparse, 0\n"
	"\t.globl _native_touch_count\n"
	"\t.set _native_touch_count, 0\n"
	"\t.globl _native_touch_rows\n"
	"\t.set _native_touch_rows, 0\n"
	"\t.globl _native_touch_seq\n"
	"\t.set _native_touch_seq, 0\n"
	"\t.globl _native_touch_stage_req\n"
	"\t.set _native_touch_stage_req, 0\n"
	"\t.globl _native_touch_xs\n"
	"\t.set _native_touch_xs, 0\n"
	"\t.globl _native_touch_ys\n"
	"\t.set _native_touch_ys, 0\n"
	"\t.globl _native_wi_count\n"
	"\t.set _native_wi_count, 0\n"
	"\t.globl _native_wi_log\n"
	"\t.set _native_wi_log, 0\n"
);

/* Function stubs. */
uint64_t
boot_diag_scan(uint64_t cookie)
{
	(void) cookie;
	return 0;
}

int
boot_diag_stream(int (*sink)(const void *, uint32_t, void *), void *context)
{
	(void) sink;
	(void) context;
	return -1;
}

void
boot_log_tick(unsigned now)
{
	(void) now;
}

void
boot_process_capture(void)
{
	/* r12: the renderer calls this every two seconds from process_monitor(); it now also
	 * refreshes the pid 1 / SystemOS status row. */
	nuwa_pid1_sample();
}

void
boot_process_snapshot(void)
{
}

void
boot_progress_exit_fault(int pid, unsigned signal, char *row, unsigned long cap)
{
	(void) pid;
	(void) signal;
	(void) row;
	(void) cap;
}

void
boot_progress_exit_reason(int pid, unsigned signal, char *row, unsigned long cap)
{
	(void) pid;
	(void) signal;
	(void) row;
	(void) cap;
}

unsigned
boot_ui_trace_role_rows(unsigned role, char rows[][120], unsigned limit, unsigned extra)
{
	(void) role;
	(void) rows;
	(void) limit;
	(void) extra;
	return 0;
}

void
boot_ui_trace_snapshot(unsigned now)
{
	(void) now;
}

void
sheng_cpufreq_poll(void)
{
}
