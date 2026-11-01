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
 * the way to give it orders ([ChamberHost]) and what each button does ([ChamberActions]). Several chambers at once, one per other person; the page lists them all.
 */
object ChamberState {
    @Volatile var rooms: List<JSONObject> = emptyList()

    /** The first chamber (what the widget's buttons and the home show when no profile is named). */
    val status: JSONObject get() = rooms.firstOrNull() ?: JSONObject()

    /** The chamber with the person of this profile: the room named for her (I visit) or my own room where she is the visitor. */
    fun forRepo(repo: String?): JSONObject? = if (repo.isNullOrBlank()) null else rooms.firstOrNull { it.optString("room") == repo || it.optJSONObject("partner")?.optString("repo") == repo }

    /** The chamber where what the person says goes (only one at a time), if any. */
    fun speakRoom(): JSONObject? = rooms.firstOrNull { it.optBoolean("speak") }

    /** What the page says now; a visitor who arrives or leaves is told on the screen. */
    fun update(context: Context, next: List<JSONObject>) {
        val before = rooms.associate { it.optString("room") to it.optJSONObject("partner")?.optString("name") }
        rooms = next
        val first = status
        Aiwa.update {
            it.copy(
                chamberMode = first.optString("mode", "closed").ifBlank { "closed" }, chamberConversing = first.optBoolean("conversing"), chamberEar = first.optBoolean("ear"),
                chamberCreate = first.optBoolean("dangerMe"), chamberCreateThem = first.optBoolean("dangerThem"), chamberPartner = first.optJSONObject("partner")?.optString("name"), chamberRoom = first.optString("room").ifBlank { null },
                chamberRefusedBusy = first.optString("refused") == "busy",
            )
        }
        for (r in next) {
            val key = r.optString("room")
            val after = r.optJSONObject("partner")?.optString("name")
            if (after != before[key] && after != null) toastOnMain(context, "$after est dans la chambre.")
        }
        for ((key, was) in before) if (was != null && next.none { it.optString("room") == key && it.optJSONObject("partner") != null }) toastOnMain(context, "$was a quitté la chambre.")
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
    /** The cells of the chamber with ONE person (her profile): the room, converse, listen, speak, create. */
    fun cellsFor(room: JSONObject?): Map<String, RoomCell> {
        val closed = room == null || room.optString("mode", "closed") == "closed"
        val name = room?.optJSONObject("partner")?.optString("name")
        val conversing = room?.optBoolean("conversing") == true
        val create = room?.optBoolean("dangerMe") == true
        val both = create && room?.optBoolean("dangerThem") == true
        return mapOf(
            "room" to when {
                room?.optString("refused") == "busy" -> RoomCell("Occupé", "red", false)
                room?.optString("refused") == "refus" -> RoomCell("Refusé", "red", false)
                closed -> RoomCell("Entrer", "grey", false)
                conversing -> RoomCell("Avec $name", "green", true)
                name != null -> RoomCell("$name est là", "green", true)
                else -> RoomCell("En attente", "violet", true)
            },
            "roomtalk" to RoomCell(when { conversing -> "Couper"; room?.optBoolean("asking") == true -> "Demande envoyée"; room?.optString("mode") == "visit" -> "Demander"; else -> "Converser" }, if (conversing) "red" else "green", conversing || room?.optBoolean("asking") == true, name != null),
            "roomear" to RoomCell("Écouter", "violet", room?.optBoolean("ear") == true, !closed),
            "roomspeak" to RoomCell("Parler", "violet", room?.optBoolean("speak") == true, !closed),
            "roomcreate" to RoomCell(if (both) "Create actif" else "Create", "red", create, !closed),
        )
    }

    /** The cells of the Chambre page (the first chamber) and what they show now. */
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

    /** The visitor presses « Chambre » on the profile of someone: she enters the room of that person, or leaves it. The other chambers go on. */
    fun visit(context: Context, repo: String?) {
        if (!ProfileView.valid(repo)) { toastOnMain(context, "Pas de profil pour la chambre."); return }
        val here = ChamberState.rooms.firstOrNull { it.optString("room") == repo }
        if (here == null) ChamberHost.send(context, JSONObject().put("cmd", "visit").put("repo", repo))
        else ChamberHost.send(context, JSONObject().put("cmd", "close").put("room", repo))
    }

    /** Listen and speak on the chamber of this profile; speaking takes the voice away from the other chambers (and from the normal super agent): one voice at a time. */
    fun setMode(context: Context, repo: String?, mode: String) {
        val room = ChamberState.forRepo(repo) ?: run { toastOnMain(context, "Entre d'abord dans la chambre."); return }
        val key = room.optString("room")
        val on = !room.optBoolean(mode)
        ChamberHost.send(context, JSONObject().put("cmd", mode).put("room", key).put("on", on))
        if (mode == "speak" && on) toastOnMain(context, "Ce que tu dis va dans cette chambre. Touche encore pour revenir à ton super agent.")
    }

    /** The door: the own room opens (someone can knock, the person accepts or not) or closes. */
    fun door(context: Context, on: Boolean) {
        val here = ProfileSettings.repo(context)
        if (!ProfileView.valid(here)) return
        val open = ChamberState.rooms.any { it.optString("room") == here }
        if (on && !open) ChamberHost.send(context, JSONObject().put("cmd", "open").put("repo", here))
        else if (!on && open) ChamberHost.send(context, JSONObject().put("cmd", "close").put("room", here))
    }

    /** She answers the one who knocked. */
    fun answer(context: Context, room: JSONObject, yes: Boolean) {
        ChamberHost.send(context, JSONObject().put("cmd", if (yes) "accept" else "refuse").put("room", room.optString("room")))
    }

    /** She went to another profile: nobody listens or speaks any more; the chambers themselves go on. */
    fun quiet(context: Context) {
        if (ChamberState.rooms.any { it.optBoolean("ear") || it.optBoolean("speak") }) ChamberHost.send(context, JSONObject().put("cmd", "quiet"))
    }

    /** What the person said while she speaks in a chamber: it goes to that chamber as from her human. False when no chamber has her voice. */
    fun say(context: Context, text: String): Boolean {
        val room = ChamberState.speakRoom() ?: return false
        ChamberHost.send(context, JSONObject().put("cmd", "human").put("room", room.optString("room")).put("text", text))
        return true
    }

    /** What a press of a cell of the chamber does. `activity` is needed for the questions (the description, Create): without one, the person is asked to open Aiwa. */
    fun press(context: Context, id: String, activity: Activity? = context as? Activity, repo: String? = null, onDone: () -> Unit = {}) {
        val status = ChamberState.forRepo(repo) ?: ChamberState.status
        val key = status.optString("room").ifBlank { null }
        val partnered = status.optJSONObject("partner") != null
        when (id) {
            "room" -> {
                val here = ProfileSettings.repo(context)
                if (!ProfileView.valid(here)) { toastOnMain(context, "Pas de profil pour la chambre : choisis d'abord ton dépôt de profil (Réglages)."); return }
                when {
                    ChamberState.rooms.none { it.optString("room") == here } -> ChamberHost.send(context, JSONObject().put("cmd", "open").put("repo", here))
                    else -> ChamberHost.send(context, JSONObject().put("cmd", "close").put("room", here))
                }
            }
            "roomtalk" -> when {
                status.optBoolean("conversing") -> ChamberHost.send(context, JSONObject().put("cmd", "end").put("room", key))
                partnered -> ChamberHost.send(context, JSONObject().put("cmd", "begin").put("room", key))
                else -> toastOnMain(context, "Personne dans la chambre pour l'instant.")
            }
            "roomear" -> if (repo != null) setMode(context, repo, "ear") else ChamberHost.send(context, JSONObject().put("cmd", "ear").put("room", key))
            "roomspeak" -> setMode(context, repo, "speak")
            "roomcreate" -> {
                if (status.optBoolean("dangerMe", false)) { ChamberHost.send(context, JSONObject().put("cmd", "danger").put("on", false).put("room", key)); onDone(); return }
                if (activity == null) { toastOnMain(context, "Ouvre Aiwa pour activer Create."); onDone(); return }
                activity.runOnUiThread {
                    AlertDialog.Builder(activity)
                        .setTitle("Activer Create ?")
                        .setMessage("Si l'autre l'active aussi, vos super agents pourront s'envoyer des messages (à ton super agent) et des propositions (à toi, qui réponds toujours), avec une production publiée en pièce jointe que tu ouvres ou non. Sans cela, ils ne font que parler.")
                        .setPositiveButton("Activer") { _, _ -> ChamberHost.send(context, JSONObject().put("cmd", "danger").put("on", true).put("room", key)) }
                        .setNegativeButton("Annuler", null)
                        .setOnDismissListener { onDone() }
                        .show()
                }
            }
        }
    }
}
