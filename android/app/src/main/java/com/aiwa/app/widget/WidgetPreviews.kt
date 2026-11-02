package com.aiwa.app.widget

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.os.Build
import com.aiwa.app.common.Prefs

/**
 * The previews of the picker (what the person sees when she chooses a widget for the home screen) are the REAL widgets: the views the widgets are drawn with, as they are now, given to the system
 * (Android 15 and later; older versions show the layout of the preview). The system limits how often it takes them: once per version of the application and at most once every six hours.
 */
object WidgetPreviews {
    private const val SIX_HOURS = 6 * 60 * 60 * 1000L

    fun publish(context: Context) {
        if (Build.VERSION.SDK_INT < 35) return
        val prefs = Prefs(context, "aiwa_widget_previews")
        val version = try { context.packageManager.getPackageInfo(context.packageName, 0).longVersionCode.toString() } catch (err: Exception) { "?" }
        val last = prefs.string("at", "0")?.toLongOrNull() ?: 0L
        if (System.currentTimeMillis() - last < SIX_HOURS && prefs.string("version") == version) return
        try {
            val manager = AppWidgetManager.getInstance(context)
            val first = manager.setWidgetPreview(ComponentName(context, AiwaWidgetProvider::class.java), AppWidgetManager.WIDGET_CATEGORY_HOME_SCREEN, AiwaWidget.previewViews(context))
            val second = manager.setWidgetPreview(ComponentName(context, AiwaWidget2Provider::class.java), AppWidgetManager.WIDGET_CATEGORY_HOME_SCREEN, AiwaWidget2.views(context))
            if (first || second) { prefs.put("version", version); prefs.put("at", System.currentTimeMillis().toString()) }
        } catch (err: Throwable) { /* the system refused (limit): the next start tries again */ }
    }
}
