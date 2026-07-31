import org.gradle.api.Action
import org.gradle.api.execution.TaskExecutionGraph

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

val cxrVersion = providers.gradleProperty("rokidCxrVersion")
    .orNull
    ?.trim()
    ?.takeIf { it.isNotEmpty() }

if (cxrVersion != null) {
    dependencies {
        implementation("com.rokid.cxr:client-m:$cxrVersion")
    }
}

val modulePath = project.path
gradle.taskGraph.whenReady(
    Action<TaskExecutionGraph> { graph ->
        val test19TaskSelected = graph.allTasks.any { task -> task.project.path == modulePath }
        if (test19TaskSelected && cxrVersion == null) {
            throw GradleException("Pass -ProkidCxrVersion=<resolved client-m version>")
        }
    },
)
