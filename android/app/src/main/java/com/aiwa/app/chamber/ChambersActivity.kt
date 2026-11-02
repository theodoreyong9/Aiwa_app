package com.aiwa.app.chamber

import android.content.Intent
import android.os.Handler
import android.os.Looper
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.home.ProfileSettings

/**
 * The chambers, one line per person: who the person is in a chamber with (and what stands: a conversation, a wait, a knock), then her own door. A touch on a line opens the window of THAT person's chamber
 * (Entrer / Converser / Écouter / Parler / Create for her alone); nothing general is done from here.
 */
class ChambersActivity : FloatActivity() {
    override val title = "Chambres"
    private val main = Handler(Looper.getMainLooper())
    private var running = true
    private var shown = ""

    override fun onCreate(savedInstanceState: android.os.Bundle?) { super.onCreate(savedInstanceState); loop() }
    override fun onDestroy() { running = false; super.onDestroy() }

    private fun signature() = ChamberState.rooms.joinToString("|") { it.toString() }

    private fun loop() {
        if (!running) return
        if (signature() != shown) { shown = signature(); reload() }
        main.postDelayed({ loop() }, 1500)
    }

    override fun fill() {
        val mine = ProfileSettings.repo(this)
        val own = ChamberState.rooms.firstOrNull { it.optString("room") == mine }
        val others = ChamberState.rooms.filter { it.optString("room") != mine }
        if (others.isEmpty()) note("Tu n'es dans la chambre de personne pour l'instant. Pour en ouvrir une, va sur le profil de la personne et touche Chambre.")
        for (room in others) {
            val partner = room.optJSONObject("partner")
            val name = partner?.optString("name").orEmpty().ifBlank { room.optString("room").substringBefore('/') }
            val state = when {
                room.optBoolean("conversing") -> "en conversation"
                room.optBoolean("asking") -> "demande envoyée, en attente de sa réponse"
                partner != null -> "est là"
                room.optString("refused") == "refus" -> "a refusé"
                else -> "en attente"
            } + if (room.optBoolean("speak")) " · tu lui parles" else if (room.optBoolean("ear")) " · tu écoutes" else ""
            entry(name, state, if (room.optBoolean("conversing")) Palette.GREEN else Palette.CARD) {
                startActivity(Intent(this, ChamberActivity::class.java).putExtra(ChamberActivity.EXTRA_REPO, room.optString("room")))
            }
        }
        val knocking = own?.optBoolean("knock") == true
        val ownPartner = own?.optJSONObject("partner")?.optString("name")
        section("Ta porte")
        entry(
            if (knocking) "${ownPartner ?: "Quelqu'un"} demande à parler" else if (own == null) "Ta porte est fermée" else if (ownPartner != null) "$ownPartner est à ta porte" else "Ta porte est ouverte",
            if (knocking) "touche pour accepter ou refuser" else "les demandes de chambre arrivent ici",
            if (knocking) Palette.GOLD else Palette.CARD,
        ) { startActivity(Intent(this, ChamberActivity::class.java)) }
    }
}
