import base64
import hashlib
import json
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from fastapi.testclient import TestClient

from cloud.app import create_app
from cloud.auth import OIDC, Settings
from cloud.storage import Denied, Store, encode_json


class Key:
    def __init__(self,key):
        self.key=key

class MockKeys:
    def __init__(self,key):
        self.key=key.public_key()

    def get_signing_key_from_jwt(self, token):
        return Key(self.key)


@pytest.fixture
def world(tmp_path):
    rsa=generate_private_key(public_exponent=65537,key_size=2048)
    settings=Settings("https://accounts.example.org/", "https://remote.example.org/mcp",
                      "https://accounts.example.org/.well-known/jwks.json", "https://remote.example.org")
    store=Store(tmp_path/"store.sqlite3",bytes(range(32)))
    oidc=OIDC(settings,key_provider=MockKeys(rsa))
    app=create_app(settings,store,oidc,
                   clock=time.time,challenge_token="verification-example-value")
    client=TestClient(app)

    def auth(user="alice", **overrides):
        claims={"iss":settings.issuer,"aud":settings.audience,"sub":user,
                "scope":"ur:read ur:control ur:shell ur:screen ur:devices",
                "iat":int(time.time()),"exp":int(time.time())+1800}
        claims.update(overrides)
        token=jwt.encode(claims,rsa,algorithm="RS256",headers={"kid":"test-public-key"})
        return {"Authorization":"Bearer "+token}

    def call(name,args=None,user="alice"):
        return client.post("/mcp",headers=auth(user),json={"jsonrpc":"2.0","id":"call-1",
                     "method":"tools/call","params":{"name":name,"arguments":args or {}}})

    def enroll(user="alice"):
        private=Ed25519PrivateKey.generate()
        pub=private.public_key().public_bytes(encoding=serialization.Encoding.Raw,
                                               format=serialization.PublicFormat.Raw)
        info=client.post("/v1/device/enrollment/begin",headers=auth(user)).json()
        principal=hashlib.sha256((settings.issuer+"\0"+user).encode()).hexdigest()
        msg=encode_json({"domain":"universal-remote-enroll/v1","owner":principal,
                 "id":info["id"],"challenge":info["challenge"],
                 "public_key":base64.b64encode(pub).decode()})
        body={"id":info["id"],"public_key":base64.b64encode(pub).decode(),
              "signature":base64.b64encode(private.sign(msg)).decode(),"label":"A user's PC"}
        response=client.post("/v1/device/enrollment/finish",headers=auth(user),json=body)
        assert response.status_code==200,response.text
        return response.json()["device_id"],private

    def signed(private, device, method, path, body=b"", nonce=None, timestamp=None):
        stamp=timestamp if timestamp is not None else int(time.time())
        nonce=nonce or str(uuid.uuid4())
        msg=encode_json({"domain":"universal-remote-agent/v1","device_id":device,
            "nonce":nonce,"timestamp":stamp,"method":method,"path":path,
            "sha256":hashlib.sha256(body).hexdigest()})
        return {"x-ur-nonce":nonce,"x-ur-timestamp":str(stamp),
                "x-ur-signature":base64.b64encode(private.sign(msg)).decode()}

    return locals()


def test_health_and_oauth_discovery(world):
    c=world['client']
    assert c.get('/healthz').status_code==200
    assert c.get('/.well-known/oauth-protected-resource').json()['authorization_servers']==[
        'https://accounts.example.org/']
    challenge=c.get('/.well-known/openai-apps-challenge')
    assert challenge.status_code==200 and challenge.text=='verification-example-value'


def test_requires_bearer_on_mcp(world):
    c=world['client']
    r=c.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
    assert r.status_code==401
    assert 'resource_metadata=' in r.headers['www-authenticate']


def test_wrong_audience_denied(world):
    c=world['client']; h=world['auth']('alice',aud='https://other.example.org')
    assert c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':1,'method':'tools/list'}).status_code==401


def test_expired_token_denied(world):
    c=world['client']; h=world['auth']('alice',exp=int(time.time())-3600,iat=int(time.time())-7200)
    assert c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':1,'method':'tools/list'}).status_code==401


def test_mcp_initialize_and_tools(world):
    c=world['client'];h=world['auth']()
    a=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
    assert a.status_code==200 and a.json()['result']['protocolVersion']=='2025-06-18'
    b=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':2,'method':'tools/list'})
    names={t['name'] for t in b.json()['result']['tools']}
    assert 'request_windows_powershell' in names and 'get_windows_operation' in names
    assert all('annotations' in t for t in b.json()['result']['tools'])


def test_enrollment_and_list(world):
    d,_=world['enroll'](); a=world['call']('list_windows_devices')
    assert a.json()['result']['structuredContent']['devices'][0]['device_id']==d


def test_cross_tenant_cannot_access(world):
    device,_=world['enroll']('alice')
    b=world['call']('get_windows_device',{'device_id':device},user='bob')
    assert b.json()['result']['isError'] is True
    b2=world['call']('list_windows_devices',user='bob')
    assert b2.json()['result']['structuredContent']['devices']==[]


def test_invalid_enrollment_signature_denied(world):
    c=world['client']; info=c.post('/v1/device/enrollment/begin',headers=world['auth']()).json()
    key=Ed25519PrivateKey.generate()
    pub=key.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
    b={'id':info['id'],'public_key':base64.b64encode(pub).decode(),
       'signature':base64.b64encode(bytes(64)).decode(),'label':'Test'}
    assert c.post('/v1/device/enrollment/finish',headers=world['auth'](),json=b).status_code==403


def test_replayed_enrollment_denied(world):
    c=world['client'];info=c.post('/v1/device/enrollment/begin',headers=world['auth']()).json()
    key=Ed25519PrivateKey.generate()
    pub=key.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
    owner=hashlib.sha256(('https://accounts.example.org/'+'\0'+'alice').encode()).hexdigest()
    msg=encode_json({'domain':'universal-remote-enroll/v1','owner':owner,'id':info['id'],
        'challenge':info['challenge'],'public_key':base64.b64encode(pub).decode()})
    b={'id':info['id'],'public_key':base64.b64encode(pub).decode(),
       'signature':base64.b64encode(key.sign(msg)).decode(),'label':'Test'}
    assert c.post('/v1/device/enrollment/finish',headers=world['auth'](),json=b).status_code==200
    assert c.post('/v1/device/enrollment/finish',headers=world['auth'](),json=b).status_code==403


def test_reject_invalid_diagnostic(world):
    device,_=world['enroll']()
    data=world['call']('request_windows_diagnostic',{'device_id':device,'diagnostic':'arbitrary_shell'})
    assert data.json()['result']['isError'] is True


def test_round_trip_signed_agent_queues_and_retrieves(world):
    c=world['client']; d,key=world['enroll']()
    result=world['call']('request_windows_diagnostic',{'device_id':d,'diagnostic':'computer'}).json()
    op=result['result']['structuredContent']['operation_id']
    path=f'/v1/agent/{d}/poll'
    polled=c.get(path,headers=world['signed'](key,d,'GET',path))
    assert polled.status_code==200
    job=polled.json()['job']
    assert job['operation_id']==op and job['tool']=='windows_diagnostic'
    assert job['arguments']=={'name':'computer'}
    path=f'/v1/agent/{d}/result'
    raw=encode_json({'operation_id':op,'ok':True,'output':{'cpu':'OK'}})
    completed=c.post(path,headers=world['signed'](key,d,'POST',path,raw),content=raw)
    assert completed.status_code==200
    status=world['call']('get_windows_operation',{'operation_id':op}).json()
    assert status['result']['structuredContent']['result']=={'cpu':'OK'}


def test_other_user_cannot_see_operation(world):
    device,_=world['enroll']()
    op=world['call']('request_windows_diagnostic',{'device_id':device,'diagnostic':'network'}).json()['result']['structuredContent']['operation_id']
    assert world['call']('get_windows_operation',{'operation_id':op},user='bob').json()['result']['isError'] is True


def test_duplicate_poll_returns_no_job(world):
    c=world['client'];d,key=world['enroll']()
    world['call']('request_windows_diagnostic',{'device_id':d,'diagnostic':'computer'})
    path=f'/v1/agent/{d}/poll'
    assert c.get(path,headers=world['signed'](key,d,'GET',path)).json()['job'] is not None
    assert c.get(path,headers=world['signed'](key,d,'GET',path)).json()['job'] is None


def test_same_nonce_replayed_denied(world):
    c=world['client'];d,key=world['enroll'](); path=f'/v1/agent/{d}/poll';h=world['signed'](key,d,'GET',path)
    assert c.get(path,headers=h).status_code==200
    assert c.get(path,headers=h).status_code==401


def test_unsigned_agent_denied(world):
    d,_=world['enroll']();c=world['client']
    assert c.get(f'/v1/agent/{d}/poll').status_code==401


def test_signature_cannot_be_used_for_other_device(world):
    c=world['client'];d1,key1=world['enroll']();d2,key2=world['enroll']()
    path=f'/v1/agent/{d2}/poll'
    assert c.get(path,headers=world['signed'](key1,d2,'GET',path)).status_code==401


def test_expired_device_signature_denied(world):
    c=world['client'];d,key=world['enroll']();path=f'/v1/agent/{d}/poll'
    assert c.get(path,headers=world['signed'](key,d,'GET',path,timestamp=int(time.time())-300)).status_code==401


def test_powershell_requires_explicit_confirmation(world):
    d,_=world['enroll']()
    ans=world['call']('request_windows_powershell',{'device_id':d,'command':'Get-Process','confirmation':'not-consented'})
    assert ans.json()['result']['isError'] is True
    good=world['call']('request_windows_powershell',{'device_id':d,'command':'Get-Process',
           'confirmation':'I understand this requires local Windows approval'})
    assert good.json()['result']['structuredContent']['status']=='queued'


def test_revoke_blocks_agent(world):
    c=world['client'];d,key=world['enroll']()
    v=world['call']('revoke_windows_device',{'device_id':d,'confirmation':'REVOKE DEVICE'})
    assert v.json()['result']['structuredContent']['revoked']
    path=f'/v1/agent/{d}/poll'
    assert c.get(path,headers=world['signed'](key,d,'GET',path)).status_code==401


def test_wrong_owner_cannot_revoke(world):
    d,_=world['enroll']()
    v=world['call']('revoke_windows_device',{'device_id':d,'confirmation':'REVOKE DEVICE'},user='bob')
    assert v.json()['result']['isError'] is True
    assert len(world['call']('list_windows_devices').json()['result']['structuredContent']['devices'])==1


def test_nonce_single_use_atomic(world):
    d,key=world['enroll']();now=int(time.time())
    world['store'].accept_nonce(d,str(uuid.uuid4()),now)
    nonce=str(uuid.uuid4())
    world['store'].accept_nonce(d,nonce,now)
    with pytest.raises(Denied):
        world['store'].accept_nonce(d,nonce,now)


def test_queue_limit(world):
    d,_=world['enroll']()
    for _ in range(25):
        assert world['call']('request_windows_diagnostic',{'device_id':d,'diagnostic':'network'}).json()['result']['isError'] is False
    assert world['call']('request_windows_diagnostic',{'device_id':d,'diagnostic':'network'}).json()['result']['isError'] is True


def test_domain_challenge_missing_404(world):
    c=TestClient(create_app(world['settings'],world['store'],world['oidc'], challenge_token=None))
    assert c.get('/.well-known/openai-apps-challenge').status_code==404


def test_mcp_unknown_method(world):
    c=world['client']; r=c.post('/mcp',headers=world['auth'](),json={'jsonrpc':'2.0','id':4,'method':'tools/drop_all'})
    assert r.json()['error']['code']==-32601


def test_read_only_token_cannot_request_shell(world):
    c=world['client'];d,_=world['enroll']()
    h=world['auth']('alice',scope='ur:read')
    r=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':7,'method':'tools/call',
             'params':{'name':'request_windows_powershell','arguments':{
             'device_id':d,'command':'Get-Process',
             'confirmation':'I understand this requires local Windows approval'}}})
    assert r.json()['result']['isError'] is True


def test_read_only_token_cannot_revoke(world):
    c=world['client'];d,_=world['enroll']()
    h=world['auth']('alice',scope='ur:read')
    r=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':8,'method':'tools/call',
             'params':{'name':'revoke_windows_device','arguments':{
             'device_id':d,'confirmation':'REVOKE DEVICE'}}})
    assert r.json()['result']['isError'] is True
    assert len(world['call']('list_windows_devices').json()['result']['structuredContent']['devices'])==1


def test_no_scope_cannot_list_devices(world):
    c=world['client'];h=world['auth']('alice',scope='')
    r=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':8,'method':'tools/call',
             'params':{'name':'list_windows_devices','arguments':{}}})
    assert r.json()['result']['isError'] is True


def test_no_devices_scope_cannot_enroll(world):
    c=world['client'];h=world['auth']('alice',scope='ur:read')
    r=c.post('/v1/device/enrollment/begin',headers=h)
    assert r.status_code==403


def test_native_device_client_enrollment_helpers(world):
    from cloud.device_client import Signer
    c=world['client'];signer=Signer.generate_for_local_enrollment()
    info=c.post('/v1/device/enrollment/begin',headers=world['auth']()).json()
    payload=signer.sign_enrollment(info)
    r=c.post('/v1/device/enrollment/finish',headers=world['auth'](),json={**payload,'label':'Other PC'})
    assert r.status_code==200
    assert len(world['call']('list_windows_devices').json()['result']['structuredContent']['devices'])==1


def test_native_agent_without_local_grant_denies_execution(world):
    from cloud.device_client import DeviceAgent, Signer
    c=world['client'];signer=Signer.generate_for_local_enrollment()
    info=c.post('/v1/device/enrollment/begin',headers=world['auth']()).json()
    d=c.post('/v1/device/enrollment/finish',headers=world['auth'](),json={
        **signer.sign_enrollment(info),'label':'Local PC'}).json()['device_id']
    op=world['call']('request_windows_powershell',{'device_id':d,'command':'Get-Process',
        'confirmation':'I understand this requires local Windows approval'}).json()['result']['structuredContent']['operation_id']

    class InProcess:
        def get(self,url,**kwargs):
            return c.get(url.replace('https://remote.example.org',''),**kwargs)
        def post(self,url,**kwargs):
            return c.post(url.replace('https://remote.example.org',''),**kwargs)

    invoked=[]
    agent=DeviceAgent('https://remote.example.org',d,signer,
        has_local_permission=lambda name:False,
        dispatch_local=lambda name,args:invoked.append((name,args)),http=InProcess())
    r=agent.poll_once()
    assert r['status']=='denied'
    assert invoked==[]
    status=world['call']('get_windows_operation',{'operation_id':op}).json()
    assert status['result']['structuredContent']['status']=='failed'


def test_native_agent_valid_local_grant_dispatch(world):
    from cloud.device_client import DeviceAgent, Signer
    c=world['client'];signer=Signer.generate_for_local_enrollment()
    info=c.post('/v1/device/enrollment/begin',headers=world['auth']()).json()
    d=c.post('/v1/device/enrollment/finish',headers=world['auth'](),json={
        **signer.sign_enrollment(info),'label':'Local PC'}).json()['device_id']
    op=world['call']('request_windows_diagnostic',{'device_id':d,'diagnostic':'computer'}).json()['result']['structuredContent']['operation_id']

    class InProcess:
        def get(self,url,**kwargs):
            return c.get(url.replace('https://remote.example.org',''),**kwargs)
        def post(self,url,**kwargs):
            return c.post(url.replace('https://remote.example.org',''),**kwargs)
    agent=DeviceAgent('https://remote.example.org',d,signer,
        has_local_permission=lambda name:name=='windows_diagnostic',
        dispatch_local=lambda name,args:{'diagnostic':args['name'],'state':'OK'},http=InProcess())
    assert agent.poll_once()['status']=='done'
    data=world['call']('get_windows_operation',{'operation_id':op}).json()['result']['structuredContent']
    assert data['status']=='done' and data['result']['diagnostic']=='computer'


def test_revoked_device_cannot_use_a_cached_signature_after_revocation(world):
    d,key=world['enroll']()
    headers=world['signed'](key,d,'GET',f'/v1/agent/{d}/poll')
    world['store'].revoke(hashlib.sha256((world['settings'].issuer+'\0alice').encode()).hexdigest(),d)
    assert world['client'].get(f'/v1/agent/{d}/poll',headers=headers).status_code==401


def test_native_dispatch_gates_privileged_tools():
    from cloud.native_dispatch import NativeDispatcher
    class Native:
        def agent_policy(self):
            return json.dumps({'requires_restart':False, 'effective_permissions':{
                'shell':False,'screen':False}})
        def windows_diagnostic(self,name):
            return json.dumps({'name':name,'ok':True})
        def run_powershell(self,*args):
            raise AssertionError('must never run shell')
    d=NativeDispatcher(native_server=Native())
    assert not d.has_local_permission('run_powershell')
    assert d.has_local_permission('windows_diagnostic')
    assert d.dispatch_local('windows_diagnostic',{'name':'computer'})=={'name':'computer','ok':True}
    from cloud.native_dispatch import NativeDenied
    with pytest.raises(NativeDenied):
        d.dispatch_local('run_powershell',{'command':'whoami','operation_id':str(uuid.uuid4())})


def test_native_dispatch_calls_existing_at_most_once_operation_id():
    from cloud.native_dispatch import NativeDispatcher
    operation=str(uuid.uuid4())
    class Native:
        def __init__(self):
            self.called=[]
        def agent_policy(self):
            return json.dumps({'requires_restart':False,'effective_permissions':{'shell':True}})
        def run_powershell(self,cmd,operation_id):
            self.called.append((cmd,operation_id))
            return json.dumps({'exit_code':0,'stdout':'ok'})
    native=Native();d=NativeDispatcher(native_server=native)
    assert d.dispatch_local('run_powershell',{'command':'Get-Date','operation_id':operation})['exit_code']==0
    assert native.called==[('Get-Date',operation)]


def test_native_dispatch_fail_closed_on_stale_policy():
    from cloud.native_dispatch import NativeDispatcher
    class Native:
        def agent_policy(self):
            return json.dumps({'requires_restart':True,'effective_permissions':{'shell':True}})
    d=NativeDispatcher(native_server=Native())
    assert not d.has_local_permission('run_powershell')
    assert not d.has_local_permission('windows_diagnostic')


def test_dpapi_helpers_are_unavailable_outside_windows():
    import sys
    from cloud.windows_identity import _dpapi, IdentityError
    if sys.platform!='win32':
        with pytest.raises(IdentityError):
            _dpapi(b'secret',encrypt=True)


def test_revoke_during_nonce_accept_fails_closed(world):
    d,key=world['enroll']()
    owner=hashlib.sha256((world['settings'].issuer+'\0alice').encode()).hexdigest()
    world['store'].revoke(owner,d)
    with pytest.raises(Denied):
        world['store'].accept_nonce(d,str(uuid.uuid4()),int(time.time()))


def test_revoked_device_cannot_retrieve_queued_job(world):
    d,key=world['enroll']()
    world['call']('request_windows_diagnostic',{'device_id':d,'diagnostic':'computer'})
    owner=hashlib.sha256((world['settings'].issuer+'\0alice').encode()).hexdigest()
    world['store'].revoke(owner,d)
    with pytest.raises(Denied):
        world['store'].poll(d)


def test_cors_untrusted_origin_rejected(world):
    c=world['client']
    h={**world['auth'](), 'origin':'https://attacker.example'}
    r=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
    assert r.status_code==403


def test_content_length_oversized_rejected(world):
    c=world['client']
    h={**world['auth'](),'content-length':'99999999'}
    r=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
    assert r.status_code==413


def test_enrollment_limit_throttled(world):
    c=world['client'];h=world['auth']()
    for _ in range(5):
        assert c.post('/v1/device/enrollment/begin',headers=h).status_code==200
    assert c.post('/v1/device/enrollment/begin',headers=h).status_code==429


def test_agent_result_duplicate_denied(world):
    c=world['client'];d,k=world['enroll']()
    op=world['call']('request_windows_diagnostic',{'device_id':d,'diagnostic':'computer'}).json()['result']['structuredContent']['operation_id']
    path=f'/v1/agent/{d}/poll';c.get(path,headers=world['signed'](k,d,'GET',path))
    path=f'/v1/agent/{d}/result'
    raw=encode_json({'operation_id':op,'ok':True,'output':{'ok':True}})
    assert c.post(path,headers=world['signed'](k,d,'POST',path,raw),content=raw).status_code==200
    assert c.post(path,headers=world['signed'](k,d,'POST',path,raw),content=raw).status_code==401


def test_agent_online_only_after_signed_request(world):
    c=world['client'];d,k=world['enroll']()
    assert world['call']('get_windows_device',{'device_id':d}).json()['result']['structuredContent']['online'] is False
    path=f'/v1/agent/{d}/poll'
    c.get(path,headers=world['signed'](k,d,'GET',path))
    assert world['call']('get_windows_device',{'device_id':d}).json()['result']['structuredContent']['online'] is True


def test_real_diagnostics_only_six(world):
    c=world['client']; h=world['auth']()
    data=c.post('/mcp',headers=h,json={'jsonrpc':'2.0','id':2,'method':'tools/list'}).json()
    schema=next(x['inputSchema'] for x in data['result']['tools'] if x['name']=='request_windows_diagnostic')
    assert set(schema['properties']['diagnostic']['enum'])=={'computer','cpu','gpu','network','memory_manager','volumes'}


def test_powershell_is_annotated_open_world_and_destructive(world):
    c=world['client']
    data=c.post('/mcp',headers=world['auth'](),json={'jsonrpc':'2.0','id':15,'method':'tools/list'}).json()
    t=next(v for v in data['result']['tools'] if v['name']=='request_windows_powershell')
    assert t['annotations']['openWorldHint'] is True
    assert t['annotations']['destructiveHint'] is True
