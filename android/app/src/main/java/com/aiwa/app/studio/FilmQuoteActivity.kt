package com.aiwa.app.studio

import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.files.VideoPlayerActivity
import com.aiwa.app.settings.KeysActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.Locale

/** The quote of a film: each scene with its price (touch one to change what is seen or said, or to remove it), the total, then « Lancer ». Nothing is paid before. Then the film is followed until it is done. */
class FilmQuoteActivity : FloatActivity() {
    override val title = "Devis du film"
    private var job: JSONObject? = null
    private var info: JSONObject? = null
    private var following = false
    private val id: String get() = intent.getStringExtra(EXTRA_JOB).orEmpty()

    private fun dollars(v: Double) = String.format(Locale.FRANCE, "%.2f $", v)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        load()
    }

    private fun load() {
        CoroutineScope(Dispatchers.Main).launch {
            job = withContext(Dispatchers.IO) { Aiwa.brain.filmGet(id) }
            follow()
            reload()
        }
    }

    /** While it is made, and while it is saved in GitHub: the brain is asked every few seconds. */
    private fun follow() {
        val j = job ?: return
        if (following || !(j.optString("state") == "running" || j.optString("saved") == "pending")) return
        following = true
        CoroutineScope(Dispatchers.Main).launch {
            while (!isDestroyed) {
                delay(3000)
                val next = withContext(Dispatchers.IO) { Aiwa.brain.filmGet(id) } ?: continue
                job = next
                if (next.optString("state") == "done" && info == null) info = withContext(Dispatchers.IO) { Aiwa.brain.filmInfo() }
                reload()
                if (next.optString("state") != "running" && next.optString("saved") != "pending") break
            }
            following = false
        }
    }

    private fun edit(index: Int, scene: JSONObject) {
        val situation = EditText(this).apply { setText(scene.optString("situation")); hint = "Ce qu'on voit"; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE; minLines = 2 }
        val says = EditText(this).apply { setText(scene.optString("says")); hint = "Ce que je dis"; inputType = InputType.TYPE_CLASS_TEXT }
        val box = android.widget.LinearLayout(this).apply { orientation = android.widget.LinearLayout.VERTICAL; addView(situation); addView(says) }
        android.app.AlertDialog.Builder(this).setTitle("Scène ${index + 1}").setView(box)
            .setPositiveButton("Appliquer") { _, _ -> change { Aiwa.brain.filmEdit(id, index, situation.text.toString(), says.text.toString()) } }
            .setNeutralButton("Enlever") { _, _ -> change { Aiwa.brain.filmEdit(id, index, null, null, remove = true) } }
            .setNegativeButton("Annuler", null).show()
    }

    private fun change(call: () -> com.aiwa.client.Brain.Outcome) {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { call() }
            if (out.ok) job = out.json else toastOnMain(applicationContext, out.error ?: "refusé")
            reload()
        }
    }

    private fun start() {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.filmStart(id) }
            if (out.ok) { job = out.json; follow() } else toastOnMain(applicationContext, out.error ?: "refusé")
            reload()
        }
    }

    override fun fill() {
        val j = job
        if (j == null) { note("…"); return }
        val scenes = j.optJSONArray("scenes")
        val state = j.optString("state")
        for (i in 0 until (scenes?.length() ?: 0)) {
            val s = scenes!!.getJSONObject(i)
            val says = s.optString("says")
            val line = (if (says.isNotBlank()) "Je dis : « $says » · " else "") + "${s.optInt("seconds")} s · " + (if (s.optBoolean("done")) "déjà fait" else dollars(s.optDouble("price")))
            entry("${i + 1}. ${s.optString("situation")}", line) { if (state == "quoted") edit(i, s) }
        }
        note("Total : ${dollars(j.optDouble("total"))} (estimation, facturée par fal.ai sur ton compte)", Palette.GOLD)
        if (j.optBoolean("over_cap")) { note("Au-dessus de ton plafond : monte-le dans Clés et plafonds, ou enlève des scènes.", Palette.RED); entry("Clés et plafonds") { startActivity(Intent(this, KeysActivity::class.java)) } }
        when (state) {
            "running" -> note("En cours : ${j.optString("step")}…")
            "done" -> {
                note("Terminé ✓", Palette.GREEN)
                entry("Voir le film") { startActivity(Intent(this, VideoPlayerActivity::class.java).putExtra(VideoPlayerActivity.EXTRA_URL, Aiwa.brain.filmAddress(id)).putExtra(VideoPlayerActivity.EXTRA_TITLE, "Film")) }
                when (j.optString("saved")) {
                    "saved" -> note("Sauvegardé dans ton dépôt ✓ (Fichiers, Vidéos)", Palette.GREEN)
                    "pending" -> note("Sauvegarde dans ton dépôt en cours…")
                    else -> {
                        if (j.optString("saved") == "failed") note(j.optString("saved_error"), Palette.RED) else note("Seulement sur ce téléphone pour l'instant.")
                        val where = info
                        if (where?.optString("repo").isNullOrEmpty()) note("Choisis un dépôt (Fichiers) pour le sauvegarder.")
                        else {
                            if (where?.optBoolean("public") == true) note("Le dépôt ${where.optString("repo")} est public : le film sera visible par tous.")
                            entry("Sauvegarder dans ${where?.optString("repo")}") {
                                CoroutineScope(Dispatchers.Main).launch {
                                    val out = withContext(Dispatchers.IO) { Aiwa.brain.filmPublish(id) }
                                    if (!out.ok) toastOnMain(applicationContext, if (out.json.optString("needs") == "github") "Connecte GitHub (Réglages) pour le sauvegarder." else (out.error ?: "refusé"))
                                    job = withContext(Dispatchers.IO) { Aiwa.brain.filmGet(id) }; follow(); reload()
                                }
                            }
                        }
                    }
                }
                if (info == null) CoroutineScope(Dispatchers.Main).launch { info = withContext(Dispatchers.IO) { Aiwa.brain.filmInfo() }; reload() }
            }
            "error" -> { note("Échec : ${j.optString("error")}", Palette.RED); entry("Revoir le devis") { load() } }
            else -> entry("Lancer (${dollars(j.optDouble("total"))})") { if (!j.optBoolean("over_cap")) start() }
        }
    }

    companion object { const val EXTRA_JOB = "job" }
}
