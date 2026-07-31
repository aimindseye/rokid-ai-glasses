#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, shutil, subprocess, tempfile, threading, unittest, zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel); assert spec and spec.loader
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
EVIDENCE=load('e','scripts/tests/analyze_test19_cxr_evidence.py')
ARTIFACT=load('a','scripts/research/cxr/analyze_cxr_artifact.py')
NETWORK=load('n','scripts/tests/analyze_test19_network.py')
RESOLVER=ROOT/'scripts/research/cxr/resolve_cxr_m_maven.py'

class EvidenceTests(unittest.TestCase):
    def records(self,n):
        p=ROOT/'fixtures/synthetic/test19'/n
        return [json.loads(x) for x in p.read_text().splitlines() if x]
    def test_shared(self):
        s=EVIDENCE.analyze(self.records('pass-events.jsonl'))
        self.assertTrue(s['qualification_complete']); self.assertEqual(s['ownership_classification'],'SHARED_WITH_HI_ROKID_FOREGROUND')
        self.assertEqual(s['markers']['LOCAL_NETWORK_PRIVACY_GATE'],'PASS')
    def test_force_stop(self):
        s=EVIDENCE.analyze(self.records('force-stop-required-events.jsonl'))
        self.assertTrue(s['qualification_complete']); self.assertEqual(s['ownership_classification'],'HI_ROKID_FORCE_STOP_REQUIRED')
    def test_blocked(self):
        s=EVIDENCE.analyze(self.records('blocked-events.jsonl'))
        self.assertFalse(s['qualification_complete']); self.assertEqual(s['markers']['CUSTOM_APP_DEVICE_CONNECTION'],'BLOCKED')

class ArtifactTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('jar'),'JDK unavailable')
    def test_aar(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t); src=r/'src/com/rokid/cxr/client/extend/CxrApi.java'; src.parent.mkdir(parents=True)
            src.write_text('package com.rokid.cxr.client.extend; public final class CxrApi { public static CxrApi getInstance(){return new CxrApi();} public boolean isBluetoothConnected(){return false;} public void deinitBluetooth(){} }')
            c=r/'classes'; c.mkdir(); subprocess.run(['javac','-d',str(c),str(src)],check=True)
            jar=r/'classes.jar'; subprocess.run(['jar','cf',str(jar),'-C',str(c),'.'],check=True)
            aar=r/'client-m.aar'
            with zipfile.ZipFile(aar,'w') as z: z.write(jar,'classes.jar'); z.writestr('AndroidManifest.xml','<manifest/>')
            self.assertTrue(ARTIFACT.analyze(aar)['recognized_api_class'])

class NetworkTests(unittest.TestCase):
    def test_local_pass(self): self.assertEqual(NETWORK.analyze(ROOT/'fixtures/synthetic/test19-r1/network-local-pass.csv')['gate'],'PASS')
    def test_public_fail(self): self.assertEqual(NETWORK.analyze(ROOT/'fixtures/synthetic/test19-r1/network-public-fail.csv')['gate'],'FAIL')

class ResolverTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('jar'),'JDK unavailable')
    def test_local_maven_resolution(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); version='1.2.3'; base=root/'com/rokid/cxr/client-m'/version; base.mkdir(parents=True)
            (root/'com/rokid/cxr/client-m/maven-metadata.xml').write_text(f'<metadata><versioning><release>{version}</release><versions><version>{version}</version></versions></versioning></metadata>')
            (base/f'client-m-{version}.pom').write_text('<project/>')
            with zipfile.ZipFile(base/f'client-m-{version}.aar','w') as z: z.writestr('classes.jar',b'PK\x05\x06'+b'\0'*18)
            class Quiet(SimpleHTTPRequestHandler):
                def log_message(self,*a): pass
            old=Path.cwd()
            try:
                import os; os.chdir(root)
                server=ThreadingHTTPServer(('127.0.0.1',0),Quiet); th=threading.Thread(target=server.serve_forever,daemon=True); th.start()
                url=f'http://127.0.0.1:{server.server_port}/'
                out=root/'out'
                r=subprocess.run(['python3',str(RESOLVER),'--output',str(out),'--repository-url',url,'--metadata-url',url+'com/rokid/cxr/client-m/maven-metadata.xml'],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr+r.stdout); self.assertEqual(json.loads((out/'resolution.json').read_text())['version'],version)
            finally:
                try:
                    server.shutdown(); server.server_close()
                except Exception: pass
                os.chdir(old)

class SourceContract(unittest.TestCase):
    def test_contract(self):
        manifest=(ROOT/'android-client/test19/src/main/AndroidManifest.xml').read_text()
        settings=(ROOT/'android-client/settings.gradle.kts').read_text()
        adapter=(ROOT/'android-client/test19/src/main/java/org/aimindseye/rokid/cxrqualification/CxrReflectionAdapter.java').read_text()
        self.assertIn('android.permission.INTERNET',manifest)
        self.assertIn('maven.rokid.com/repository/maven-public',settings)
        self.assertNotIn('BluetoothSocket',adapter); self.assertNotIn('getOutputStream',adapter)
        self.assertNotIn('CredentialStore',adapter)

if __name__=='__main__': unittest.main()
