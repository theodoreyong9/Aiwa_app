package com.aiwa.app.voice

import android.content.Context
import com.aiwa.app.common.Prefs
import com.aiwa.client.WakeCustoms
import com.aiwa.client.WakeWords
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * The words the person can make her own. « Mes mots » are what SHE says: the ones the small listening model must hear (the call of the super agent, stop, éteins: they are SAID once to the
 * phone, which keeps how the engine hears them) and the ones the phone's recognizer writes down in a conversation (what confirms). « Ses mots » are what Aiwa says: written once.
 */
object Words {
    /** `heard`: the word is said to the phone and kept as the engine hears it (it is listened for by the small model); otherwise it is written. */
    class Slot(val id: String, val label: String, val defaults: List<String>, val help: String, val heard: Boolean)

    val MINE = listOf(
        Slot("call", "Réveil", listOf("mon super agent", "heille wa"), "Ce que tu dis pour réveiller le super agent, écran verrouillé ou non : il répond et prend ta demande.", heard = true),
        Slot("direct", "Envoi direct", listOf("mon agent"), "Ce que tu dis pour que l'agent envoie tout de suite ce que tu lui dictes, sans relecture ni confirmation. (« Mon super agent » discute avec toi et envoie quand tu le lui demandes.)", heard = true),
        Slot("stop", "Stop", listOf("stop claude", "arrête claude"), "Arrête la production en cours et fait oublier à la dernière session le dernier commentaire du super agent.", heard = true),
        Slot("off", "Éteins", listOf("éteins toi"), "Éteint l'écoute permanente et le super agent.", heard = true),
        Slot("confirm", "Validation", listOf("vas-y", "c'est bon", "oui"), "Ce que tu dis pour confirmer ce que le super agent vient de te lire : rien ne part avant.", heard = false),
    )
    val ITS = listOf(
        Slot("listening", "Écoute", listOf("J'écoute."), "Ce que dit Aiwa quand le super agent s'ouvre.", heard = false),
        Slot("asleep", "Veille", listOf("À toute."), "Ce que dit Aiwa quand il se remet en veille (dix secondes sans rien entendre).", heard = false),
        Slot("ready", "Accomplissement", listOf("C'est prêt."), "Ce que dit Aiwa quand une production vient d'arriver.", heard = false),
        Slot("question", "Question", listOf("J'ai une question."), "Ce que dit Aiwa avant de te lire la question d'une session.", heard = false),
    )

    fun slot(id: String): Slot? = (MINE + ITS).firstOrNull { it.id == id }

    private fun prefs(context: Context) = Prefs(context, "aiwa_words")

    // ---- the spellings of a word that is SAID to the phone ----
    fun variants(context: Context, slot: String): List<String> = (prefs(context).string("v_$slot", "") ?: "").split('|').map { it.trim() }.filter { it.isNotEmpty() }
    fun name(context: Context, slot: String): String = prefs(context).string("n_$slot", "") ?: ""
    fun save(context: Context, slot: String, name: String, variants: List<String>) {
        prefs(context).put("v_$slot", variants.joinToString("|")); prefs(context).put("n_$slot", name.trim())
    }
    fun clear(context: Context, slot: String) { prefs(context).remove("v_$slot"); prefs(context).remove("n_$slot") }

    // ---- the words that are WRITTEN ----
    fun written(context: Context, slot: String): List<String> = (prefs(context).string("w_$slot", "") ?: "").split('|').map { it.trim() }.filter { it.isNotEmpty() }
    fun saveWritten(context: Context, slot: String, words: List<String>) { prefs(context).put("w_$slot", words.joinToString("|") { it.trim() }) }
    fun clearWritten(context: Context, slot: String) { prefs(context).remove("w_$slot") }

    /** The spellings of the words chosen by voice, for the small model. */
    fun customs(context: Context) = WakeCustoms(call = variants(context, "call"), stop = variants(context, "stop"), off = variants(context, "off"), direct = variants(context, "direct"))

    /** What Aiwa says for one of its words: the one the person wrote, or the one of origin. */
    fun spoken(context: Context, slot: String): String = written(context, slot).firstOrNull() ?: slot(slot)?.defaults?.first().orEmpty()

    /** The words that confirm, plain, besides the ones of origin (« c'est bien ça »…). */
    fun extraConfirm(context: Context): List<String> = written(context, "confirm").map { WakeWords.plain(it) }.filter { it.isNotEmpty() }

    /** Why a written word cannot be used, or null. */
    fun checkWritten(text: String): String? {
        val plain = WakeWords.plain(text)
        if (plain.isEmpty()) return "Écris un mot."
        if (plain.length < 2) return "« $plain » est trop court."
        return null
    }

    fun pauseOnMedia(context: Context): Boolean = prefs(context).bool("pause_on_media", true)
    fun setPauseOnMedia(context: Context, on: Boolean) { prefs(context).put("pause_on_media", on) }

    /** The words changed: the small model listens for the new ones, and the super agent is told them. */
    fun changed(context: Context) {
        VoiceService.reload(context)
        val app = context.applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            val said = (MINE + ITS).associate { it.label to (written(app, it.id) + variants(app, it.id)) }.filterValues { it.isNotEmpty() }
            if (said.isNotEmpty()) com.aiwa.app.brain.Aiwa.brain.agentVocabulary(said)
        }
    }
}
