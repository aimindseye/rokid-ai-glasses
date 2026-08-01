plugins {
    id("com.android.application")
}

android {
    namespace = "org.aimindseye.rokid.cxrphotoqualification"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.aimindseye.rokid.cxrphotoqualification"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "1.0-test20-r3.2"
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
gradle.taskGraph.whenReady(
    object : org.gradle.api.Action<org.gradle.api.execution.TaskExecutionGraph> {
        override fun execute(graph: org.gradle.api.execution.TaskExecutionGraph) {
            val selected = graph.allTasks.any { task -> task.project.path == modulePath }
            if (selected && cxrLVersion == null) {
                throw GradleException(
                    "Pass -ProkidCxrLVersion=<resolved client-l version>",
                )
            }
            if (selected && cxrLVersion != "1.0.1") {
                throw GradleException(
                    "Test 20 r3.2 is attested only for " +
                        "com.rokid.cxr:client-l:1.0.1",
                )
            }
        }
    },
)
