"""Provider contracts and configurable HTTP adapters.

No fake credentials are bundled. Admin config selects the provider and credentials.
"""
from __future__ import annotations
import os, json, urllib.request, urllib.error
from dataclasses import dataclass

@dataclass
class ProviderConfig:
    name:str
    base_url:str
    api_key:str=''
    timeout:float=15

class HTTPProvider:
    def __init__(self,cfg:ProviderConfig): self.cfg=cfg
    def request(self,path,payload,method='POST'):
        url=self.cfg.base_url.rstrip('/')+'/'+path.lstrip('/')
        data=json.dumps(payload).encode(); headers={'Content-Type':'application/json'}
        if self.cfg.api_key: headers['Authorization']='Bearer '+self.cfg.api_key
        req=urllib.request.Request(url,data=data,headers=headers,method=method)
        with urllib.request.urlopen(req,timeout=self.cfg.timeout) as r:
            raw=r.read().decode(); return json.loads(raw) if raw else {'status':r.status}

class PaymentProvider(HTTPProvider):
    def authorize(self,amount,currency,reference,metadata=None): return self.request('/payments/authorize',{'amount':str(amount),'currency':currency,'reference':reference,'metadata':metadata or {}})
    def capture(self,transaction_id,amount=None): return self.request('/payments/capture',{'transaction_id':transaction_id,'amount':str(amount) if amount is not None else None})
    def refund(self,transaction_id,amount=None): return self.request('/payments/refund',{'transaction_id':transaction_id,'amount':str(amount) if amount is not None else None})
    def settlement(self,date): return self.request('/settlements',{'date':date},'POST')

class WalletProvider(PaymentProvider): pass
class MessagingProvider(HTTPProvider):
    def send_sms(self,to,body,reference=None): return self.request('/messages/sms',{'to':to,'body':body,'reference':reference})
    def send_email(self,to,subject,body,reference=None): return self.request('/messages/email',{'to':to,'subject':subject,'body':body,'reference':reference})

class RoutingProvider(HTTPProvider):
    def route(self,origin,destination,waypoints=None): return self.request('/route',{'origin':origin,'destination':destination,'waypoints':waypoints or []})
    def geocode(self,address): return self.request('/geocode',{'address':address})
    def eta(self,origin,destination): return self.request('/eta',{'origin':origin,'destination':destination})

class ProviderRegistry:
    def __init__(self,settings=None): self.settings=settings or {}
    def payment(self): return PaymentProvider(ProviderConfig(**self.settings['payment'])) if self.settings.get('payment',{}).get('base_url') else None
    def wallet(self): return WalletProvider(ProviderConfig(**self.settings['wallet'])) if self.settings.get('wallet',{}).get('base_url') else None
    def messaging(self): return MessagingProvider(ProviderConfig(**self.settings['messaging'])) if self.settings.get('messaging',{}).get('base_url') else None
    def routing(self): return RoutingProvider(ProviderConfig(**self.settings['routing'])) if self.settings.get('routing',{}).get('base_url') else None
