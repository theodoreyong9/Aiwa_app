package com.aiwa.client

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppUpdateTest {
    private val sha = "ebff2e7a1b2c3d4e5f60718293a4b5c6d7e8f901"

    @Test
    fun theInstalledBuildIsRecognisedByItsCommit() {
        assertTrue(isUpToDate("1.ebff2e7", sha))
        assertFalse(isUpToDate("1.0f73312", sha))
    }

    @Test
    fun aBuildMadeByHandIsNeverUpToDate() {
        assertFalse(isUpToDate("1.local", sha))
        assertFalse(isUpToDate(null, sha))
        assertFalse(isUpToDate("", sha))
    }

    @Test
    fun onlyAnApkIsInstalled() {
        assertTrue(looksLikeApk(byteArrayOf('P'.code.toByte(), 'K'.code.toByte(), 3, 4), 40_000_000))
        assertFalse(looksLikeApk("<h".toByteArray(), 40_000_000))
        assertFalse(looksLikeApk(byteArrayOf('P'.code.toByte(), 'K'.code.toByte()), 500))
    }

    @Test
    fun onlyAVideoIsShared() {
        val mp4 = byteArrayOf(0, 0, 0, 24, 'f'.code.toByte(), 't'.code.toByte(), 'y'.code.toByte(), 'p'.code.toByte(), 0, 0, 0, 0)
        assertTrue(looksLikeVideo(mp4, 5_000_000))
        assertFalse(looksLikeVideo("<!doctype html>".toByteArray(), 5_000_000))
        assertFalse(looksLikeVideo(mp4, 100))
    }
}
