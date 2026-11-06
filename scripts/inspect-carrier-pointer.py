"""Resolve fixed CHECK5 pointer slots against the actual linked symbol table."""
import argparse,struct,sys
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import Carrier,t
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e'
p=argparse.ArgumentParser();p.add_argument('slots',nargs='+');a=p.parse_args();c=Carrier(t.R/'out/ufs-check-5-r1-qualified')
for item in a.slots:
 if item.startswith('s:'):
  address=int(item[2:],0);off=c.b.backed(c.m,address,128);print(item,c.raw[off:off+128].split(b'\0')[0].decode());continue
 if item.startswith('_'):
  print(item,hex(c.sy[item]));continue
 slot=int(item,0)
 value=struct.unpack_from('<Q',c.raw,c.b.backed(c.m,slot,8))[0]
 print(hex(slot),hex(value),[k for k,v in c.sy.items() if v==value])
