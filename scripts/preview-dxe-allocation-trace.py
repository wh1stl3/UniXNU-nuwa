"""Create a source-only diagnostic patch against pinned Mu; never build images."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MU = Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore')
PIN = 'cfb93724a06ff86ff5ba971413368a7809ee42a5'
PAGE = 'MdeModulePkg/Core/Dxe/Mem/Page.c'
MAIN = 'MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c'

HELPER = '''// Nuwa diagnostic only: no allocation, map conversion or resource promotion.
STATIC UINTN  mNuwaPoolFailureCount;

VOID
CoreNuwaDumpAllocationState (
  IN CONST CHAR8  *Stage
  )
{
  LIST_ENTRY  *Link;
  MEMORY_MAP  *Entry;
  UINT64      Pages;
  UINT64      FreePages = 0;
  UINT64      Largest = 0;
  UINT64      SpPages = 0;
  UINT64      TypePages[EfiMaxMemoryType] = {0};
  UINTN       Ranges = 0;

  // Caller holds gMemoryLock. Read the existing list; do not call GetMemoryMap.
  for (Link = gMemoryMap.ForwardLink; Link != &gMemoryMap; Link = Link->ForwardLink) {
    Entry = CR (Link, MEMORY_MAP, Link, MEMORY_MAP_SIGNATURE);
    if (Entry->End < Entry->Start) {
      DEBUG ((DEBUG_ERROR, "[NUWA-MEM] invalid descriptor start=%lx end=%lx\\n", Entry->Start, Entry->End));
      continue;
    }
    Pages = (Entry->End - Entry->Start + 1) >> EFI_PAGE_SHIFT;
    if (Entry->Type < EfiMaxMemoryType) {
      TypePages[Entry->Type] += Pages;
    }
    if (Entry->Type != EfiConventionalMemory) {
      continue;
    }
    if ((Entry->Attribute & EFI_MEMORY_SP) != 0) {
      SpPages += Pages;
      continue;
    }
    FreePages += Pages;
    if (Pages > Largest) {
      Largest = Pages;
    }
    if (Ranges < 8) {
      DEBUG ((DEBUG_ERROR, "[NUWA-MEM] free start=%lx end=%lx pages=%lu attr=%lx\\n", Entry->Start, Entry->End, Pages, Entry->Attribute));
    }
    Ranges++;
  }
  DEBUG ((DEBUG_ERROR, "[NUWA-MEM] %a failures=%lu free=%lu largest=%lu ranges=%lu special=%lu\\n", Stage, (UINT64)mNuwaPoolFailureCount, FreePages, Largest, (UINT64)Ranges, SpPages));
  for (UINTN Type = 0; Type < EfiMaxMemoryType; Type++) {
    if (TypePages[Type] != 0) {
      DEBUG ((DEBUG_ERROR, "[NUWA-MEM] type=%u pages=%lu\\n", (UINT32)Type, TypePages[Type]));
    }
  }
}

'''


def main():
    report_dir = ROOT/'reports/dxe-allocation-audit'
    report_dir.mkdir(parents=True, exist_ok=True)
    def git(*a):
        return subprocess.check_output(['git','--no-optional-locks','-C',str(MU),*a])
    if git('log','-1','--format=%H').decode().strip() != PIN:
        raise ValueError('Read-only Mu cache is not pinned submodule')
    old = {}
    original_endings = {}
    for path in (PAGE, MAIN):
        blob = git('show',PIN+':'+path)
        working = (MU/path).read_bytes()
        if blob.replace(b'\r\n',b'\n') != working.replace(b'\r\n',b'\n'):
            raise ValueError('Read-only cached input differs: '+path)
        old[path] = blob.decode().replace('\r\n','\n')
        original_endings[path] = '\r\n' if b'\r\n' in blob else '\n'
    # Keep diagnostic helper in Page.c, sharing the internal map without a new protocol.
    anchor = 'VOID *\nCoreAllocatePoolPages (\n'
    assert old[PAGE].count(anchor) == 1
    # Insert before the function documentation, keeping the original doc attached.
    pos = old[PAGE].rfind('/**',0,old[PAGE].index(anchor))
    revised = {PAGE:old[PAGE][:pos]+HELPER+'''// Keep private memory-lock functions within their existing Page.c context.
VOID
CoreNuwaDumpAllocationStateWithLock (
  IN CONST CHAR8  *Stage
  )
{
  CoreAcquireMemoryLock ();
  CoreNuwaDumpAllocationState (Stage);
  CoreReleaseMemoryLock ();
}

'''+old[PAGE][pos:]}
    failure = '  if (Start == 0) {\n    DEBUG ((DEBUG_ERROR | DEBUG_PAGE, "AllocatePoolPages: failed to allocate %d pages\\n", (UINT32)NumberOfPages));'
    replacement = '''  if (Start == 0) {
    mNuwaPoolFailureCount++;
    if (mNuwaPoolFailureCount == 1) {
      DEBUG ((DEBUG_ERROR, "[NUWA-MEM] request type=%u pages=%lu align=%lu guard=%u caller=%p\\n", (UINT32)PoolType, (UINT64)NumberOfPages, (UINT64)Alignment, (UINT32)NeedGuard, RETURN_ADDRESS (0)));
      if ((UINT32)PoolType < EfiMaxMemoryType) {
        DEBUG ((DEBUG_ERROR, "[NUWA-MEM] bin base=%lx max=%lx default-base=%lx default-max=%lx\\n", mMemoryTypeStatistics[PoolType].BaseAddress, mMemoryTypeStatistics[PoolType].MaximumAddress, mDefaultBaseAddress, mDefaultMaximumAddress));
      }
      CoreNuwaDumpAllocationState ("first-pool-failure");
    }
    DEBUG ((DEBUG_ERROR | DEBUG_PAGE, "AllocatePoolPages: failed to allocate %d pages\\n", (UINT32)NumberOfPages));'''
    assert revised[PAGE].count(failure)==1
    revised[PAGE] = revised[PAGE].replace(failure,replacement)
    include = '#include "DxeMain.h"\n'
    revised[MAIN] = old[MAIN].replace(include,include+'''
// Internal diagnostic wrapper acquires and releases the core memory lock.
VOID CoreNuwaDumpAllocationStateWithLock (IN CONST CHAR8 *Stage);
''',1)
    target = '  Status = CoreAllEfiServicesAvailable ();\n  if (EFI_ERROR (Status)) {'
    assert revised[MAIN].count(target)==1
    revised[MAIN] = revised[MAIN].replace(target,target+'''
    CoreNuwaDumpAllocationStateWithLock ("missing-arch-before-assert");
''',1)
    patch=''.join(''.join(difflib.unified_diff(old[p].replace('\n',original_endings[p]).splitlines(True),
                revised[p].replace('\n',original_endings[p]).splitlines(True),
                fromfile='a/Mu_Basecore/'+p,tofile='b/Mu_Basecore/'+p)) for p in (PAGE,MAIN))
    destination = ROOT/'patches/firmware-candidates/0008-nuwa-dxe-allocation-trace.patch'
    destination.write_bytes(patch.encode())
    # git apply --check does not modify the read-only reference tree.
    check = subprocess.run(['git','--no-optional-locks','-C',str(MU),
        'apply','--check','-p2',str(destination)],capture_output=True,text=True)
    check.check_returncode()
    if re.search(r'\b(?:AllocatePool|AllocatePages|GetMemoryMap|CoreConvertPages|PromoteMemoryResource)\s*\(',HELPER):
        raise ValueError('Diagnostic helper must not allocate or mutate memory map')
    result=dict(scope='Approved R-010 source revision after private-lock declaration error; no compilation/image/device command',
        mu_repository='microsoft/mu_basecore',mu_commit=PIN,license='BSD-2-Clause-Patent (source headers)',
        inputs=[dict(path=p,lf_sha256=hashlib.sha256(old[p].encode()).hexdigest(),
                     proposed_lf_sha256=hashlib.sha256(revised[p].encode()).hexdigest()) for p in old],
        patch=destination.relative_to(ROOT).as_posix(),patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),
        apply_check=dict(argv=check.args,exit_code=check.returncode,stdout=check.stdout,stderr=check.stderr),
        source_only_checks=['Pinned working cache matches git objects','git apply --check -p2 passes',
                            'No allocator/map-changing calls in helper','First failure and final pre-assert only',
                            'Original allocation result, resource promotion and assertion unchanged'],
        limitations=['No full Mu compile or device result','Largest raw free range before alignment/guard clipping; not guaranteed allocatable',
                     'Framebuffer-only output; timing/flush overhead and lock-held logging',
                     'Only first eight free ranges printed, aggregate includes all ranges',
                     'No successful-allocation history or early initialization map snapshot'],
        image_generated=False,firmware_checkout_modified=False,device_operated=False)
    (report_dir/'preview.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
