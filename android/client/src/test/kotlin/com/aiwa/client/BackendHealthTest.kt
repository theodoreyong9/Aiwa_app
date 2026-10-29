package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BackendHealthTest {
    @Test fun withoutTermuxItIsSaidAtOnce() {
        assertEquals(Verdict.TERMUX_MISSING, verdict(termuxInstalled = false, startsWithoutAnswer = 0))
        assertEquals(Verdict.TERMUX_MISSING, verdict(termuxInstalled = false, startsWithoutAnswer = 5))
    }

    @Test fun aBackendThatNeverComesUpIsCalledNotInstalledAfterTwoStarts() {
        assertEquals(Verdict.DOWN, verdict(termuxInstalled = true, startsWithoutAnswer = 0))
        assertEquals(Verdict.DOWN, verdict(termuxInstalled = true, startsWithoutAnswer = STARTS_BEFORE_MISSING - 1))
        assertEquals(Verdict.NOT_INSTALLED, verdict(termuxInstalled = true, startsWithoutAnswer = STARTS_BEFORE_MISSING))
        assertEquals(Verdict.NOT_INSTALLED, verdict(termuxInstalled = true, startsWithoutAnswer = 9))
    }

    @Test fun eachProblemHasItsOwnMessageAndOnlyDownPromisesAStart() {
        val messages = Verdict.values().associateWith { problemMessage(it) }
        assertEquals(Verdict.values().size, messages.values.toSet().size)
        assertTrue(messages.getValue(Verdict.TERMUX_MISSING).contains("F-Droid"))
        assertTrue(messages.getValue(Verdict.NOT_INSTALLED).contains("ligne d'installation"))
        assertFalse(messages.getValue(Verdict.TERMUX_MISSING).contains("lancement automatique"))
        assertFalse(messages.getValue(Verdict.NOT_INSTALLED).contains("lancement automatique"))
        assertTrue(messages.getValue(Verdict.DOWN).contains("lancement automatique"))
    }

    @Test fun theInstallLineIsTheOneOfTheReadmeAndTheScriptExists() {
        assertTrue(BOOTSTRAP_COMMAND.startsWith("curl -fsSL https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/"))
        assertTrue(BOOTSTRAP_COMMAND.endsWith("| bash"))
        val root = java.io.File("../..")
        val readme = java.io.File(root, "README.md").takeIf { it.exists() }?.readText()
        if (readme != null) assertTrue("the README gives the same line", readme.contains(BOOTSTRAP_COMMAND))
        if (java.io.File(root, "scripts").isDirectory) assertTrue("the script the line downloads", java.io.File(root, "scripts/bootstrap.sh").exists())
    }
}
