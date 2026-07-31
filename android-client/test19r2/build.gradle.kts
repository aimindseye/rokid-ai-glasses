plugins {
    id("com.android.application")
}

android {
    namespace = "org.aimindseye.rokid.cxrlqualification"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.aimindseye.rokid.cxrlqualification"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "2.0-test19-r2"
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

val cxrLVersion = providers.gradleProperty("rokidCxrLVersion").orNull?.trim()
    ?: throw GradleException("Pass -ProkidCxrLVersion=<resolved client-l version>")

if (cxrLVersion != "1.0.1") {
    throw GradleException("Test 19 r2 is attested only for com.rokid.cxr:client-l:1.0.1")
}

dependencies {
    implementation("com.rokid.cxr:client-l:$cxrLVersion")
}
