plugins {
    id("org.jetbrains.kotlin.jvm")
}
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
dependencies {
    // org.json is the phone's own; the tests run on a plain JVM, where this stands in for it
    compileOnly("org.json:json:20250107")
    testImplementation("org.json:json:20250107")
    testImplementation("junit:junit:4.13.2")
}
