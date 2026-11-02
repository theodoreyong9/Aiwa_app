package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class RuntimeFileTest {
    private fun file(api: Int = 1, rev: Long = 202611021430, body: String = "(function(){ window.__aiwaHome = true; })();") = "/* aiwa-home-runtime api=$api rev=$rev */\n$body"

    @Test
    fun aNewerRuntimeMadeForThisApplicationIsTaken() {
        assertNull(RuntimeFile.refusal(file(), 1, 202611010000, emptySet()))
    }

    @Test
    fun theHeaderIsReadAndNothingElseIsTaken() {
        assertEquals(202611021430, RuntimeFile.header(file())?.rev)
        assertNull(RuntimeFile.header("(function(){})()"))
        assertNull(RuntimeFile.header("<html>"))
        assertNotNull(RuntimeFile.refusal("<html>window.__aiwaHome</html>", 1, 0, emptySet()))
    }

    @Test
    fun anOlderOrOtherRuntimeIsRefused() {
        assertNotNull("not newer", RuntimeFile.refusal(file(rev = 202611010000), 1, 202611010000, emptySet()))
        assertNotNull("made for another door", RuntimeFile.refusal(file(api = 2), 1, 0, emptySet()))
        assertNotNull("rejected before", RuntimeFile.refusal(file(), 1, 0, setOf(202611021430)))
        assertNotNull("not the runtime", RuntimeFile.refusal(file(body = "alert(1)"), 1, 0, emptySet()))
        assertNotNull("too big", RuntimeFile.refusal(file(body = "x".repeat(RuntimeFile.MAX_BYTES) + "window.__aiwaHome"), 1, 0, emptySet()))
        assertNotNull(RuntimeFile.refusal(null, 1, 0, emptySet()))
    }
}
