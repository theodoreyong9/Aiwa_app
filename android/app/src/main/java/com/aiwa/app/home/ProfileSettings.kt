package com.aiwa.app.home

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.Prefs
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** The profile: the repository that holds its `Profile/` folder (the phone keeps it too, to show it as the home). The page itself is the work of a session. */
object ProfileSettings {
    private fun prefs(context: Context) = Prefs(context, "aiwa_profile")
    fun repo(context: Context): String? = prefs(context).string("repo") ?: DEFAULT_REPO

    /** Until the person chooses another one, the home is the `Profile/` of the product's own repository: a first opening shows a page, not an empty screen. */
    const val DEFAULT_REPO = "theodoreyong9/Aiwa_app"

    /** Sets the repository of the profile and tells the brain (the sessions are told where the `Profile/` folder goes). Reports in a toast. */
    fun set(context: Context, repo: String) {
        val app = context.applicationContext
        prefs(app).put("repo", repo)
        CoroutineScope(Dispatchers.IO).launch {
            val out = Aiwa.brain.setProfileRepo(repo)
            toastOnMain(app, if (out.ok) "Dépôt du profil : $repo" else "Profil : le cerveau n'a pas pris ce dépôt (${out.error}).")
        }
    }

    /** Asks the brain to read the profile of the repository chosen and says in a toast what lacks of the minimum (or that it is good). */
    fun check(context: Context) {
        val app = context.applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            val json = Aiwa.brain.profileCheck()
            if (json == null) { toastOnMain(app, "Profil : le cerveau ne répond pas."); return@launch }
            val problems = json.optJSONArray("problems")
            toastOnMain(app, when {
                !json.optBoolean("ok") -> json.optString("error").ifBlank { "Profil : pas lisible." }
                problems == null || problems.length() == 0 -> "Ton profil atteint le niveau minimal."
                else -> "Il manque : " + (0 until problems.length()).joinToString(" ") { problems.optString(it) }
            })
        }
    }
}

/** The coffee button on the profiles one visits works when the wallet is connected (its 12 words are kept on this phone): no other switch. */
object CoffeeSettings {
    fun walletConnected(context: Context): Boolean = !com.aiwa.app.web.SecretStore(context).get("phrase").isNullOrEmpty()
}
