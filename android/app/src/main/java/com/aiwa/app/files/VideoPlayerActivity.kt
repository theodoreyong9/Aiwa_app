package com.aiwa.app.files

import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.MediaController
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.VideoView
import androidx.activity.ComponentActivity
import com.aiwa.app.common.openUrl

/**
 * The player of the videos list: a video plays here, in the app, with the system's controls, instead of being downloaded or handed to the browser.
 * It streams the file from where it lives (the GitHub release of the creation); « Ouvrir ailleurs » in the list stays for the browser, which can download it.
 * The phone's own decoder plays what it can read (H.264 in an mp4, which is what the videos are).
 */
class VideoPlayerActivity : ComponentActivity() {
    private lateinit var video: VideoView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val url = intent.getStringExtra(EXTRA_URL)
        val title = intent.getStringExtra(EXTRA_TITLE) ?: ""
        val root = FrameLayout(this).apply { setBackgroundColor(0xFF000000.toInt()) }
        video = VideoView(this)
        root.addView(video, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT, Gravity.CENTER))
        val spinner = ProgressBar(this)
        root.addView(spinner, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        val message = TextView(this).apply { setTextColor(0xFFFFFFFF.toInt()); textSize = 15f; gravity = Gravity.CENTER; setPadding(48, 48, 48, 48); visibility = View.GONE }
        root.addView(message, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        setContentView(root)

        if (url.isNullOrBlank() || !url.startsWith("https://")) {
            spinner.visibility = View.GONE
            message.text = "Cette vidéo n'a pas d'adresse lisible."
            message.visibility = View.VISIBLE
            return
        }
        val controls = MediaController(this)
        controls.setAnchorView(video)
        video.setMediaController(controls)
        video.setOnPreparedListener { spinner.visibility = View.GONE; video.start() }
        video.setOnErrorListener { _, _, _ ->
            spinner.visibility = View.GONE
            // The file may not be readable by the phone's player, or the network is down: the browser can still download it.
            message.text = "La vidéo $title ne se lit pas ici. Touche pour l'ouvrir dans le navigateur."
            message.visibility = View.VISIBLE
            message.setOnClickListener { openUrl(this, url); finish() }
            true
        }
        video.setVideoURI(Uri.parse(url))
    }

    override fun onPause() {
        if (::video.isInitialized && video.isPlaying) video.pause()
        super.onPause()
    }

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_TITLE = "title"
    }
}
