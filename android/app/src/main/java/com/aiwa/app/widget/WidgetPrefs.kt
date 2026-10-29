package com.aiwa.app.widget

import android.content.Context
import com.aiwa.app.R
import com.aiwa.app.common.Prefs

/** The page of the widget that is open. */
object WidgetTab {
    val PAGES = listOf("build", "files", "tools", "voir", "chamber")
    fun get(context: Context): String = Prefs(context, "aiwa_widget_tab").string("tab", "build")?.takeIf { it in PAGES } ?: "build"
    fun set(context: Context, tab: String) = Prefs(context, "aiwa_widget_tab").put("tab", tab)
}

/** The photo behind the widget: one of a few (free of rights, from Poly Haven) or none; the default is the city at night. */
object WidgetBackground {
    private const val FILE = "aiwa_widget_bg"
    val CHOICES = listOf(
        "ville" to ("Ville la nuit" to R.drawable.fw_bg_ville), "neon" to ("Néons" to R.drawable.fw_bg_neon), "desert" to ("Ciel étoilé" to R.drawable.fw_bg_desert),
        "atelier" to ("Atelier" to R.drawable.fw_bg_atelier), "none" to ("Aucune" to 0),
    )
    fun key(context: Context): String = Prefs(context, FILE).string("bg", "ville") ?: "ville"
    fun res(context: Context): Int = CHOICES.firstOrNull { it.first == key(context) }?.second?.second ?: 0
    fun label(context: Context): String = CHOICES.firstOrNull { it.first == key(context) }?.second?.first ?: "Aucune"

    /** The next photo of the list. */
    fun next(context: Context) {
        val i = CHOICES.indexOfFirst { it.first == key(context) }
        Prefs(context, FILE).put("bg", CHOICES[(i + 1) % CHOICES.size].first)
        AiwaWidget.render(context, force = true)
    }
}

/** What the Files page looks at: every repository (« Tous »), or one. Without a choice it follows the repository in use. */
object FilesScope {
    const val ALL = "all"
    private fun prefs(context: Context) = Prefs(context, "aiwa_files_scope")

    /** The repository chosen, ALL, or null while nothing was chosen. */
    fun chosen(context: Context): String? = prefs(context).string("scope")

    fun set(context: Context, scope: String?) { prefs(context).put("scope", scope); AiwaWidget.render(context, force = true) }

    /** The repository to list, or null for every repository. */
    fun repo(context: Context, inUse: String?): String? = when (val c = chosen(context)) { null -> inUse; ALL -> null; else -> c }

    fun label(context: Context, inUse: String?): String = repo(context, inUse)?.substringAfter('/') ?: "Tous"
}
