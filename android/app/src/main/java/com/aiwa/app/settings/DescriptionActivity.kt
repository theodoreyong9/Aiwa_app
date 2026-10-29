package com.aiwa.app.settings

import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** « Ma description »: what the super agent says about the person in a chamber (who she is, what she looks for). Only the super agent reads it, and only in the chamber. */
class DescriptionActivity : FloatActivity() {
    override val title = "Ma description"
    private var text: String? = null

    override fun onResume() {
        super.onResume()
        CoroutineScope(Dispatchers.Main).launch { text = withContext(Dispatchers.IO) { Aiwa.brain.chamberNote() }; reload() }
    }

    override fun fill() {
        val current = text
        if (current == null) { note("…"); return }
        note("Ce que ton super agent sait de toi quand il en rencontre un autre dans une chambre : ce que tu fais, ce que tu cherches, ce que tu proposes.")
        val field = EditText(this).apply {
            setText(current); hint = "Je suis… Je cherche… Je propose…"; setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0"))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE; minLines = 5; gravity = android.view.Gravity.TOP
        }
        add(field)
        entry("Enregistrer") {
            val value = field.text.toString().trim()
            CoroutineScope(Dispatchers.Main).launch {
                val out = withContext(Dispatchers.IO) { Aiwa.brain.chamberSetNote(value) }
                toastOnMain(applicationContext, if (out.ok) "Description enregistrée" else "Refusé : ${out.error}")
                if (out.ok) finish()
            }
        }
    }
}
