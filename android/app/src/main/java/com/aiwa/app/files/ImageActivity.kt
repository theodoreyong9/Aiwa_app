package com.aiwa.app.files

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.ComponentActivity
import com.aiwa.app.common.openUrl
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.URL

/** An image production, shown whole on a black screen (a release file would be offered for download by the browser, not shown). */
class ImageActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val url = intent.getStringExtra(EXTRA_URL).orEmpty()
        val root = FrameLayout(this).apply { setBackgroundColor(0xFF000000.toInt()) }
        val image = ImageView(this).apply { scaleType = ImageView.ScaleType.FIT_CENTER }
        root.addView(image, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        val spinner = ProgressBar(this)
        root.addView(spinner, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        val message = TextView(this).apply { setTextColor(0xFFFFFFFF.toInt()); textSize = 15f; gravity = Gravity.CENTER; setPadding(48, 48, 48, 48); visibility = android.view.View.GONE }
        root.addView(message, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        setContentView(root)
        CoroutineScope(Dispatchers.Main).launch {
            val bitmap: Bitmap? = withContext(Dispatchers.IO) {
                try { URL(url).openStream().use { BitmapFactory.decodeStream(it) } } catch (err: Exception) { null }
            }
            spinner.visibility = android.view.View.GONE
            if (bitmap != null) image.setImageBitmap(bitmap)
            else {
                message.text = "L'image ne s'affiche pas ici. Touche pour l'ouvrir dans le navigateur."
                message.visibility = android.view.View.VISIBLE
                message.setOnClickListener { openUrl(this@ImageActivity, url); finish() }
            }
        }
    }

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_TITLE = "title"
    }
}
