#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, subprocess, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
SRC_PATH=HERE/'apply_test20_final_source_patch.py'
spec=importlib.util.spec_from_file_location('srcmod',SRC_PATH); src=importlib.util.module_from_spec(spec); spec.loader.exec_module(src)

def write(p:Path,s:str): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s,encoding='utf-8')

def create_repo(root:Path):
    (root/'.git').mkdir(parents=True)
    pkg=root/src.PACKAGE_PATH
    main='''package org.aimindseye.rokid.cxrphotoqualification;\nclass MainActivity {\n    private String callbackProfile;\n    void x(){\n        callbackProfile = getIntent().getStringExtra("callback_profile");\n        if (callbackProfile == null || callbackProfile.isBlank()) {\n            callbackProfile = "STRONG_REF_PRECONNECT";\n        }\n        logger.event("callback_profile_selected", EvidenceLogger.details(\n                "profile", callbackProfile,\n                "one_photo_request_per_run", true,\n                "audio_operation_enabled", false,\n                "payload_persistence_enabled", false));\n        controller = new CxrLPhotoController(this, logger, callbackProfile,\n                new CxrLPhotoController.Callback() {\n        title.setText("Test 20 r3.3 — Callback Non-Delivery Closure");\n        scope.setText("r3.3 preserves the r3.2.1.3 two-phase one-shot gate and instruments the post-takePhoto callback path. Exactly one photo request per run; no preview, file write, upload, audio operation, or cloud request. Profile: " + callbackProfile);\n        // operator_gate_host_command PHASE 2 — ARMED: capture ONE photo\n    }}\n}\n'''
    controller='''package org.aimindseye.rokid.cxrphotoqualification;\nclass CxrLPhotoController {\n    private final String callbackProfile;\n    private IImageStreamCbk imageStreamCallback;\n    CxrLPhotoController(Activity activity, EvidenceLogger logger, String callbackProfile, Callback callback) {\n        this.activity = activity;\n        this.logger = logger;\n        this.callbackProfile = normalizeProfile(callbackProfile);\n        this.callback = callback;\n    }\n    private static String normalizeProfile(String value) {\n        String normalized = value == null ? "" : value.trim().toUpperCase();\n        if (normalized.equals("STRONG_REF_PRECONNECT")\n                || normalized.equals("POSTCONNECT_REREGISTER")\n                || normalized.equals("ARG3_ZERO_DIAGNOSTIC")) {\n            return normalized;\n        }\n        throw new IllegalArgumentException("Unsupported r3.3 callback profile: " + value);\n    }\n    void register(){ link.setCXRImageCbk(imageStreamCallback); logger.event("x", EvidenceLogger.details("callback_profile", callbackProfile,)); }\n    private boolean maybeReregisterImageCallbackAfterServiceStatus() {\n        boolean requested = callbackProfile.equals("POSTCONNECT_REREGISTER")\n                || callbackProfile.equals("ARG3_ZERO_DIAGNOSTIC");\n        if (!requested) {\n            logger.event("image_callback_reregistration_skipped", EvidenceLogger.details(\n                    "profile", callbackProfile,\n                    "reason", "PROFILE_PRECONNECT_ONLY",\n                    "strong_reference_held", imageStreamCallback != null,\n                    "media_request_issued", photoRequestIssued.get()));\n            return true;\n        }\n        boolean returned = false;\n        String errorClass = "";\n        int identityBefore = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);\n        try {\n            if (imageStreamCallback == null) throw new IllegalStateException("image callback strong reference missing");\n            link.setCXRImageCbk(imageStreamCallback);\n            returned = true;\n            imageCallbackRegistrationElapsedMs = SystemClock.elapsedRealtime();\n        } catch (Throwable error) {\n            errorClass = error.getClass().getName();\n        }\n        int identityAfter = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);\n        logger.event("image_callback_reregistration_result", EvidenceLogger.details(\n                "method", "setCXRImageCbk(IImageStreamCbk)V",\n                "registration_phase", "POST_SERVICE_STATUS",\n                "registration_returned", returned,\n                "registration_error_class", errorClass,\n                "callback_identity_before", identityBefore,\n                "callback_identity_after", identityAfter,\n                "same_callback_identity", identityBefore >= 0 && identityBefore == identityAfter,\n                "strong_reference_held", imageStreamCallback != null,\n                "callback_profile", callbackProfile,\n                "media_request_issued", photoRequestIssued.get()));\n        return returned;\n    }\n    void service(){\n        if (!maybeReregisterImageCallbackAfterServiceStatus()) {\n            finish("IMAGE_CALLBACK_REREGISTRATION_FAILED", false);\n            return;\n        }\n        photoReady = true;\n    }\n    void photo(){\n        if (!hostArmGranted.compareAndSet(true, false)) return; // operator_gate_arm_result\n        int requestArg3 = callbackProfile.equals("ARG3_ZERO_DIAGNOSTIC")\n                ? 0 : Test20R32Contract.PHOTO_ARG_3;\n        returned = link.takePhoto(Test20R32Contract.PHOTO_ARG_1, Test20R32Contract.PHOTO_ARG_2, requestArg3);\n        logger.event("photo_request_result", EvidenceLogger.details(\n                "argument_semantics", requestArg3 == 0\n                        ? "DIAGNOSTIC_THIRD_ARGUMENT_ZERO_SEMANTICS_NOT_ASSUMED"\n                        : Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,\n                "callback_profile", callbackProfile,));\n        for (long d: Test20R32Contract.R3_3_WATCHDOG_DELAYS_MS) {}\n    }\n}\n'''
    contract='''package org.aimindseye.rokid.cxrphotoqualification;\nclass Test20R32Contract {\n    static final String EVENT_SCHEMA = "rokid.test20-r3.2.cxrl-one-shot-photo.v1";\n    static final int PHOTO_ARG_1=1920, PHOTO_ARG_2=1080, PHOTO_ARG_3=80;\n    static final String PHOTO_ARGUMENT_SEMANTICS =\n            "WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED";\n    static final long[] R3_3_WATCHDOG_DELAYS_MS = new long[] {1000L,5000L};\n}\n'''
    gradle='''plugins {}\nandroid { defaultConfig {\n        versionCode = 3\n        versionName = "1.0-test20-r3.3"\n} }\nval cxrLVersion = providers.gradleProperty("rokidCxrLVersion")\n    .orNull\n    ?.trim()\n    ?.takeIf { it.isNotEmpty() }\nif (cxrLVersion != null) {\n    dependencies {\n        implementation("com.rokid.cxr:client-l:$cxrLVersion")\n    }\n}\nif (cxrLVersion != "1.0.1") { throw GradleException("pinned") }\n'''
    write(pkg/'MainActivity.java',main); write(pkg/'CxrLPhotoController.java',controller); write(pkg/'Test20R32Contract.java',contract); write(root/src.GRADLE_REL,gradle)
    docs={
      'docs/developer/current-status.md':'''# Developer Current Status\n<!-- wiki-status: audience=developer; evidence=validated; last_reviewed=2026-07-31 -->\n| Last reviewed | 2026-07-31 |\n| CXR-L one-shot photo qualification | Test 20 r3.2 implementation ready for governed build and one physical attempt; exactly one bounded photo request, no payload persistence |\n| Independent camera capture | Not yet tested |\nThe accepted runtime-qualified delta is limited to\n`setCXRImageCbk(IImageStreamCbk)`, `setCXRAudioCbk(IAudioStreamCbk)`,\n`getServiceVersion()`, `getServiceVersionCode()`, and\n`isGlassBtConnected()`. Photo capture, audio streaming, payload formats,\nparameter semantics, and media transport behavior remain unqualified. The next\nbounded gate is Test 20 r3.2, a separately governed one-shot photo design.\n## Evidence\n''',
      'docs/developer/companion-app/requirements.md':'# Companion-App Requirements\n<!-- wiki-status: last_reviewed=2026-07-30 -->\n| Last reviewed | 2026-07-30 |\n## Safety and privacy requirements\n',
      'docs/research/connection-protocol/README.md':'# Stock Connection Protocol and Minimal Companion Research\nbody\n',
      'docs/research/README.md':'# Research Index\n## Current boundary\n',
      'docs/README.md':'# Documentation Home\n\n## Research and evidence\n\nStart with the [Research library](research/README.md) for validated numbered tests.\n\n## Shared reference\n',
      'docs/tests/README.md':'# Tests and Qualification History\nnumbered product/device tests through **Test 18**\n| 18 | Developer Mode and USB ADB control-path static/offline follow-up |\n',
      'docs/tests/test-matrix.md':'# Test and Research Matrix\n| 18 | USB ADB control-path follow-up | 18A–18D | PASS in static/offline scope; runtime invocation unresolved | [Sanitized summary](../../evidence/sanitized/glasses-os-services/usb-adb-control-summary.txt) |\n',
    }
    for rel,s in docs.items(): write(root/rel,s)

class FreshInstallTests(unittest.TestCase):
    def test_fresh_and_idempotent_install(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)/'repo'; create_repo(repo)
            cmd=['python3',str(HERE/'install_test20_final_overlay.py'),'--repo',str(repo)]
            p=subprocess.run(cmd,text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertIn('TEST20_FINAL_OVERLAY_INSTALL=PASS',p.stdout)
            p2=subprocess.run(cmd,text=True,capture_output=True)
            self.assertEqual(p2.returncode,0,p2.stdout+p2.stderr)
            self.assertIn('TEST20_FINAL_OVERLAY_INSTALL=PASS',p2.stdout)
            backups=sorted((repo/'.git').glob('test20-final-overlay-backup-*'))
            self.assertEqual(len(backups),2,[str(p) for p in backups])
            self.assertNotEqual(backups[0].name,backups[1].name)
            gradle=(repo/src.GRADLE_REL).read_text()
            self.assertIn('1.0-test20-final',gradle)
            self.assertIn('implementation("com.rokid.cxr:client-l:$cxrLVersion")',gradle)
            self.assertIn('cxrLVersion != "1.0.1"',gradle)
            self.assertIn('canonical_image_callback_reregistration_result',(repo/src.CONTROLLER_REL).read_text())

    def test_wrong_baseline_refused_before_overlay_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)/'repo'; create_repo(repo)
            controller=repo/src.CONTROLLER_REL
            original=controller.read_text()
            controller.write_text('wrong baseline sentinel\n')
            cmd=['python3',str(HERE/'install_test20_final_overlay.py'),'--repo',str(repo)]
            p=subprocess.run(cmd,text=True,capture_output=True)
            self.assertNotEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertIn('REPOSITORY_MUTATION=NONE',p.stdout+p.stderr)
            self.assertEqual(controller.read_text(),'wrong baseline sentinel\n')
            self.assertFalse((repo/'docs/tests/test-20-final-photo-control-callback-publication.md').exists())

if __name__=='__main__': unittest.main(verbosity=2)
