"""Use already extracted and hash-bound binaries; retain all launch policy keys."""
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('consumer_audit',R/'scripts/audit-core-service-consumers.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.parent=a.parent.resolve();assert not a.output.exists()
r=json.loads(a.parent.read_bytes());assert r['passed'] and r['mount_cleanup_complete']
edges=[];listeners=[];unknown=[]
for binary in r['binaries']:
 raw=(R/binary['extracted']).read_bytes();assert A.sha(raw)==binary['sha256'];binary.update(A.inspect(raw))
 for call in binary['constant_calls']:
  if call['api']!='_xpc_connection_create_mach_service':continue
  call['declared_providers']=r['providers'].get(call['literal'],[])
  item=dict(program=binary['path'],**call)
  (edges if call['endpoint_role']=='client' else listeners if call['endpoint_role']=='listener' else unknown).append(item)
fixed=[]
for item in r['jobs']:
 actual=item['actual_plist'];old=item['job']['declared']
 conditions={k:v for k,v in actual.items() if k in ('KeepAlive','Disabled','RunAtLoad','UserName','GroupName','POSIXSpawnType','ProcessType','EmbeddedHomeScreen','MinimalBootProfile') or 'LimitLoad' in k or k.startswith('_Panic')}
 omitted={k:v for k,v in conditions.items() if k not in old}
 item['complete_conditions']=conditions;item['previous_summary_omissions']=omitted;item['effective_enabled']='runtime conditions not resolved'
 if omitted:fixed.append(dict(label=item['job']['label'],omitted_keys=list(omitted)))
r.update(parent_report=dict(path=str(a.parent.relative_to(R)),sha256=A.sha(a.parent.read_bytes())),client_edges=edges,listener_endpoints=listeners,unknown_endpoint_roles=unknown,
 summary_omissions_corrected=fixed,script_sha256=A.sha(Path(__file__).read_bytes()),analyzer_sha256=A.sha(Path(A.__file__).read_bytes()),
 scope='Actual fixed standalone code and complete selected plist policy. IPC client/listener separated by constant flags; unknown flags remain unknown. Edges do not prove runtime need, readiness or startup ordering; framework implementations remain untraced.')
# Independent known-role checks prevent promoting listener declarations to clients.
assert any(x['literal']=='com.apple.logd_helper' for x in edges)
assert any(x['literal']=='com.apple.logd.admin' for x in listeners)
assert not any(x['literal']=='com.apple.logd.admin' for x in edges)
assert any(x['label']=='com.apple.SpringBoard' and 'LimitLoadFromHardware' in x['omitted_keys'] for x in fixed)
a.output.write_text(json.dumps(r,indent=2)+'\n')
print('PASS',len(edges),'client calls',len(listeners),'listeners',len(unknown),'unknown;',len(fixed),'job summaries corrected')
