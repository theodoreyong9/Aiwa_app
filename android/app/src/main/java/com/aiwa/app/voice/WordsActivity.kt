package com.aiwa.app.voice

import android.content.Intent
import android.text.InputType
import android.widget.EditText
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain

/**
 * « Mes mots » (what the person says: the call, stop, éteins, and what confirms) and « Ses mots » (what Aiwa says: « j'écoute », « à toute », « c'est prêt », « j'ai une question »).
 * A word the small model must hear is SAID to the phone (the enrol window); a word that is only written is typed here.
 */
class WordsActivity : FloatActivity() {
    private val mine: Boolean by lazy { intent.getBooleanExtra(EXTRA_MINE, true) }
    override val title: String get() = if (mine) "Mes mots" else "Ses mots"

    override fun fill() {
        note(if (mine) "Ce que tu dis. Touche un mot pour le changer." else "Ce que dit Aiwa. Touche un mot pour le changer.")
        for (slot in if (mine) Words.MINE else Words.ITS) {
            val current = if (slot.heard) Words.name(this, slot.id).ifEmpty { Words.variants(this, slot.id).firstOrNull() } else Words.written(this, slot.id).firstOrNull()
            val shown = current ?: slot.defaults.first()
            entry(slot.label + " : « $shown »", slot.help, if (current != null) Palette.CARD else Palette.CARD) { change(slot) }
        }
    }

    private fun change(slot: Words.Slot) {
        if (slot.heard) { startActivity(Intent(this, WakeWordEnrollActivity::class.java).putExtra("slot", slot.id)); return }
        val field = EditText(this).apply { setText(Words.written(this@WordsActivity, slot.id).firstOrNull().orEmpty()); hint = slot.defaults.first(); inputType = InputType.TYPE_CLASS_TEXT; setSingleLine() }
        android.app.AlertDialog.Builder(this)
            .setTitle(slot.label).setMessage(slot.help).setView(field)
            .setPositiveButton("Enregistrer") { _, _ ->
                val text = field.text.toString().trim()
                if (text.isEmpty()) { Words.clearWritten(this, slot.id); Words.changed(this); reload(); return@setPositiveButton }
                val problem = Words.checkWritten(text)
                if (problem != null) toastOnMain(this, problem) else { Words.saveWritten(this, slot.id, listOf(text)); Words.changed(this); reload() }
            }
            .setNeutralButton("Remettre") { _, _ -> Words.clearWritten(this, slot.id); Words.changed(this); reload() }
            .setNegativeButton("Annuler", null)
            .show()
    }

    override fun onResume() { super.onResume(); reload() }

    companion object { const val EXTRA_MINE = "mine" }
}
