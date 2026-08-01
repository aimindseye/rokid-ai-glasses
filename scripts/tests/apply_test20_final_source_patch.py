#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, shutil, sys, tempfile
from pathlib import Path

PACKAGE_PATH=Path('android-client/test20r32/src/main/java/org/aimindseye/rokid/cxrphotoqualification')
MAIN_REL=PACKAGE_PATH/'MainActivity.java'
CONTROLLER_REL=PACKAGE_PATH/'CxrLPhotoController.java'
CONTRACT_REL=PACKAGE_PATH/'Test20R32Contract.java'
GRADLE_REL=Path('android-client/test20r32/build.gradle.kts')
NEW_VERSION='1.0-test20-final'

class PatchError(RuntimeError): pass

def require_once(text, old, label):
    c=text.count(old)
    if c!=1: raise PatchError(f'{label}: expected exactly one r3.3 marker, found {c}')

def replace_once(text, old, new, label):
    require_once(text,old,label); return text.replace(old,new,1)

def patch_main(text:str)->str:
    if 'Test 20 Final — Canonical One-Shot Photo Controller' in text and 'CANONICAL_POSTCONNECT_REREGISTER' in text:
        return text
    if 'Test 20 r3.3 — Callback Non-Delivery Closure' not in text or 'callback_profile_selected' not in text:
        raise PatchError('MainActivity is not at the accepted r3.3 diagnostic baseline')
    text=replace_once(text,'    private String callbackProfile;\n','', 'MainActivity profile field')
    text=replace_once(text,
        '        callbackProfile = getIntent().getStringExtra("callback_profile");\n'
        '        if (callbackProfile == null || callbackProfile.isBlank()) {\n'
        '            callbackProfile = "STRONG_REF_PRECONNECT";\n'
        '        }\n','', 'MainActivity profile input')
    old='''        logger.event("callback_profile_selected", EvidenceLogger.details(
                "profile", callbackProfile,
                "one_photo_request_per_run", true,
                "audio_operation_enabled", false,
                "payload_persistence_enabled", false));
'''
    new='''        logger.event("canonical_photo_controller_lifecycle", EvidenceLogger.details(
                "lifecycle", "CANONICAL_POSTCONNECT_REREGISTER",
                "strong_callback_reference", true,
                "preconnect_registration", true,
                "post_service_status_reregistration", true,
                "one_photo_request_per_run", true,
                "audio_operation_enabled", false,
                "payload_persistence_enabled", false));
'''
    text=replace_once(text,old,new,'MainActivity canonical lifecycle event')
    text=replace_once(text,
        '        controller = new CxrLPhotoController(this, logger, callbackProfile,\n'
        '                new CxrLPhotoController.Callback() {',
        '        controller = new CxrLPhotoController(this, logger,\n'
        '                new CxrLPhotoController.Callback() {',
        'MainActivity controller constructor')
    text=replace_once(text,
        '        title.setText("Test 20 r3.3 — Callback Non-Delivery Closure");',
        '        title.setText("Test 20 Final — Canonical One-Shot Photo Controller");',
        'MainActivity title')
    text=replace_once(text,
        '        scope.setText("r3.3 preserves the r3.2.1.3 two-phase one-shot gate and instruments the post-takePhoto callback path. Exactly one photo request per run; no preview, file write, upload, audio operation, or cloud request. Profile: " + callbackProfile);',
        '        scope.setText("Canonical lifecycle: retain one image callback, register before connect, re-register the same callback after successful service status, then allow the host to arm exactly one takePhoto(1920,1080,80) request. No preview, file write, upload, audio operation, or cloud request.");',
        'MainActivity scope')
    return text

def patch_contract(text:str)->str:
    if 'IMAGE_CALLBACK_LIFECYCLE' in text and 'POST_TAKEPHOTO_WATCHDOG_DELAYS_MS' in text:
        return text
    if 'R3_3_WATCHDOG_DELAYS_MS' not in text:
        raise PatchError('Test20R32Contract is not at the r3.3 baseline')
    text=replace_once(text,
        'static final String EVENT_SCHEMA = "rokid.test20-r3.2.cxrl-one-shot-photo.v1";',
        'static final String EVENT_SCHEMA = "rokid.test20-final.cxrl-one-shot-photo.v1";',
        'Contract final event schema')
    marker='''    static final String PHOTO_ARGUMENT_SEMANTICS =
            "WORKING_HYPOTHESIS_WIDTH_HEIGHT_QUALITY_NOT_GENERALIZED";
'''
    replacement=marker+'''    static final String IMAGE_CALLBACK_LIFECYCLE =
            "STRONG_REFERENCE_PRECONNECT_PLUS_POST_SERVICE_STATUS_REREGISTRATION";
'''
    text=replace_once(text,marker,replacement,'Contract lifecycle constant')
    text=text.replace('R3_3_WATCHDOG_DELAYS_MS','POST_TAKEPHOTO_WATCHDOG_DELAYS_MS')
    return text

def patch_controller(text:str)->str:
    if 'canonical_image_callback_reregistration_result' in text and 'IMAGE_CALLBACK_LIFECYCLE' in text and 'callbackProfile' not in text:
        return text
    if 'image_callback_reregistration_result' not in text or 'ARG3_ZERO_DIAGNOSTIC' not in text or 'callbackProfile' not in text:
        raise PatchError('CxrLPhotoController is not at the accepted r3.3 diagnostic baseline')
    text=replace_once(text,'    private final String callbackProfile;\n','', 'Controller profile field')
    old_ctor='''    CxrLPhotoController(Activity activity, EvidenceLogger logger, String callbackProfile, Callback callback) {
        this.activity = activity;
        this.logger = logger;
        this.callbackProfile = normalizeProfile(callbackProfile);
        this.callback = callback;
    }
    private static String normalizeProfile(String value) {
        String normalized = value == null ? "" : value.trim().toUpperCase();
        if (normalized.equals("STRONG_REF_PRECONNECT")
                || normalized.equals("POSTCONNECT_REREGISTER")
                || normalized.equals("ARG3_ZERO_DIAGNOSTIC")) {
            return normalized;
        }
        throw new IllegalArgumentException("Unsupported r3.3 callback profile: " + value);
    }
'''
    new_ctor='''    CxrLPhotoController(Activity activity, EvidenceLogger logger, Callback callback) {
        this.activity = activity;
        this.logger = logger;
        this.callback = callback;
    }
'''
    text=replace_once(text,old_ctor,new_ctor,'Controller canonical constructor')

    old_rereg='''    private boolean maybeReregisterImageCallbackAfterServiceStatus() {
        boolean requested = callbackProfile.equals("POSTCONNECT_REREGISTER")
                || callbackProfile.equals("ARG3_ZERO_DIAGNOSTIC");
        if (!requested) {
            logger.event("image_callback_reregistration_skipped", EvidenceLogger.details(
                    "profile", callbackProfile,
                    "reason", "PROFILE_PRECONNECT_ONLY",
                    "strong_reference_held", imageStreamCallback != null,
                    "media_request_issued", photoRequestIssued.get()));
            return true;
        }
        boolean returned = false;
        String errorClass = "";
        int identityBefore = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);
        try {
            if (imageStreamCallback == null) throw new IllegalStateException("image callback strong reference missing");
            link.setCXRImageCbk(imageStreamCallback);
            returned = true;
            imageCallbackRegistrationElapsedMs = SystemClock.elapsedRealtime();
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }
        int identityAfter = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);
        logger.event("image_callback_reregistration_result", EvidenceLogger.details(
                "method", "setCXRImageCbk(IImageStreamCbk)V",
                "registration_phase", "POST_SERVICE_STATUS",
                "registration_returned", returned,
                "registration_error_class", errorClass,
                "callback_identity_before", identityBefore,
                "callback_identity_after", identityAfter,
                "same_callback_identity", identityBefore >= 0 && identityBefore == identityAfter,
                "strong_reference_held", imageStreamCallback != null,
                "callback_profile", callbackProfile,
                "media_request_issued", photoRequestIssued.get()));
        return returned;
    }
'''
    new_rereg='''    private boolean reregisterImageCallbackAfterServiceStatus() {
        boolean returned = false;
        String errorClass = "";
        int identityBefore = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);
        try {
            if (imageStreamCallback == null) throw new IllegalStateException("image callback strong reference missing");
            link.setCXRImageCbk(imageStreamCallback);
            returned = true;
            imageCallbackRegistrationElapsedMs = SystemClock.elapsedRealtime();
        } catch (Throwable error) {
            errorClass = error.getClass().getName();
        }
        int identityAfter = imageStreamCallback == null ? -1 : System.identityHashCode(imageStreamCallback);
        boolean sameIdentity = identityBefore >= 0 && identityBefore == identityAfter;
        imageCallbackRegistered = returned && sameIdentity;
        logger.event("canonical_image_callback_reregistration_result", EvidenceLogger.details(
                "method", "setCXRImageCbk(IImageStreamCbk)V",
                "registration_phase", "POST_SERVICE_STATUS",
                "canonical_requirement", true,
                "registration_returned", returned,
                "registration_error_class", errorClass,
                "callback_identity_before", identityBefore,
                "callback_identity_after", identityAfter,
                "same_callback_identity", sameIdentity,
                "strong_reference_held", imageStreamCallback != null,
                "image_callback_lifecycle", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,
                "media_request_issued", photoRequestIssued.get()));
        return imageCallbackRegistered;
    }
'''
    text=replace_once(text,old_rereg,new_rereg,'Controller canonical post-connect reregistration')
    text=replace_once(text,
        '        if (!maybeReregisterImageCallbackAfterServiceStatus()) {\n'
        '            finish("IMAGE_CALLBACK_REREGISTRATION_FAILED", false);\n'
        '            return;\n'
        '        }',
        '        if (!reregisterImageCallbackAfterServiceStatus()) {\n'
        '            finish("IMAGE_CALLBACK_REREGISTRATION_FAILED", false);\n'
        '            return;\n'
        '        }',
        'Controller reregistration call')
    text=replace_once(text,
        '        int requestArg3 = callbackProfile.equals("ARG3_ZERO_DIAGNOSTIC")\n'
        '                ? 0 : Test20R32Contract.PHOTO_ARG_3;',
        '        int requestArg3 = Test20R32Contract.PHOTO_ARG_3;',
        'Controller fixed photo arg3')
    text=replace_once(text,
        '                "argument_semantics", requestArg3 == 0\n'
        '                        ? "DIAGNOSTIC_THIRD_ARGUMENT_ZERO_SEMANTICS_NOT_ASSUMED"\n'
        '                        : Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,',
        '                "argument_semantics", Test20R32Contract.PHOTO_ARGUMENT_SEMANTICS,',
        'Controller fixed arg3 semantics')
    # Replace remaining diagnostic profile labels only after exact r3.3 blocks have been consumed.
    text=text.replace('\"callback_profile\", callbackProfile,','\"image_callback_lifecycle\", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,')
    text=text.replace('\"profile\", callbackProfile,','\"image_callback_lifecycle\", Test20R32Contract.IMAGE_CALLBACK_LIFECYCLE,')
    text=text.replace('Test20R32Contract.R3_3_WATCHDOG_DELAYS_MS','Test20R32Contract.POST_TAKEPHOTO_WATCHDOG_DELAYS_MS')
    if 'callbackProfile' in text or 'ARG3_ZERO_DIAGNOSTIC' in text or 'STRONG_REF_PRECONNECT' in text or 'POSTCONNECT_REREGISTER' in text:
        raise PatchError('Controller canonicalization left diagnostic profile code behind')
    return text

def patch_gradle(text:str)->str:
    if f'versionName = "{NEW_VERSION}"' in text: return text
    if 'versionName = "1.0-test20-r3.3"' not in text: raise PatchError('build.gradle.kts is not at r3.3')
    text=replace_once(text,'        versionCode = 3\n','        versionCode = 4\n','Gradle versionCode')
    text=replace_once(text,'        versionName = "1.0-test20-r3.3"\n',f'        versionName = "{NEW_VERSION}"\n','Gradle versionName')
    return text

def atomic_write(path:Path,text:str):
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent),text=True)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as h:
            h.write(text); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--backup-dir'); ap.add_argument('--check-only',action='store_true'); a=ap.parse_args()
    repo=Path(a.repo).expanduser().resolve()
    if not (repo/'.git').is_dir(): print(f'ERROR: not git repo: {repo}',file=sys.stderr); return 2
    paths=[repo/MAIN_REL,repo/CONTROLLER_REL,repo/CONTRACT_REL,repo/GRADLE_REL]
    for p in paths:
        if not p.is_file(): print(f'ERROR: required source missing: {p}',file=sys.stderr); return 1
    originals={p:p.read_text(encoding='utf-8') for p in paths}
    try:
        updated={repo/MAIN_REL:patch_main(originals[repo/MAIN_REL]),repo/CONTROLLER_REL:patch_controller(originals[repo/CONTROLLER_REL]),repo/CONTRACT_REL:patch_contract(originals[repo/CONTRACT_REL]),repo/GRADLE_REL:patch_gradle(originals[repo/GRADLE_REL])}
    except PatchError as e:
        print(f'ERROR: {e}',file=sys.stderr); print('REPOSITORY_MUTATION=NONE',file=sys.stderr); return 1
    changed=[p for p in paths if updated[p]!=originals[p]]
    if a.check_only:
        print('TEST20_FINAL_SOURCE_PATCH_PREFLIGHT=PASS'); print(f'FILES_REQUIRING_PATCH={len(changed)}'); print('BASELINE_REQUIRED=accepted_r3.3'); return 0
    if not changed:
        print('TEST20_FINAL_SOURCE_PATCH=ALREADY_APPLIED'); return 0
    backup=Path(a.backup_dir).expanduser().resolve() if a.backup_dir else repo/'.git/test20-final-source-backup'
    for p in changed:
        q=backup/p.relative_to(repo); q.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,q)
    try:
        for p in changed: atomic_write(p,updated[p])
    except Exception as e:
        for p in changed:
            q=backup/p.relative_to(repo)
            if q.is_file(): shutil.copy2(q,p)
        print(f'ERROR: source write failed and restored: {e}',file=sys.stderr); return 1
    print('TEST20_FINAL_SOURCE_PATCH=PASS'); print(f'FILES_PATCHED={len(changed)}'); print(f'BACKUP_DIR={backup}')
    print('CANONICAL_IMAGE_CALLBACK_LIFECYCLE=STRONG_REFERENCE_PRECONNECT_PLUS_POST_SERVICE_STATUS_REREGISTRATION')
    print('R3_2_1_3_TWO_PHASE_ARMING=PRESERVED'); print('MAX_PHOTO_REQUESTS_PER_RUN=1'); print('ARG3_ZERO_DIAGNOSTIC=REMOVED_FROM_CANONICAL_PATH')
    return 0
if __name__=='__main__': raise SystemExit(main())
