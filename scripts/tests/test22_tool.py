#!/usr/bin/env python3
"""Canonical read-only Test 22 diagnostics and evidence recovery.

No subcommand mutates Wi-Fi, sends AssistServer commands, clears app data,
installs APKs, uses adb forward/reverse, or retries the historical effect.
Compatible with Python 3 standard library only.
"""
from __future__ import print_function
import argparse, json, os, re, shutil, subprocess, sys, time

MAC_RE = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
SSID_DQ_RE = re.compile(r'SSID="[^"]*"', re.I)
SSID_FIELD_RE = re.compile(r'(?i)\bssid:\s*[^\s,]+')
SERIAL_LINE_RE = re.compile(r'(?i)\b(serial|device_serial|phone_serial)=\S+')


def redact(s):
    s = MAC_RE.sub('<MAC_REDACTED>', s)
    s = IPV4_RE.sub('<IP_REDACTED>', s)
    s = SSID_DQ_RE.sub('SSID="<REDACTED>"', s)
    s = SSID_FIELD_RE.sub('ssid: <REDACTED>', s)
    s = SERIAL_LINE_RE.sub(lambda m: m.group(1) + '=<REDACTED>', s)
    return s


def run(args, timeout=15):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(timeout=timeout) if hasattr(p, 'communicate') else (b'', b'')
    if not isinstance(out, str): out = out.decode('utf-8', 'replace')
    if not isinstance(err, str): err = err.decode('utf-8', 'replace')
    return p.returncode, out.replace('\r',''), err.replace('\r','')


def resolve_adb(explicit=None):
    candidates = []
    if explicit: candidates.append(explicit)
    env = os.environ.get('ADB')
    if env: candidates.append(env)
    home = os.path.expanduser('~')
    candidates += [os.path.join(home,'Library/Android/sdk/platform-tools/adb'), shutil.which('adb')]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK): return c
    raise RuntimeError('adb_not_found')


def adb_devices(adb):
    rc,out,err = run([adb,'devices'])
    if rc != 0: raise RuntimeError('adb_devices_failed')
    rows=[]
    for line in out.splitlines()[1:]:
        p=line.split()
        if len(p)>=2 and p[1]=='device': rows.append(p[0])
    return rows


def adb_shell(adb, serial, *cmd):
    rc,out,err = run([adb,'-s',serial,'shell']+list(cmd))
    return rc,out.strip(),err.strip()


def select_glasses(adb, serial=None):
    devs=adb_devices(adb)
    if serial:
        if serial not in devs: raise RuntimeError('requested_serial_not_connected')
        return serial, len(devs)
    matches=[]
    for s in devs:
        rc,out,_=adb_shell(adb,s,'getprop','ro.product.device')
        if rc==0 and out.strip()=='glasses': matches.append(s)
    if len(matches)==1: return matches[0], len(devs)
    if len(devs)==1: return devs[0],1
    raise RuntimeError('glasses_not_uniquely_identified')


def snapshot(adb, serial):
    _,wifi,_=adb_shell(adb,serial,'settings','get','global','wifi_on')
    _,addr,_=adb_shell(adb,serial,'ip','-o','-4','addr','show','dev','wlan0')
    _,route,_=adb_shell(adb,serial,'ip','-4','route')
    default_wlan=False
    any_wlan=False
    for line in route.splitlines():
        if ' dev wlan0' in (' '+line): any_wlan=True
        if line.startswith('default ') and 'wlan0' in line: default_wlan=True
    return {'wifi_on':wifi or 'UNKNOWN','wlan0_ipv4':bool(addr.strip()),'wlan0_route':any_wlan,'default_route_wlan0':default_wlan}


def emit_snapshot(prefix,s):
    print(prefix+'WIFI_ON='+str(s['wifi_on']))
    print(prefix+'WLAN0_IPV4='+('YES' if s['wlan0_ipv4'] else 'NO'))
    print(prefix+'WLAN0_ROUTE='+('YES' if s['wlan0_route'] else 'NO'))
    print(prefix+'DEFAULT_ROUTE_WLAN0='+('YES' if s['default_route_wlan0'] else 'NO'))


def cmd_device_status(a):
    try:
        adb=resolve_adb(a.adb); serial,count=select_glasses(adb,a.serial); s=snapshot(adb,serial)
        print('TEST22_DEVICE_STATUS=PASS'); print('ADB_DEVICE_COUNT='+str(count)); emit_snapshot('',s)
        print('DEVICE_OPERATION=READ_ONLY'); print('WIFI_MUTATION=NONE'); return 0
    except Exception as e:
        print('TEST22_DEVICE_STATUS=HOLD'); print('ERROR='+str(e)); return 3


def cmd_monitor(a):
    try:
        adb=resolve_adb(a.adb); serial,count=select_glasses(adb,a.serial)
        print('TEST22_MONITOR=STARTED'); print('ADB_DEVICE_COUNT='+str(count)); start=time.time(); i=0
        while True:
            i+=1; s=snapshot(adb,serial)
            print('SAMPLE=%d WIFI_ON=%s WLAN0_IPV4=%s WLAN0_ROUTE=%s' % (i,s['wifi_on'],'YES' if s['wlan0_ipv4'] else 'NO','YES' if s['wlan0_route'] else 'NO'))
            sys.stdout.flush()
            if s['wifi_on']=='1' and s['wlan0_ipv4'] and s['wlan0_route']:
                print('GLASSES_WIFI_SESSION_OBSERVED=YES'); return 0
            if a.timeout and time.time()-start >= a.timeout:
                print('GLASSES_WIFI_SESSION_OBSERVED=NO'); print('MONITOR_DECISION=HOLD_NO_WIFI_SESSION_WITHIN_WINDOW'); return 3
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print('MONITOR_DECISION=STOPPED_BY_OPERATOR'); return 130
    except Exception as e:
        print('MONITOR_DECISION=HOLD'); print('ERROR='+str(e)); return 3


def cmd_isolation(a):
    try:
        adb=resolve_adb(a.adb); serial,count=select_glasses(adb,a.serial); samples=[]
        print('TEST22_PHONE_OFF_ISOLATION=YES'); print('ADB_DEVICE_COUNT='+str(count))
        for i in range(a.samples):
            s=snapshot(adb,serial); samples.append(s)
            print('SAMPLE=%d WIFI_ON=%s WLAN0_IPV4=%s DEFAULT_ROUTE_WLAN0=%s' % (i+1,s['wifi_on'],'YES' if s['wlan0_ipv4'] else 'NO','YES' if s['default_route_wlan0'] else 'NO'))
            if i+1<a.samples: time.sleep(a.interval)
        down=all(x['wifi_on']=='0' and not x['wlan0_ipv4'] and not x['default_route_wlan0'] for x in samples)
        up=all(x['wifi_on']=='1' and x['wlan0_ipv4'] and x['default_route_wlan0'] for x in samples)
        if down: decision='PHONE_SESSION_REMOVAL_TORE_DOWN_WIFI'
        elif up: decision='INDEPENDENT_WIFI_PERSISTED_AFTER_PHONE_REMOVAL'
        else: decision='MIXED_OR_TRANSITIONAL_WIFI_STATE'
        print('TEST22_ISOLATION_DECISION='+decision); print('DEVICE_OPERATION=READ_ONLY'); print('WIFI_MUTATION=NONE'); return 0
    except Exception as e:
        print('TEST22_PHONE_OFF_ISOLATION=HOLD'); print('ERROR='+str(e)); return 3


def find_one(root,name):
    hits=[]
    for dp,_,fns in os.walk(root):
        if name in fns: hits.append(os.path.join(dp,name))
    return sorted(hits)


def loadj(path):
    with open(path,'r') as f: return json.load(f)


def cmd_receipts(a):
    arms=find_one(a.root,'arm.json'); runs=find_one(a.root,'run.json')
    print('TEST22_RECEIPT_RECOVERY=YES'); print('ARM_RECEIPT_COUNT='+str(len(arms))); print('RUN_RECEIPT_COUNT='+str(len(runs)))
    for p in arms:
        d=loadj(p); print('ARM_OK='+str(d.get('ok','UNKNOWN'))); print('ARMED='+str(d.get('armed','UNKNOWN'))); print('ARM_COMMAND='+str(d.get('command','UNKNOWN'))); print('ARM_EXPIRES_IN_MS='+str(d.get('expires_in_ms','UNKNOWN')))
    for p in runs:
        d=loadj(p); print('RUN_OK='+str(d.get('ok','UNKNOWN'))); print('RUN_ACCEPTED='+str(d.get('accepted','UNKNOWN'))); print('RUN_COMMAND='+str(d.get('command','UNKNOWN'))); print('BROADCAST_COUNT='+str(d.get('broadcast_count','UNKNOWN'))); print('ACTION='+str(d.get('action','UNKNOWN'))); print('TARGET_PACKAGE='+str(d.get('target_package','UNKNOWN'))); print('CMD_TYPE='+str(d.get('cmd_type','UNKNOWN'))); print('SETTING_KEY='+str(d.get('setting_key','UNKNOWN')))
    print('DEVICE_OPERATION=NONE'); print('WIFI_MUTATION=NONE'); return 0


def cmd_effect(a):
    results=find_one(a.root,'result.json'); analyses=find_one(a.root,'effect-analysis.json')
    print('TEST22_EFFECT_RECOVERY=YES'); print('RESULT_COUNT='+str(len(results))); print('ANALYSIS_COUNT='+str(len(analyses)))
    for p in results:
        d=loadj(p); q=d.get('probe',{}); print('RESULT_STATE='+str(d.get('result_state','UNKNOWN'))); print('CLASSIFICATION='+str(q.get('classification','UNKNOWN'))); print('BROADCAST_COUNT='+str(q.get('broadcast_count','UNKNOWN'))); print('WIFI_DISABLED_AT_BASELINE='+str(q.get('wifi_disabled_at_baseline','UNKNOWN'))); print('WIFI_ENABLED_AFTER='+str(q.get('wifi_enabled_after_broadcast','UNKNOWN'))); print('WIFI_TRANSITION='+str(q.get('wifi_enabled_transition','UNKNOWN'))); print('ACTIVE_WIFI_NETWORK='+str(q.get('active_wifi_network_observed','UNKNOWN')))
    for p in analyses:
        d=loadj(p); print('DECISION='+str(d.get('decision','UNKNOWN'))); print('ACTIVE_WIFI_SAMPLE_COUNT='+str(d.get('active_wifi_sample_count','UNKNOWN'))); print('ACTIVE_WIFI_DEFAULT_ROUTE_SAMPLE_COUNT='+str(d.get('active_wifi_default_route_sample_count','UNKNOWN'))); print('DIRECT_SOCKET_ATTEMPTED='+str(d.get('direct_socket_attempted','UNKNOWN')))
    print('DEVICE_OPERATION=NONE'); print('WIFI_MUTATION=NONE'); return 0

KEEP_RE = re.compile(r'^(?:[A-Z][A-Z0-9_]*=|.*(?:PASS|FAIL|ERROR|HOLD|REFUSED|UNKNOWN|DECISION|CLASSIFICATION|WIFI_|WLAN0_|ROUTE_|SOCKET_|STATE_|EXECUTION_|PHONE_).*)$')
def cmd_compact(a):
    src=sys.stdin if a.input=='-' else open(a.input,'r',errors='replace')
    count=0
    try:
        for line in src:
            line=line.rstrip('\r\n')
            if KEEP_RE.match(line.strip()):
                print(redact(line)); count+=1
                if a.max_lines and count>=a.max_lines: break
    finally:
        if src is not sys.stdin: src.close()
    print('COMPACT_LINE_COUNT='+str(count)); return 0


def build_parser():
    p=argparse.ArgumentParser(description='Canonical read-only Test 22 utility')
    sp=p.add_subparsers(dest='cmd')
    for name in ('device-status','monitor','isolation'):
        q=sp.add_parser(name); q.add_argument('--adb'); q.add_argument('--serial')
        if name=='monitor': q.add_argument('--interval',type=float,default=1.0); q.add_argument('--timeout',type=float,default=120.0)
        if name=='isolation': q.add_argument('--samples',type=int,default=5); q.add_argument('--interval',type=float,default=1.0)
    q=sp.add_parser('receipts'); q.add_argument('--root',required=True)
    q=sp.add_parser('effect'); q.add_argument('--root',required=True)
    q=sp.add_parser('compact'); q.add_argument('--input',required=True); q.add_argument('--max-lines',type=int,default=250)
    return p


def main():
    p=build_parser(); a=p.parse_args()
    if a.cmd=='device-status': return cmd_device_status(a)
    if a.cmd=='monitor': return cmd_monitor(a)
    if a.cmd=='isolation': return cmd_isolation(a)
    if a.cmd=='receipts': return cmd_receipts(a)
    if a.cmd=='effect': return cmd_effect(a)
    if a.cmd=='compact': return cmd_compact(a)
    p.print_help(); return 2

if __name__=='__main__': sys.exit(main())
