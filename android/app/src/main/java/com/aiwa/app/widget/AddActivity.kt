package com.aiwa.app.widget

import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.util.Base64
import androidx.activity.result.contract.ActivityResultContracts
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.clipboardText
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Largest file the paperclip takes (the brain refuses more too). */
private const val ATTACH_MAX_BYTES = 12 * 1024 * 1024

/**
 * The « Ajouter » of the widget: a file that goes with the next message (a document, a photo, a video, a sound), the files already joined (each can be taken back), and a session of Claude's
 * that already exists (its link or its branch, copied), to be talked to from here.
 */
class AddActivity : FloatActivity() {
    override val title = "Ajouter"
    private var joined: List<String> = emptyList()

    private val picker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri == null) finish() else attach(uri) }
    private var types: Array<String> = arrayOf("*/*")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        CoroutineScope(Dispatchers.Main).launch {
            joined = withContext(Dispatchers.IO) { Aiwa.brain.status()?.attachmentFiles ?: emptyList() }
            reload()
        }
    }

    override fun fill() {
        joined.forEachIndexed { i, name ->
            entry("✕  $name", "part avec le prochain message : toucher pour le retirer") {
                val app = applicationContext
                CoroutineScope(Dispatchers.Main).launch {
                    val ok = withContext(Dispatchers.IO) { Aiwa.brain.attachRemove(i).ok }
                    toastOnMain(app, if (ok) "« $name » retiré" else "Impossible de le retirer")
                    withContext(Dispatchers.IO) { BrainSync.refresh() }
                    AiwaWidget.render(app, force = true)
                    finish()
                }
            }
        }
        entry("Document", "un fichier joint au prochain message") { types = arrayOf("*/*"); picker.launch(types) }
        entry("Média", "photo, vidéo ou son, joint au prochain message") { types = arrayOf("image/*", "video/*", "audio/*"); picker.launch(types) }
        entry("Une session qui existe déjà", "copie son lien (claude.ai/code/session_…) ou le nom de sa branche, puis touche ici") { addSession() }
    }

    private fun addSession() {
        val text = clipboardText(this)?.trim().orEmpty()
        if (text.isEmpty()) { toastOnMain(this, "Copie d'abord le lien de la session (claude.ai/code/session_…) ou le nom de sa branche."); return }
        val app = applicationContext
        CoroutineScope(Dispatchers.Main).launch {
            toastOnMain(app, "Je cherche la session…")
            val out = withContext(Dispatchers.IO) { ensureBrain(app); Aiwa.brain.addSession(text) }
            toastOnMain(app, if (out.ok) "Session ajoutée : elle est celle en cours." else (out.error ?: "Session introuvable."))
            withContext(Dispatchers.IO) { BrainSync.refresh() }
            AiwaWidget.render(app, force = true)
            finish()
        }
    }

    private fun attach(uri: Uri) {
        val app = applicationContext
        CoroutineScope(Dispatchers.Main).launch {
            val message = withContext(Dispatchers.IO) {
                try {
                    val name = app.contentResolver.query(uri, null, null, null, null)?.use { c ->
                        val i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        if (i >= 0 && c.moveToFirst()) c.getString(i) else null
                    } ?: "fichier"
                    val bytes = app.contentResolver.openInputStream(uri)?.use { readCapped(it, ATTACH_MAX_BYTES + 1) } ?: ByteArray(0)
                    if (bytes.size > ATTACH_MAX_BYTES) "Fichier trop gros (maximum ${ATTACH_MAX_BYTES / 1048576} Mo)."
                    else {
                        ensureBrain(app)
                        val out = Aiwa.brain.attach(name, Base64.encodeToString(bytes, Base64.NO_WRAP))
                        if (out.ok) "« $name » est joint (${out.json.optInt("count")} en attente) : il part avec ton prochain message." else (out.error ?: "Impossible de joindre ce fichier.")
                    }
                } catch (e: Exception) {
                    e.message ?: "Impossible de joindre ce fichier."
                }
            }
            toastOnMain(app, message)
            withContext(Dispatchers.IO) { BrainSync.refresh() }
            AiwaWidget.render(app, force = true)
            finish()
        }
    }
}

/** Up to `max` bytes of the stream (readNBytes needs a newer Android than the minimum supported). */
private fun readCapped(input: java.io.InputStream, max: Int): ByteArray {
    val out = java.io.ByteArrayOutputStream()
    val buf = ByteArray(64 * 1024)
    while (out.size() < max) {
        val n = input.read(buf, 0, minOf(buf.size, max - out.size()))
        if (n < 0) break
        out.write(buf, 0, n)
    }
    return out.toByteArray()
}
