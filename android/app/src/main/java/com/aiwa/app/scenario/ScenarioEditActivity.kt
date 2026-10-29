package com.aiwa.app.scenario

import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.Scenario
import com.aiwa.client.ScenarioWord
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** A scenario made or changed: its name, its launch word, what its double is asked to do, when it speaks and when it keeps quiet, and the special words that mean something only inside it (« mot = ce qu'il fait », one per line). */
class ScenarioEditActivity : FloatActivity() {
    override val title: String get() = if (editing == null) "Nouveau scénario" else "Modifier le scénario"
    private var editing: Scenario? = null
    private lateinit var name: EditText
    private lateinit var word: EditText
    private lateinit var prompt: EditText
    private lateinit var speak: EditText
    private lateinit var words: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        val id = intent.getStringExtra(EXTRA_ID)
        if (id != null) editing = null
        super.onCreate(savedInstanceState)
        if (id != null) CoroutineScope(Dispatchers.Main).launch {
            editing = withContext(Dispatchers.IO) { Aiwa.brain.scenarios()?.firstOrNull { it.id == id } }
            reload()
        }
    }

    private fun field(hint: String, text: String, lines: Int = 1): EditText = EditText(this).apply {
        this.hint = hint; setText(text); setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0"))
        inputType = InputType.TYPE_CLASS_TEXT or (if (lines > 1) InputType.TYPE_TEXT_FLAG_MULTI_LINE else 0)
        if (lines > 1) { minLines = lines; gravity = android.view.Gravity.TOP }
        add(this)
    }

    override fun fill() {
        val sc = editing
        name = field("Nom (par exemple Entretien)", sc?.name.orEmpty())
        word = field("Mot de lancement (quatre lettres au moins : « scénario entretien »)", sc?.word.orEmpty())
        prompt = field("Ce que son double fait", sc?.prompt.orEmpty(), 4)
        speak = field("Quand il parle à voix haute, quand il se tait", sc?.speak.orEmpty(), 2)
        words = field("Mots spéciaux : « mot = ce qu'il fait », un par ligne", sc?.words?.joinToString("\n") { "${it.word} = ${it.does}" }.orEmpty(), 3)
        entry("Enregistrer") { save() }
        entry("Annuler") { finish() }
    }

    private fun save() {
        val list = words.text.toString().lines().mapNotNull { line ->
            val parts = line.split('=', limit = 2)
            if (parts.size == 2 && parts[0].isNotBlank() && parts[1].isNotBlank()) ScenarioWord(parts[0].trim(), parts[1].trim()) else null
        }
        val sc = Scenario(editing?.id.orEmpty(), name.text.toString().trim(), word.text.toString().trim(), editing?.kind ?: "double", prompt.text.toString().trim(), speak.text.toString().trim(), list)
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.scenarioSave(sc) }
            if (out.ok) finish() else toastOnMain(applicationContext, out.error ?: "Scénario refusé.")
        }
    }

    companion object { const val EXTRA_ID = "id" }
}
