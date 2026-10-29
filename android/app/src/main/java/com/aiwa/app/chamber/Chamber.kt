package com.aiwa.app.chamber

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.Snapshot
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.home.ProfileSettings
import com.aiwa.app.home.ProfileView
import com.aiwa.app.widget.AiwaWidget
import org.json.JSONObject

/**
 * The chamber: a room where the super agent of the visited and the one of the visitor meet. The connection between the two phones lives in a small page of the web app (web/src/chambre.js, a
 * view without a screen held by ChamberService), the words of the agents are made by the brain (chamber.py); here are the buttons' side: what the page says is going on ([ChamberState]),
 * the way to give it orders ([ChamberHost]) and what each button does ([ChamberActions]). One chamber at a time.
 */
object ChamberState {
    @Volatile var status: JSONObject = JSONObject()

    /** What the page says now; a visitor who arrives or leaves is told on the screen. */
    fun update(context: Context, next: JSONObject) {
        val before = status.optJSONObject("partner")?.optString("name")
        val after = next.optJSONObject("partner")?.optString("name")
        status = next
        Aiwa.update {
            it.copy(
                chamberMode = next.optString("mode", "closed").ifBlank { "closed" }, chamberConversing = next.optBoolean("conversing"), chamberEar = next.optBoolean("ear"),
                chamberCreate = next.optBoolean("dangerMe"), chamberCreateThem = next.optBoolean("dangerThem"), chamberPartner = after, chamberRoom = next.optString("room").ifBlank { null },
                chamberRefusedBusy = next.optString("refused") == "busy",
            )
        }
        if (after != before) {
            if (after != null) toastOnMain(context, "$after est dans la chambre.")
            else if (before != null) toastOnMain(context, "$before a quitté la chambre.")
        }
        AiwaWidget.render(context)
    }
}

object ChamberHost {
    /** The service that holds the connection (set while it runs); the orders wait here until it does. */
    @Volatile var runner: ((JSONObject) -> Unit)? = null
    private val waiting = ArrayList<JSONObject>()

    /** An order for the chamber. The connection is held by a service of the phone, so it goes on with the application closed and the screen off; the first order starts it. */
    fun send(context: Context, cmd: JSONObject) {
        val run = runner
        if (run != null) { run(cmd); return }
        synchronized(waiting) { waiting.add(cmd) }
        ContextCompat.startForegroundService(context.applicationContext, Intent(context.applicationContext, ChamberService::class.java))
    }

    fun drain(): List<JSONObject> = synchronized(waiting) { val out = ArrayList(waiting); waiting.clear(); out }
}

/** What a cell of the chamber page shows: its words, its tone, whether it is on, whether it answers a tap. */
class RoomCell(val label: String, val tone: String, val on: Boolean, val found: Boolean = true)

object ChamberActions {
    /** The cells of the Chambre page and what they show now. */
    fun cells(snap: Snapshot): Map<String, RoomCell> {
        val name = snap.chamberPartner
        val closed = snap.chamberMode == "closed"
        val both = snap.chamberCreate && snap.chamberCreateThem
        return mapOf(
            "room" to when {
                snap.chamberRefusedBusy -> RoomCell("Occupé", "red", false)
                closed -> RoomCell("Chambre", "grey", false)
                snap.chamberConversing -> RoomCell("Avec $name", "green", true)
                name != null -> RoomCell(name, "green", true)
                else -> RoomCell("En attente", "violet", true)
            },
            "roomtalk" to RoomCell(if (snap.chamberConversing) "Couper" else "Converser", if (snap.chamberConversing) "red" else "green", snap.chamberConversing, name != null),
            "roomear" to RoomCell("Écouter", "violet", snap.chamberEar),
            "roomcreate" to RoomCell(if (both) "Create actif" else "Create", "red", snap.chamberCreate),
        )
    }

    /** The visitor presses « Chambre » on the profile of someone: she enters the room of that person (or leaves it). One chamber at a time. */
    fun visit(context: Context, repo: String?) {
        if (!ProfileView.valid(repo)) { toastOnMain(context, "Pas de profil pour la chambre."); return }
        val status = ChamberState.status
        val closed = status.optString("mode", "closed").ifBlank { "closed" } == "closed"
        when {
            closed -> ChamberHost.send(context, JSONObject().put("cmd", "visit").put("repo", repo))
            status.optString("room") == repo -> ChamberHost.send(context, JSONObject().put("cmd", "close"))
            else -> toastOnMain(context, "Tu es déjà dans une autre chambre : ferme-la d'abord.")
        }
    }

    /** What a press of a cell of the chamber does. `activity` is needed for the questions (the description, Create): without one, the person is asked to open Aiwa. */
    fun press(context: Context, id: String, activity: Activity? = context as? Activity, onDone: () -> Unit = {}) {
        val status = ChamberState.status
        val mode = status.optString("mode", "closed").ifBlank { "closed" }
        val partnered = status.optJSONObject("partner") != null
        when (id) {
            "room" -> {
                val here = ProfileSettings.repo(context)
                if (!ProfileView.valid(here)) { toastOnMain(context, "Pas de profil pour la chambre : choisis d'abord ton dépôt de profil (Réglages)."); return }
                when {
                    mode == "closed" -> ChamberHost.send(context, JSONObject().put("cmd", "open").put("repo", here))
                    status.optString("room") == here -> ChamberHost.send(context, JSONObject().put("cmd", "close"))
                    else -> toastOnMain(context, "Tu es déjà dans une autre chambre : ferme-la d'abord.")
                }
            }
            "roomtalk" -> when {
                status.optBoolean("conversing") -> ChamberHost.send(context, JSONObject().put("cmd", "end"))
                partnered -> ChamberHost.send(context, JSONObject().put("cmd", "begin"))
                else -> toastOnMain(context, "Personne dans la chambre pour l'instant.")
            }
            "roomear" -> ChamberHost.send(context, JSONObject().put("cmd", "ear"))
            "roomcreate" -> {
                if (status.optBoolean("dangerMe", false)) { ChamberHost.send(context, JSONObject().put("cmd", "danger").put("on", false)); onDone(); return }
                if (activity == null) { toastOnMain(context, "Ouvre Aiwa pour activer Create."); onDone(); return }
                activity.runOnUiThread {
                    AlertDialog.Builder(activity)
                        .setTitle("Activer Create ?")
                        .setMessage("Si l'autre l'active aussi, vos super agents pourront s'envoyer des messages (à ton super agent) et des propositions (à toi, qui réponds toujours), avec une production publiée en pièce jointe que tu ouvres ou non. Sans cela, ils ne font que parler.")
                        .setPositiveButton("Activer") { _, _ -> ChamberHost.send(context, JSONObject().put("cmd", "danger").put("on", true)) }
                        .setNegativeButton("Annuler", null)
                        .setOnDismissListener { onDone() }
                        .show()
                }
            }
            "roomnote" -> {
                if (activity == null) { toastOnMain(context, "Ouvre Aiwa pour écrire ta description."); onDone(); return }
                Thread {
                    val current = Aiwa.brain.chamberNote()
                    activity.runOnUiThread {
                        val field = android.widget.EditText(activity).apply { setText(current); hint = "Ce que ton super agent peut savoir de toi"; setLines(4); filters = arrayOf(android.text.InputFilter.LengthFilter(400)) }
                        AlertDialog.Builder(activity)
                            .setTitle("Description pour la chambre")
                            .setMessage("Seul le super agent de l'autre la lit, pour mieux t'aider. Il n'est pas autorisé à la répéter, et l'autre personne ne la voit pas.")
                            .setView(field)
                            .setPositiveButton("Enregistrer") { _, _ -> Thread { Aiwa.brain.chamberSetNote(field.text.toString()) }.start() }
                            .setNegativeButton("Annuler", null)
                            .setOnDismissListener { onDone() }
                            .show()
                    }
                }.start()
            }
        }
    }
}
