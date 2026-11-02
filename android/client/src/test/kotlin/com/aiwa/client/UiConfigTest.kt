package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class UiConfigTest {
    private val actions = setOf("match", "zone", "wallet")

    @Test
    fun aFileGivesItsKeysInOrderWhateverTheyAre() {
        val out = UiConfig.parseBar("""{"v":1,"bar":[{"action":"zone","icon":"📍","label":"Autour","tone":"violet"},{"action":"wallet"},{"action":"url:https://ok.example/a"}]}""", actions)!!
        assertEquals(listOf("zone", "wallet", "url:https://ok.example/a"), out.map { it.action })
        assertEquals("Autour", out[0].label)
        assertNull(out[1].label)
    }

    @Test
    fun noLimitIsPutOnHerOwnBar() {
        val many = (1..20).joinToString(",") { """{"action":"zone","label":"${"x".repeat(30)}","tone":"#12345G"}""" }
        val out = UiConfig.parseBar("""{"bar":[$many]}""", actions)!!
        assertEquals(20, out.size)
        assertEquals("x".repeat(30), out[0].label)
        assertEquals("#12345G", out[0].tone)
    }

    @Test
    fun aFileThatLeavesNothingChangesNothing() {
        assertNull(UiConfig.parseBar("not json", actions))
        assertNull(UiConfig.parseBar("""{"bar":[]}""", actions))
        assertNull(UiConfig.parseBar("""{"bar":[{"label":"sans action"}]}""", actions))
        assertNull(UiConfig.parseBar(null, actions))
    }
}
