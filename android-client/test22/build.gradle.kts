plugins {
    id("com.android.application")
}

android {
    namespace = "org.aimindseye.rokid.test22wifi"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.aimindseye.rokid.test22wifi"
        minSdk = 26
        // Intentionally legacy-targeted for the bounded sideload-only control-plane test and Wi-Fi capability test.
        // Android 10+ blocks the tested Wi-Fi enable/config APIs for modern-target apps.
        targetSdk = 28
        versionCode = 4
        versionName = "1.3-test22-r4.3.3"
    }

    buildTypes {
        debug { isMinifyEnabled = false }
        release { isMinifyEnabled = false }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
