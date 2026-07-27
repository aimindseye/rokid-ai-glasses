plugins {
    id("com.android.application")
}

android {
    namespace = "org.aimindseye.rokid.channelprobe"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.aimindseye.rokid.channelprobe"
        minSdk = 26
        targetSdk = 36
        versionCode = 7
        versionName = "0.7.0-r25.2.2.2"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
