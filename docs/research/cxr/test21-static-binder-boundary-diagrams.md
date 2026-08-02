# Test 21 — Diagrams

## 1) High-level closure structure

```mermaid
flowchart LR
    A[r3.3.4.2.6.1.1\nService-side / client Binder ABI] --> C[Combined static Binder boundary]
    B[r3.3.4.2.6.1.2\nCallback Proxy + Parcel baseline] --> D[r3.3.4.2.6.1.3\nHost-JVM Stub dispatch recovery]
    D --> C
```

**Interpretation:** `r3.3.4.2.6.1.1` closed the service-side/client ABI, while `r3.3.4.2.6.1.3` completed the callback side by closing the seven baseline Stub-confirmation gaps left by `r3.3.4.2.6.1.2`.

## 2) Client ↔ service ↔ callback flow

```mermaid
sequenceDiagram
    participant App as Clean-room client app
    participant Proxy as Client-side service Proxy
    participant Binder as Binder kernel transport
    participant Service as Rokid service Stub/implementation
    participant Cb as Client callback Stub

    App->>Proxy: invoke service method
    Proxy->>Binder: transact(code, request Parcel)
    Binder->>Service: onTransact(code, request Parcel)
    Service-->>Binder: reply Parcel
    Binder-->>Proxy: readException() + reply fields
    Proxy-->>App: return result

    Service->>Binder: callback transact(code, request Parcel)
    Binder->>Cb: callback Stub.onTransact(code, Parcel)
    Cb-->>Service: reply / completion
```

**Interpretation:** Test 21 describes the static structure of both directions: forward service calls and reverse callback calls.

## 3) Callback-side evidence pipeline

```mermaid
flowchart TD
    P[Accepted callback Proxy map\n21 methods / 21 Parcel contracts] --> H[Host-JVM Stub dispatch harness]
    J[Exact accepted classes.jar] --> H
    O[Minimal clean-room android.os stand-ins] --> H
    H --> M[Observed callback method reached]
    M --> X{Matches accepted Proxy code?}
    X -- Yes --> Y[Two-source callback confirmation]
    X -- No --> Z[Transaction mismatch]
```

**Interpretation:** `r3.3.4.2.6.1.3` did not merely restate the Proxy map. It independently re-confirmed each callback transaction by executing the compiled Stub dispatch path on the host JVM.

## 4) Baseline gap and closure

```mermaid
flowchart LR
    A[Baseline onTransact confirmations\n14 / 21] --> B[Seven unresolved methods]
    B --> C[Host-JVM Stub dispatch recovery]
    C --> D[Final confirmations\n21 / 21]
    D --> E[All 7 interfaces ABI-ready]
```

**Interpretation:** The key improvement from baseline to final closure is the recovery of the seven unresolved callback Stub confirmations.

## 5) Final callback inventory

```mermaid
flowchart TD
    ROOT[Callback interfaces: 7] --> AI[AI_EVENT: 4 methods]
    ROOT --> AU[AUDIO: 3 methods]
    ROOT --> CC[CUSTOM_CMD: 1 method]
    ROOT --> CV[CUSTOM_VIEW: 5 methods]
    ROOT --> DS[DEVICE_STATUS: 1 method]
    ROOT --> GA[GLASS_APP: 5 methods]
    ROOT --> IM[IMAGE: 2 methods]
```

**Interpretation:** The final callback-side Binder ABI covers all seven callback interfaces and all twenty-one callback methods.
