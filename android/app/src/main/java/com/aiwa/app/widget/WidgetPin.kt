package com.aiwa.app.widget

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import com.aiwa.app.common.toastOnMain

/**
 * Putting the widget on the home screen. Android never lets an application place a widget by itself: it can only ASK, and the system shows its own window
 * (« Ajouter le widget à l'écran d'accueil ? ») where one tap on « Ajouter » does it. Some launchers do not take the request: the person is then told the gesture by hand.
 * It is asked once, when the application is first opened and no widget is there; the menu d'Aiwa asks again whenever the person wants.
 */
object WidgetPin {
    private const val HAND_GESTURE = "Ajoute le widget toi-même : appui long sur l'écran d'accueil, puis Widgets, puis Aiwa."

    private fun provider(context: Context) = ComponentName(context, AiwaWidgetProvider::class.java)

    /**
     * Is a widget really on a home screen? The list of ids is not enough: after a reinstall Android may give back the numbers of old widgets that no launcher shows. A launcher that
     * hosts a widget tells it its size (the options of the id); an id nobody hosts has none. (Having been « drawn » does not prove it: updateAll draws for every id, hosted or not.)
     */
    fun hasWidget(context: Context): Boolean = try {
        val manager = AppWidgetManager.getInstance(context)
        manager.getAppWidgetIds(provider(context)).any { id ->
            manager.getAppWidgetInfo(id) != null &&
                manager.getAppWidgetOptions(id).let { it.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0) > 0 || it.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 0) > 0 }
        }
    } catch (err: Exception) { false }

    /** Asks the system to add the widget. Returns false when the launcher cannot be asked (the gesture by hand is then said, if `explain`). */
    fun request(context: Context, explain: Boolean): Boolean {
        val manager = AppWidgetManager.getInstance(context)
        val supported = try { manager.isRequestPinAppWidgetSupported } catch (err: Exception) { false }
        val asked = supported && try { manager.requestPinAppWidget(provider(context), null, null) } catch (err: Exception) { false }
        if (!asked && explain) toastOnMain(context.applicationContext, HAND_GESTURE)
        return asked
    }

    /**
     * Whenever the application is opened and there is no widget: the request is made, every time (the person said no, or closed the window, or reinstalled: it is asked again
     * at the next opening). Only a few minutes between two requests, so that opening and closing the app is not a loop; Android itself may refuse some. NOT « once for ever »
     * nor « once a day »: a flag kept for ever was restored by Android's backup after a reinstall, and a daily limit made the request vanish right after the first opening.
     * The time of the last request is in storage that the backup does not carry (noBackupFilesDir). When the launcher cannot be asked, the gesture by hand is said.
     */
    fun offerOnce(context: Context) {
        if (hasWidget(context)) return
        val file = java.io.File(context.noBackupFilesDir, "widget_pin.txt")
        val parts = try { file.readText().trim().split(' ') } catch (err: Exception) { emptyList() }
        val last = parts.getOrNull(1)?.toLongOrNull() ?: 0L
        val now = System.currentTimeMillis()
        if (now - last < 3 * 60 * 1000L) return
        try { file.writeText("1 $now") } catch (err: Exception) { }
        request(context, explain = true)
    }
}
