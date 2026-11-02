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
        // a small copy, to look at in the log of the build
        val small = Bitmap.createScaledBitmap(bitmap, 330, 100, true)
        val flat = Bitmap.createBitmap(330, 100, Bitmap.Config.ARGB_8888).also { android.graphics.Canvas(it).apply { drawColor(0xFF222222.toInt()); drawBitmap(small, 0f, 0f, null) } }
        File(out, "thumb.jpg").outputStream().use { flat.compress(Bitmap.CompressFormat.JPEG, 55, it) }
        // and into the resources of the APK about to be built (the build runs this test first): the preview of the picker is this picture
        val res = File("src/main/res/drawable-nodpi")
        if (res.isDirectory) File(res, "widget1_preview.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
}
