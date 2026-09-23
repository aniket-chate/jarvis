import java.io.File

// Dynamic Android SDK resolution: auto-detect from environment or standard paths
val localPropsFile = file("local.properties")
if (!localPropsFile.exists() || !localPropsFile.readText().contains("sdk.dir")) {
    val candidates = listOfNotNull(
        System.getenv("ANDROID_HOME"),
        System.getenv("ANDROID_SDK_ROOT"),
        "${System.getProperty("user.home")}/AppData/Local/Android/Sdk",
        "${System.getProperty("user.home")}/Android/Sdk",
        "/usr/lib/android-sdk"
    )
    val resolvedSdk = candidates.firstOrNull { File(it).exists() }
    if (resolvedSdk != null) {
        val sanitized = resolvedSdk.replace("\\", "\\\\")
        localPropsFile.writeText("## Auto-generated portable local.properties for JARVIS Android Client\nsdk.dir=$sanitized\n")
    }
}

pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "JarvisClient"
include(":app")

