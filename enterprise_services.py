"""Production service adapters. No provider is required for local operation.
Configure providers through environment variables or the Admin provider registry.
"""
from __future__ import annotations
import hashlib,hmac,json,os,secrets,time,urllib.request,zipfile,io
from pathlib import Path
from enterprise_completion_patch import connect,now

class Passwords:
    ITER=310000
    @classmethod
    def hash(cls,password):
        salt=secrets.token_bytes(16); dk=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,cls.ITER); return f'pbkdf2_sha256${cls.ITER}${salt.hex()}${dk.hex()}'
    @classmethod
    def verify(cls,password,encoded):
        try: alg,it,salt,digest=encoded.split('$'); got=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(it)).hex(); return hmac.compare_digest(got,digest)
        except Exception:return False

class RateLimiter:
    def __init__(self,max_attempts=8,window=300): self.max=max_attempts; self.window=window; self.data={}
    def allow(self,key):
        t=time.time(); arr=[x for x in self.data.get(key,[]) if t-x<self.window]; self.data[key]=arr; return len(arr)<self.max
    def fail(self,key): self.data.setdefault(key,[]).append(time.time())
    def clear(self,key): self.data.pop(key,None)

class Provider:
    def __init__(self,name,url='',token=''): self.name=name; self.url=url; self.token=token
    def request(self,path,payload,timeout=20):
        if not self.url: raise RuntimeError(f'{self.name} provider is not configured')
        data=json.dumps(payload).encode(); req=urllib.request.Request(self.url.rstrip('/')+'/'+path.lstrip('/'),data=data,headers={'Content-Type':'application/json','Authorization':f'Bearer {self.token}'} if self.token else {'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read() or '{}')

class MessagingProvider(Provider):
    def send_email(self,to,subject,html): return self.request('/email',{'to':to,'subject':subject,'html':html})
    def send_sms(self,to,text): return self.request('/sms',{'to':to,'text':text})

class PaymentProvider(Provider):
    def authorize(self,amount,currency,reference,metadata=None): return self.request('/payments/authorize',{'amount':str(amount),'currency':currency,'reference':reference,'metadata':metadata or {}})
    def capture(self,transaction_id,amount=None): return self.request('/payments/capture',{'transaction_id':transaction_id,'amount':str(amount) if amount is not None else None})
    def refund(self,transaction_id,amount=None): return self.request('/payments/refund',{'transaction_id':transaction_id,'amount':str(amount) if amount is not None else None})

class RoutingProvider(Provider):
    def route(self,origin,destination,waypoints=None): return self.request('/route',{'origin':origin,'destination':destination,'waypoints':waypoints or []})
    def geocode(self,address): return self.request('/geocode',{'address':address})

class Backup:
    @staticmethod
    def encrypted(db_path='pos.db',output='backups/pos.enc',password=None):
        password=password or os.getenv('POS_BACKUP_PASSWORD')
        if not password: raise RuntimeError('backup encryption password is required')
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        except ImportError: raise RuntimeError('install cryptography for encrypted backups')
        salt=secrets.token_bytes(16); kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=390000); key=Fernet.generate_key() if False else __import__('base64').urlsafe_b64encode(kdf.derive(password.encode())); f=Fernet(key)
        out=Path(output); out.parent.mkdir(parents=True,exist_ok=True); token=f.encrypt(Path(db_path).read_bytes()); out.write_bytes(b'DEEPSEEK1'+salt+token); return str(out)
    @staticmethod
    def decrypt(path,password,output):
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        raw=Path(path).read_bytes();
        if not raw.startswith(b'DEEPSEEK1'): raise ValueError('invalid backup format')
        salt=raw[9:25]; token=raw[25:]; kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=390000); key=__import__('base64').urlsafe_b64encode(kdf.derive(password.encode())); Path(output).write_bytes(Fernet(key).decrypt(token)); return output


def verify_restore(db_path):
    c=connect(db_path); row=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close(); return row=='ok'


def install(App):
    App.Passwords=Passwords; App.RateLimiter=RateLimiter; App.MessagingProvider=MessagingProvider; App.PaymentProvider=PaymentProvider; App.RoutingProvider=RoutingProvider; App.Backup=Backup; App.verify_restore=staticmethod(verify_restore)
