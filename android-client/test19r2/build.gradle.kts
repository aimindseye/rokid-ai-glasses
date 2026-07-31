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
        versionCode = 4
        versionName = "2.3-test19-r2.3"
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

val cxrLVersion = providers.gradleProperty("rokidCxrLVersion")
    .orNull
    ?.trim()
    ?.takeIf { it.isNotEmpty() }

if (cxrLVersion != null) {
    dependencies {
        implementation("com.rokid.cxr:client-l:$cxrLVersion")
    }
}

val modulePath = project.path
gradle.taskGraph.whenReady { graph ->
    val test19r2TaskSelected = graph.allTasks.any { task -> task.project.path == modulePath }
    if (test19r2TaskSelected && cxrLVersion == null) {
        throw GradleException("Pass -ProkidCxrLVersion=<resolved client-l version>")
    }
    if (test19r2TaskSelected && cxrLVersion != "1.0.1") {
        throw GradleException("Test 19 r2 is attested only for com.rokid.cxr:client-l:1.0.1")
    }
}
