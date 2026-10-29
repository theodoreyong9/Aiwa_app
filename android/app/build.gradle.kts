plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "com.aiwa.app"
    compileSdk = 36
    defaultConfig {
        // The identifier of the first Aiwa: a phone that already has it updates in place and loses nothing.
        applicationId = "com.aiwa.store"
        minSdk = 26
        targetSdk = 36
        // The CI numbers every build (run number, commit): the person can see which build is installed. A local build stays 1 / "local".
        versionCode = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 1
        versionName = "1." + (System.getenv("GITHUB_SHA")?.take(7) ?: "local")
        // The speech model's native library (Vosk) only for the phones that exist.
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
    }
    // A pinned debug key: without it every CI build is signed with a different one and Android refuses to install it over the previous one.
    // It is the well-known Android debug key (alias and password "android"), never a secret: the point is that every build uses the SAME one.
    signingConfigs {
        getByName("debug") {
            storeFile = rootProject.file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    // The web app (wallet, voir, chambre, home) is part of the APK: its build is copied into the assets, never committed.
    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("generated/web-assets"))
}

val webDist = rootProject.file("../web/dist")
val copyWeb by tasks.registering(Copy::class) {
    description = "Copies the web app (npm run build:web) into the APK's assets"
    doFirst { check(webDist.isDirectory) { "Build the web app first: npm install && npm run build:web (expected $webDist)" } }
    from(webDist)
    into(layout.buildDirectory.dir("generated/web-assets/web"))
}
tasks.matching { it.name.startsWith("merge") && it.name.endsWith("Assets") }.configureEach { dependsOn(copyWeb) }

dependencies {
    implementation(project(":client"))
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.webkit:webkit:1.14.0")
    implementation("androidx.viewpager2:viewpager2:1.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    // The speech recognizer that listens for the wake word on the phone itself: Apache 2.0, offline.
    implementation("com.alphacephei:vosk-android:0.3.47")
    implementation("net.java.dev.jna:jna:5.13.0@aar")
}
