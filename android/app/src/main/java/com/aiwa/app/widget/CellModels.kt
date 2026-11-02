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
            status != null && !status.githubToken -> CellModel("Connecter GitHub", "red")          // right after Claude, on the same button
            agentNeeds -> CellModel(if (status?.lastSend?.startsWith("ÉCHEC") == true) "Envoi échoué : touche pour voir" else "Il a quelque chose à dire", "red", on = true)
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
        val drawing = status?.diagramOn == true
        out["diagram"] = CellModel(if (drawing) "Schéma actif" else "Schéma", if (drawing) "green" else "grey", on = drawing)
        out["scope"] = CellModel(FilesScope.label(context, status?.repo) + " ▾", if (status?.githubToken == false) "grey" else "green")
        for ((kind, label) in listOf("docs" to "Docs", "image" to "Images", "video" to "Vidéos", "app" to "Apps", "page" to "Pages")) {
            val found = (snap.fileCounts[kind] ?: 0) > 0
            out[kind] = CellModel(label, if (found) "green" else "grey", enabled = found)
        }
        out["scenario"] = CellModel("Scénario", "grey")
        out["cast"] = CellModel("Cast TV", "grey")
        out["nearby"] = CellModel("Swipe", "violet", on = VoirSettings.on(context))
        out["link"] = CellModel("Lien", "grey")
        out["qr"] = CellModel("QR code", "grey")
        out["favorites"] = CellModel("Favoris", "grey")
        for ((id, cell) in ChamberActions.cells(snap)) out[id] = CellModel(cell.label, cell.tone, cell.found, cell.on)
        val calls = com.aiwa.app.chamber.ChamberState.rooms
        val talking = calls.any { it.optBoolean("conversing") }
        out["room"] = CellModel(if (calls.isEmpty()) "Chambres" else "Chambres · ${calls.size}", if (talking) "green" else "blue", on = talking)      // the list: one line per person she called
        out["update"] = CellModel("Mise à jour", if (snap.appUpdateReady) "green" else "grey", on = snap.appUpdateReady)
        out["question"] = CellModel("Question", if (status?.ask != null) "red" else "grey", on = status?.ask != null)
        out["settings"] = CellModel("Réglages", "grey")
        out["wallet"] = CellModel("Wallet", "grey")
        // the twelve tiles of the settings (a page of the widget): the groups open their window, the switches show their state
        val accountsOk = status?.claudeLogin == "ok" && status.githubToken
        out["set_accounts"] = CellModel("Connexions", if (accountsOk) "grey" else "red", on = !accountsOk)
        out["set_words"] = CellModel("Les mots", "grey")
        out["set_persona"] = CellModel("Jeu", "grey")
        out["set_me"] = CellModel("Moi", "grey")
        out["set_voice"] = CellModel("Voix", "grey")
        val listen = com.aiwa.app.voice.ListenSettings.enabled(context)
        out["set_ear"] = CellModel(if (listen) "Écoute ✓" else "Écoute", if (listen) "green" else "grey", on = listen)
        out["set_papers"] = CellModel("Papers", "grey")
        out["set_model"] = CellModel("Modèle", "grey")
        val ready = com.aiwa.app.voice.ReadySettings.enabled(context)
        out["set_ready"] = CellModel(if (ready) "Prêt ✓" else "Prêt", if (ready) "green" else "grey", on = ready)
        val push = status?.pushMain ?: true
        out["set_push"] = CellModel(if (push) "Push ✓" else "Push", if (push) "green" else "grey", on = push)
        out["set_bg"] = CellModel(WidgetBackground.label(context).take(10), "grey")
        out["set_health"] = CellModel("État", "grey")
        return out
    }
}
