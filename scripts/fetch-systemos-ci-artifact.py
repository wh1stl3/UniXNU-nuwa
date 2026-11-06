"""Download a pinned CI artifact with digest/path checks; no device operation.
The local proxy stalls on large Azure blobs. Only the signed Azure transfer
bypasses that proxy; GitHub credentials are never forwarded to the blob host.
"""
import argparse,hashlib,json,subprocess,time,urllib.request,urllib.error,urllib.parse,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--commit',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
assert not a.output.exists();a.output.mkdir(parents=True)
token=subprocess.check_output(['gh','auth','token']).decode().strip()
direct=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def gh(path):
 req=urllib.request.Request('https://api.github.com/repos/wh1stl3/UniXNU-nuwa/'+path,headers={'Authorization':'Bearer '+token})
 return json.load(direct.open(req,timeout=20))
run=gh('actions/runs/'+str(a.run));assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==a.commit
summary={k:run[v] for k,v in [('status','status'),('conclusion','conclusion'),('headSha','head_sha'),('url','html_url')]}
(a.output/'run.json').write_text(json.dumps(summary,indent=2)+'\n')
artifacts=gh('actions/runs/'+str(a.run)+'/artifacts')['artifacts'];matches=[x for x in artifacts if x['name']=='nuwa-8796-merged-'+str(a.run)];assert len(matches)==1
meta=matches[0];assert meta['workflow_run']['head_sha']==a.commit and not meta['expired'];(a.output/'artifact.json').write_text(json.dumps(meta,indent=2)+'\n')
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
token=subprocess.check_output(['gh','auth','token']).decode().strip()
req=urllib.request.Request('https://api.github.com/repos/wh1stl3/UniXNU-nuwa/actions/artifacts/'+str(meta['id'])+'/zip',headers={'Authorization':'Bearer '+token})
try:urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(req,timeout=20);raise AssertionError('Expected artifact redirect')
except urllib.error.HTTPError as e:
 assert e.code==302,e.code;url=e.headers['Location']
parsed=urllib.parse.urlsplit(url);assert parsed.scheme=='https' and parsed.hostname.endswith('.blob.core.windows.net'),parsed.hostname
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));part=a.output/'artifact.zip.part';digest=hashlib.sha256();total=0;started=time.monotonic()
with opener.open(url,timeout=30) as response,part.open('wb') as target:
 while True:
  data=response.read(1024*1024)
  if not data:break
  target.write(data);digest.update(data);total+=len(data)
  if total%(16*1024*1024)==0:print('Downloaded MiB',total//(1024*1024),flush=True)
  assert time.monotonic()-started<600,'Artifact transfer total time limit'
assert total==meta['size_in_bytes'],(total,meta['size_in_bytes'])
assert meta['digest']=='sha256:'+digest.hexdigest()
archive=a.output/'artifact.zip';part.rename(archive)
with zipfile.ZipFile(archive) as z:
 for name in z.namelist():assert (a.output/name).resolve().is_relative_to(a.output.resolve()),'ZIP path escape'
 assert z.testzip() is None;z.extractall(a.output)
print('PASS artifact',a.run,digest.hexdigest(),flush=True)
