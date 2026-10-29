package com.aiwa.app.question

import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** « Question »: the question a session asked (answer by a choice or by typing, and it goes back to that session), and, under it, a question to put to the super agent, which answers aloud. */
class AskActivity : FloatActivity() {
    override val title = "Question"

    override fun onResume() { super.onResume(); reload() }

    private fun answer(id: String, text: String) {
        if (text.isBlank()) return
        CoroutineScope(Dispatchers.Main).launch {
            toastOnMain(applicationContext, "Réponse envoyée")
            val out = withContext(Dispatchers.IO) { val o = Aiwa.brain.answerAsk(id, text); BrainSync.refresh(); o }
            if (!out.ok) toastOnMain(applicationContext, "Pas parti : ${out.error}")
        }
        finish()
    }

    private fun field(hintText: String) = EditText(this).apply {
        hint = hintText; setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0"))
        inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE; minLines = 2; gravity = android.view.Gravity.TOP
    }

    override fun fill() {
        val ask = Aiwa.state.value.status?.ask
        if (ask != null) {
            note(ask.question, Palette.TEXT)
            for (option in ask.options) entry(option, tone = Palette.CARD) { answer(ask.id, option) }
            val own = field("Ta réponse")
            add(own)
            entry("Envoyer ma réponse") { answer(ask.id, own.text.toString().trim()) }
            if (ask.count > 1) note("${ask.count - 1} autre(s) question(s) attendent.")
        } else note("Aucune session n'attend de réponse.")
        note("Une question au super agent", Palette.GOLD)
        val question = field("Ce que tu veux savoir (où en est Claude, ce que j'ai fait aujourd'hui…)")
        add(question)
        entry("Demander") {
            val text = question.text.toString().trim()
            if (text.isEmpty()) return@entry
            CoroutineScope(Dispatchers.IO).launch { Aiwa.brain.agentAsk(text) }
            toastOnMain(this, "Le super agent répond…")
            finish()
        }
    }
}
