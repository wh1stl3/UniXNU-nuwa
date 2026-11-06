"""Emit an analysis-only prelink of the current kernel using the qualified pool patch."""
import argparse
import json
from pathlib import Path
import struct
from native_prelink_inputs import ROOT,sha,inputs,tools,components

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--work',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);cli.add_argument('--profile',type=Path,default=ROOT/'config/native-prelink-merged-analysis-profile.json');args=cli.parse_args()
    work=args.work.resolve();output=args.output.resolve()
    if not work.is_relative_to(ROOT/'out') or work.exists() or not output.is_relative_to(ROOT/'reports') or output.exists():raise ValueError('Fresh analysis outputs required')
    profile,native,donor,selection=inputs(args.profile)
    qualification=json.loads((ROOT/'reports/native-prelink-current/libm-pool.json').read_text())
    if qualification['donor_sha256']!=sha(donor) or qualification['pool']!=profile['literal_pool'] or qualification['external_sites_resolved']!=12:raise ValueError('Pool qualification mismatched')
    roots=selection['components']+selection['codeless_components']
    with tools(True,args.profile) as (parser,emitter):
        plan=parser.plan(native,donor,roots,profile['slide'])
        image,full=emitter.emit(native,donor,roots,profile['slide'],{})
        parent,metadata,modules=components(parser,donor,selection)
        candidate=parser.macho(image)
        preserved=[]
        for name,module in modules.items():
            for segment in module['segments']:
                if segment['name']!='__TEXT_EXEC' or not segment['filesize']:continue
                size=segment['filesize'];before=parser.backed_offset(parent,segment['va'],size,len(donor));after=parser.backed_offset(candidate['segments'],segment['va']+profile['slide'],size,len(image))
                if donor[before:before+size]!=image[after:after+size]:raise ValueError('Component executable bytes changed')
                preserved.append(dict(module=name,bytes=size,sha256=sha(image[after:after+size])))
        native_macho=parser.macho(native)
        for segment in native_macho['segments']:
            if segment['name']=='__TEXT_EXEC' and segment['filesize']:
                a=segment['fileoff'];size=segment['filesize'];b=parser.backed_offset(candidate['segments'],segment['va'],size,len(image))
                if native[a:a+size]!=image[b:b+size]:raise ValueError('Native executable bytes changed')
        # Independently reread every emitted relocation against the immutable plan.
        for binding in plan['bindings']:
            at=parser.backed_offset(candidate['segments'],binding['new_site'],8,len(image))
            if struct.unpack_from('<Q',image,at)[0]!=binding['new_target']:raise ValueError('Emitted binding mismatch')
        work.mkdir(parents=True);(work/'kernel-prelinked-analysis.macho').write_bytes(image)
        (work/'full-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
        (work/'full-emission.json').write_text(json.dumps(full,indent=2)+'\n',encoding='utf-8')
        report=dict(scope='Analysis-only emitted current-native prelink; not a boot payload and not approved for hardware',
          sources=dict(repository=profile['source_repository'],commit=profile['source_commit'],license='BSD-2-Clause-Patent',tool_sha256=profile['source_sha256'],patch=profile['patch']),
          native_sha256=sha(native),donor_sha256=sha(donor),reference_selection_sha256=profile['reference_selection_sha256'],
          analytical_slide=profile['slide'],board_configuration_adopted=False,early_security_initializers={},
          plan=dict(component_count=len(plan['components']),codeless_count=len(plan['codeless_components']),extent_count=len(plan['extents']),pointer_counts=plan['pointer_counts'],bindings_rechecked=len(plan['bindings']),components=plan['components']),
          candidate=dict(path=(work/'kernel-prelinked-analysis.macho').relative_to(ROOT).as_posix(),bytes=len(image),sha256=sha(image),mapped_segments=len(candidate['segments']),virtual_span_bytes=max(s['va']+s['size'] for s in candidate['segments'] if s['size'])-min(s['va'] for s in candidate['segments'] if s['size'])),
          native_text_unchanged=True,component_text_preservation=preserved,
          full_report_hashes={name:sha((work/name).read_bytes()) for name in ('full-plan.json','full-emission.json')},
          runtime_qualified=False,loadable=False,device_accessed=False,
          blockers=['Early security initializer identity/call ABI not qualified or configured','Complete donor/native C++ and structure ABI not qualified','Real nuwa Apple ADT and runtime allocation window not supplied','Large-payload transport from firmware configuration probe remains separate'])
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(candidate=report['candidate'],plan=report['plan']['pointer_counts'],bindings_rechecked=report['plan']['bindings_rechecked'],component_text_ranges=len(preserved),loadable=False)))
if __name__=='__main__':main()
