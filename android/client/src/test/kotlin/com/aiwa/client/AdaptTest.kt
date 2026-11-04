package com.aiwa.client

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AdaptTest {
    private val host = JSONObject("""{"adaptable":true,"zones":{"titre":{"modifiable":["texte","couleur"]},"intro":{"modifiable":["texte","visible"]},"offres":{"modifiable":["ordre"]}}}""")
    private fun visitor(json: String) = JSONObject(json)

    @Test fun `a match changes the zone the rule names`() {
        val rules = JSONObject("""{"regles":[{"si":{"traits.couleurs":{"contient":"Rouge"}},"alors":[{"zone":"titre","couleur":"{traits.couleurs.0}"}]}]}""")
        val ops = Adapt.plan(host, rules, visitor("""{"traits":{"couleurs":["rouge","noir"]}}"""))
        assertEquals(1, ops.length())
        assertEquals("titre", ops.getJSONObject(0).getString("zone"))
        assertEquals("#e11d48", ops.getJSONObject(0).getString("couleur"))
        assertEquals(0, Adapt.plan(host, rules, visitor("""{"traits":{"couleurs":["bleu"]}}""")).length())
    }

    @Test fun `a page that is not adaptable, or a change its zone does not allow, gives nothing`() {
        val rules = JSONObject("""{"regles":[{"si":{},"alors":[{"zone":"titre","fond":"red"},{"zone":"inconnue","texte":"x"},{"zone":"intro","couleur":"red"}]}]}""")
        assertEquals(0, Adapt.plan(host, rules, visitor("{}")).length())
        assertEquals(0, Adapt.plan(JSONObject("""{"adaptable":false,"zones":{"titre":{"modifiable":["fond"]}}}"""), rules, visitor("{}")).length())
    }

    @Test fun `the host decides how the words of the visitor enter, and an empty place drops the change`() {
        val rules = JSONObject("""{"regles":[{"si":{"traits.themes":{"parmi":["video","film"]}},"alors":[{"zone":"titre","texte":"Pour {traits.themes.0}"},{"zone":"intro","texte":"{traits.lieu}"}]}]}""")
        val ops = Adapt.plan(host, rules, visitor("""{"traits":{"themes":["Vidéo"]}}"""))
        assertEquals("Pour Vidéo", ops.getJSONObject(0).getString("texte"))
        assertEquals(1, ops.length())      // no place: the second change is dropped, never half written
    }

    @Test fun `the description is a source too`() {
        val rules = JSONObject("""{"regles":[{"si":{"description":{"contient":"vidéaste"}},"alors":[{"zone":"intro","texte":"Salut un collègue : {description}"}]}]}""")
        val ops = Adapt.plan(host, rules, visitor("""{"description":"Je suis vidéaste à Lyon"}"""))
        assertEquals("Salut un collègue : Je suis vidéaste à Lyon", ops.getJSONObject(0).getString("texte"))
        assertEquals(0, Adapt.plan(host, rules, visitor("""{"traits":{}}""")).length())      // the visitor lets nothing of it be read
    }

    @Test fun `conditions combine and the last rule wins`() {
        val rules = JSONObject("""{"regles":[
            {"si":{"et":[{"traits.langues":{"contient":"en"}},{"non":{"traits.mode":{"egal":"clair"}}}]},"alors":[{"zone":"titre","texte":"Hello"}]},
            {"si":{"ou":[{"traits.roles":{"absent":false}}]},"alors":[{"zone":"titre","texte":"Bonjour"}]}]}""")
        assertEquals("Hello", Adapt.plan(host, rules, visitor("""{"traits":{"langues":["en"],"mode":"sombre"}}""")).getJSONObject(0).getString("texte"))
        assertEquals("Bonjour", Adapt.plan(host, rules, visitor("""{"traits":{"langues":["en"],"roles":["createur"]}}""")).getJSONObject(0).getString("texte"))
        assertEquals(0, Adapt.plan(host, rules, visitor("""{"traits":{"langues":["en"],"mode":"clair"}}""")).length())
    }

    @Test fun `nothing that looks like markup or a bad colour gets in, and the script carries data only`() {
        val rules = JSONObject("""{"regles":[{"si":{},"alors":[{"zone":"titre","texte":"<img src=x onerror=1>{traits.themes.0}","couleur":"url(javascript:1)"}]}]}""")
        val ops = Adapt.plan(host, rules, visitor("""{"traits":{"themes":["</script><b>"]}}"""))
        val text = ops.getJSONObject(0).getString("texte")
        assertFalse(text.contains('<') || text.contains('>'))
        assertFalse(ops.getJSONObject(0).has("couleur"))
        val script = Adapt.script(ops)
        assertFalse(script.contains("</"))
        assertTrue(script.startsWith("(function(o)"))
    }

    @Test fun `the order of the items and a variant are allowed only where the zone says so`() {
        val rules = JSONObject("""{"regles":[{"si":{},"alors":[{"zone":"offres","ordre":["video","photo"]},{"zone":"titre","ordre":["x"]}]}]}""")
        val ops = Adapt.plan(host, rules, visitor("{}"))
        assertEquals(1, ops.length())
        assertEquals("offres", ops.getJSONObject(0).getString("zone"))
    }
}
