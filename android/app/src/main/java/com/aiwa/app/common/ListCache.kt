package com.aiwa.app.common

import android.content.Context
import java.io.File

/**
 * The last list shown (the files of a repository, the page of a profile), kept on the phone so that a window opens with it at once while the new one is read; the new one replaces it when it comes. It is only a
 * copy to show faster: the system may empty it at any time and nothing is lost (the window then waits for the list as before).
 */
object ListCache {
    private fun file(context: Context, key: String): File = File(File(context.cacheDir, "lists").apply { mkdirs() }, key.hashCode().toUInt().toString(16) + ".txt")

    fun read(context: Context, key: String): String? = try { file(context, key).takeIf { it.isFile }?.readText(Charsets.UTF_8) } catch (err: Exception) { null }

    fun write(context: Context, key: String, text: String) {
        try { file(context, key).writeText(text, Charsets.UTF_8) } catch (err: Exception) { /* a copy only */ }
    }
}
