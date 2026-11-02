package com.aiwa.app.chamber

import android.content.Intent
import android.os.Handler
import android.os.Looper
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.home.ProfileSettings

/**
 * The chambers, one line per person she called: a conversation, or a call that waits for the call of the other. A touch on a line opens the window of THAT person's chamber
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
        val rooms = ChamberState.rooms
        if (rooms.isEmpty()) note("Tu n'as appelé personne. Pour appeler quelqu'un, va sur son profil et touche Chambre : la chambre s'ouvre quand il t'appellera aussi.")
        for (room in rooms) {
            val partner = room.optJSONObject("partner")
            val name = partner?.optString("name").orEmpty().ifBlank { room.optString("room").substringBefore('/') }
            val state = when {
                room.optBoolean("conversing") -> "en conversation"
                partner != null -> "est là"
                else -> "appel en attente"
            } + if (room.optBoolean("speak")) " · tu lui parles" else if (room.optBoolean("ear")) " · tu écoutes" else ""
            entry(name, state, if (room.optBoolean("conversing")) Palette.GREEN else Palette.CARD) {
                startActivity(Intent(this, ChamberActivity::class.java).putExtra(ChamberActivity.EXTRA_REPO, room.optString("room")))
            }
        }
    }
}
