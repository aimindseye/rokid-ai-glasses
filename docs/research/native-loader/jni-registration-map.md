
# Dynamically Registered JNI Map

## Exact class attribution

The following methods were captured in one `RegisterNatives` call attributed to:

```text
com.netease.nis.wrapper.MyJni
```

Absolute native pointers and runtime object handles are intentionally omitted.

| Method | JNI signature | Observed execution |
|---|---|---|
| `load` | `(Landroid/app/Application;Ljava/lang/String;)Z` | Entry observed; return not observed before process exit |
| `run` | `(Landroid/content/Context;Landroid/app/Application;)Z` | Registered; execution not observed |
| `d` | `(Ljava/lang/String;)V` | Registered; execution not observed |
| `e` | `(Ljava/lang/String;)V` | Registered; execution not observed |
| `cp` | `()V` | Registered; execution not observed |
| `ip` | `(Landroid/app/Application;)V` | Registered; execution not observed |
| `ra` | `(Landroid/content/Context;Landroid/app/Application;)Z` | Registered; execution not observed |
| `getEnvInfo` | `()Ljava/lang/String;` | Registered; execution not observed |
| `cl` | `(Ljava/lang/ClassLoader;Landroid/content/pm/ApplicationInfo;Ljava/lang/String;)Ljava/lang/ClassLoader;` | Entry and return observed; 741 ms |
| `rp` | `(Landroid/content/Context;Landroid/app/Application;)Z` | Registered; execution not observed |
| `ed` | `(Ljava/lang/String;)V` | Registered; execution not observed |

## Other attributed registrations

| Class | Method | Signature |
|---|---|---|
| `android.net.TrafficStats` | `native_tagSocketFd` | `(Ljava/io/FileDescriptor;II)I` |
| `android.net.TrafficStats` | `native_untagSocketFd` | `(Ljava/io/FileDescriptor;)I` |
| `dalvik.system.DexFile` | `getClassNameList` | `(Ljava/lang/Object;)[Ljava/lang/String;` |

## Interpretation limits

A JNI name and signature establish the Java/native registration contract. They
do not by themselves establish the method's internal semantics or its
relationship to user-facing glasses functionality. Only `cl` completion and
`load` entry were observed in this bounded startup window.
