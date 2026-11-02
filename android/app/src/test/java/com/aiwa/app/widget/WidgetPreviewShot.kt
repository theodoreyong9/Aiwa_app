package com.aiwa.app.widget

import android.graphics.Bitmap
import androidx.test.core.app.ApplicationProvider
import java.io.File
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Draws the first widget with its own drawing code (WidgetArt, Android's real Canvas through Robolectric's native graphics) and writes the picture: it is what the picker shows as the preview
 * (res/drawable-nodpi/widget1_preview.png). The build uploads it; nothing here checks a look, it only has to produce the picture.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35])
class WidgetPreviewShot {
    @Test
    fun drawsTheFirstWidget() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val bitmap = AiwaWidget.previewBitmap(context, 990, 300)
        val out = File("build/widget-previews").apply { mkdirs() }
        File(out, "widget1_preview.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        check(File(out, "widget1_preview.png").length() > 5000) { "the picture is empty" }
    }
}
