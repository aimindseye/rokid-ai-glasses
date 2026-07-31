plugins {
    id("com.android.application")
}

android {
    namespace = "org.aimindseye.rokid.cxrqualification"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.aimindseye.rokid.cxrqualification"
        minSdk = 28
        targetSdk = 36
        versionCode = 2
        versionName = "1.1-test19-r1"
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

val cxrVersion = providers.gradleProperty("rokidCxrVersion").orNull?.trim()
    ?: throw GradleException("Pass -ProkidCxrVersion=<resolved client-m version>")

dependencies {
    implementation("com.rokid.cxr:client-m:$cxrVersion")
}
