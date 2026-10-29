package com.aiwa.app.widget

import android.content.Context
import com.aiwa.app.brain.Link
import com.aiwa.app.brain.Snapshot
import com.aiwa.app.brain.hasTermuxPermission
import com.aiwa.app.chamber.ChamberActions
import com.aiwa.app.agent.AgentVoice
import com.aiwa.app.voir.VoirSettings

/** What a button shows: its words, its tone (grey, green, red, orange, violet, blue, yellow), whether it answers a tap, whether it is on. */
class CellModel(val label: String, val tone: String, val enabled: Boolean = true, val on: Boolean = false)

/**
 * The state of every button of Aiwa, by id (the ids of the home runtime, web/home/aiwa-home.js). The widget draws them, and the home page of the application draws the same ones in its
 * slots, with the same words and tones.
 */
object CellModels {
    val KIND_IDS = mapOf("docs" to "docs", "image" to "image", "video" to "video", "app" to "app", "page" to "page")

    fun of(context: Context, snap: Snapshot): Map<String, CellModel> {
        val status = snap.status
        val agent = status?.agent
        val agentNeeds = AgentVoice.waiting(agent) || agent?.say != null
        val needsSetup = !hasTermuxPermission(context)
        val waiting = status?.waiting == true || (status?.silenceMinutes ?: 0) > 0
        val ear = snap.listening && !needsSetup
        val attachments = status?.attachments ?: 0
        val hasSession = snap.sessionId != null || status?.lastSession != null
        val out = LinkedHashMap<String, CellModel>()
        out["agent"] = when {
            snap.link == Link.MISSING -> CellModel("Installation manquante", "red")
            needsSetup -> CellModel("Autoriser Aiwa", "red")
            status?.claudeLogin == "needed" -> CellModel("Connecter Claude", "red")
            agentNeeds -> CellModel("Il a quelque chose à dire", "red", on = true)
            snap.agentOpen -> CellModel("Super agent · à l'écoute", "green", on = true)
            snap.link == Link.DOWN || snap.link == Link.STARTING -> CellModel("Cerveau en route…", "grey")
            else -> CellModel("Super agent", "orange")
        }
        out["claude"] = when {
            waiting -> CellModel("Claude", "red")
            !hasSession && status?.sessionError != null -> CellModel("Session ✗", "red")
            hasSession -> CellModel("Claude", "blue", on = true)
            else -> CellModel("Claude", "grey")
        }
        out["listen"] = CellModel(if (ear) "Écoute active" else "Écoute", if (ear) "green" else "grey", on = ear)
        out["plus"] = CellModel(if (attachments > 0) "$attachments jointe(s)" else "Ajouter", if (attachments > 0) "green" else "grey")
        val single = FilesScope.repo(context, status?.repo) != null
        out["repoview"] = CellModel("Voir le dépôt", "grey", enabled = single)
        out["reposession"] = CellModel("Changer de session", "grey", enabled = single)
        out["scope"] = CellModel(FilesScope.label(context, status?.repo) + " ▾", "green")
        for ((kind, label) in listOf("docs" to "Docs", "image" to "Images", "video" to "Vidéos", "app" to "Apps", "page" to "Pages")) {
            val found = (snap.fileCounts[kind] ?: 0) > 0
            out[kind] = CellModel(label, if (found) "green" else "grey", enabled = found)
        }
        out["scenario"] = CellModel("Scénario", "grey")
        out["cast"] = CellModel("Cast TV", "grey")
        out["nearby"] = CellModel("Zone", "violet", on = VoirSettings.on(context))
        out["link"] = CellModel("Lien", "grey")
        out["qr"] = CellModel("QR code", "grey")
        out["favorites"] = CellModel("Favoris", "grey")
        for ((id, cell) in ChamberActions.cells(snap)) out[id] = CellModel(cell.label, cell.tone, cell.found, cell.on)
        out["update"] = CellModel("Mise à jour", if (snap.appUpdateReady) "green" else "grey", on = snap.appUpdateReady)
        out["question"] = CellModel("Question", if (status?.ask != null) "red" else "grey", on = status?.ask != null)
        out["settings"] = CellModel("Réglages", "grey")
        out["wallet"] = CellModel("Wallet", "grey")
        return out
    }
}
