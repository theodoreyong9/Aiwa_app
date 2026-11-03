package com.aiwa.app.home

import android.graphics.Bitmap
import android.webkit.WebChromeClient

/** The default picture of a video that has not started (a grey disc with a play triangle) is replaced by nothing: the page shows its own colour until the video plays. */
class QuietChrome : WebChromeClient() {
    private val empty: Bitmap by lazy { Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888) }
    override fun getDefaultVideoPoster(): Bitmap = empty
    override fun getVideoLoadingProgressView(): android.view.View? = null
}
