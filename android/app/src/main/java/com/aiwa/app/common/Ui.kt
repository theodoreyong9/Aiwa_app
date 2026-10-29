package com.aiwa.app.common

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/** The widget has no message area, so what it has to say is a toast. */
fun toastOnMain(context: Context, text: String) {
    val appContext = context.applicationContext
    Handler(Looper.getMainLooper()).post { Toast.makeText(appContext, text, Toast.LENGTH_LONG).show() }
}

/** The text on the clipboard, if any. Only an activity in front may read it (Android hands the clipboard to the app in focus). */
fun clipboardText(context: Context): String? {
    val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager ?: return null
    val clip = manager.primaryClip ?: return null
    if (clip.itemCount == 0) return null
    return clip.getItemAt(0).coerceToText(context)?.toString()
}

fun copyToClipboard(context: Context, text: String) {
    val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager ?: return
    manager.setPrimaryClip(ClipData.newPlainText("Aiwa", text))
}

/** Opens a link in whatever handles it (the browser). */
fun openUrl(context: Context, url: String): Boolean = try {
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    true
} catch (err: ActivityNotFoundException) {
    false
}

/** Shares a text (an address, a title) with the app the person chooses. */
fun shareText(context: Context, title: String, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_SUBJECT, title).putExtra(Intent.EXTRA_TEXT, text)
    context.startActivity(Intent.createChooser(send, title).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

fun Context.dp(value: Int): Int = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

/** The look of Aiwa's own windows: dark blue, light text. */
object Palette {
    val BACK = Color.parseColor("#10132E")
    val CARD = Color.parseColor("#1D2250")
    val TEXT = Color.WHITE
    val DIM = Color.parseColor("#9DB8FF")
    val GOLD = Color.parseColor("#E8C14A")
    val GREEN = Color.parseColor("#52D6A0")
    val RED = Color.parseColor("#F27A75")
}

/** A page of a window: a title, then what the caller adds, inside a scroll. Keeps clear of the system bars. */
class Page(val activity: Activity, title: String) {
    val column = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
    val root: View

    init {
        val pad = activity.dp(18)
        column.setPadding(pad, pad, pad, pad)
        column.addView(TextView(activity).apply { text = title; setTextColor(Palette.TEXT); textSize = 24f; setTypeface(null, android.graphics.Typeface.BOLD) })
        val scroll = ScrollView(activity).apply { setBackgroundColor(Palette.BACK); addView(column) }
        ViewCompat.setOnApplyWindowInsetsListener(scroll) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        root = scroll
    }

    fun note(text: String, color: Int = Palette.DIM): TextView = TextView(activity).apply {
        this.text = text; setTextColor(color); textSize = 15f; setPadding(0, activity.dp(8), 0, activity.dp(4)); setLineSpacing(4f, 1f)
        column.addView(this)
    }

    fun button(text: String, onClick: () -> Unit): Button = Button(activity).apply {
        this.text = text; isAllCaps = false; textSize = 16f
        setOnClickListener { onClick() }
        column.addView(this, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = activity.dp(8) })
    }

    fun space() { column.addView(View(activity), LinearLayout.LayoutParams(1, activity.dp(10))) }
}
