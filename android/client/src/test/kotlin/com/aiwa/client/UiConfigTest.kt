package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class UiConfigTest {
    private val actions = setOf("match", "zone", "wallet")

    @Test
    fun aValidFileGivesItsKeysInOrder() {
        val out = UiConfig.parseBar("""{"v":1,"bar":[{"action":"zone","icon":"📍","label":"Autour","tone":"violet"},{"action":"wallet"}]}""", actions)!!
        assertEquals(listOf("zone", "wallet"), out.map { it.action })
        assertEquals("Autour", out[0].label)
        assertNull(out[1].label)
    }

    @Test
    fun anActionTheApplicationDoesNotKnowIsDroppedNotObeyed() {
        val out = UiConfig.parseBar("""{"v":1,"bar":[{"action":"rm -rf"},{"action":"javascript:alert(1)"},{"action":"url:http://plain.example"},{"action":"url:https://ok.example/a"},{"action":"match"}]}""", actions)!!
        assertEquals(listOf("url:https://ok.example/a", "match"), out.map { it.action })
    }

    @Test
    fun aFileThatLeavesNothingChangesNothing() {
        assertNull(UiConfig.parseBar("not json", actions))
        assertNull(UiConfig.parseBar("""{"v":2,"bar":[{"action":"zone"}]}""", actions))
        assertNull(UiConfig.parseBar("""{"v":1,"bar":[{"action":"nope"}]}""", actions))
        assertNull(UiConfig.parseBar(null, actions))
    }

    @Test
    fun theLooksAreBoundedAndTheNumberOfKeysToo() {
        val many = (1..20).joinToString(",") { """{"action":"zone","label":"${"x".repeat(30)}","tone":"#12345G"}""" }
        val out = UiConfig.parseBar("""{"v":1,"bar":[$many]}""", actions)!!
        assertEquals(UiConfig.MAX_KEYS, out.size)
        assertNull(out[0].label)
        assertNull(out[0].tone)
        assertEquals("#A1B2C3", UiConfig.parseBar("""{"v":1,"bar":[{"action":"zone","tone":"#A1B2C3"}]}""", actions)!![0].tone)
    }
}
