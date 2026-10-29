package com.aiwa.app.voice
import android.content.Context
import java.io.File
import java.io.FilterInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.DigestInputStream
import java.security.MessageDigest
import java.util.zip.ZipInputStream

/**
 * The small French speech model the wake-word listening runs on the phone (Vosk, Apache 2.0): about 41 MB, downloaded once, only when
 * the person turns the always-on listening on, from the model's own site. Nothing the microphone hears ever leaves the phone: that is the
 * reason this is used instead of the phone's recognizer, which would send the ambient sound to its server.
 *
 * HONEST LIMIT: the archive's SHA-256 is not pinned, because the model's official checksum could not be fetched where this was written.
 * What is done instead: the archive comes over https from the official site, its paths are checked (nothing may leave the folder), its size is
 * capped, its layout is checked, and its SHA-256 is kept (see lastHash) so that it can be pinned.
 */
object VoskModelStore {
    const val MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
    private const val MAX_BYTES = 300L * 1024 * 1024
    private const val PREFS = "aiwa_listen"

    fun dir(context: Context): File = File(context.filesDir, "vosk/model")

    fun isReady(context: Context): Boolean = File(dir(context), "am/final.mdl").isFile && File(dir(context), "conf/model.conf").isFile

    /** The SHA-256 of the archive that was downloaded last, to be pinned. */
    fun lastHash(context: Context): String? = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("model_sha256", null)

    /** Downloads and unpacks the model. Null when it is there; otherwise why not. Blocking: call it off the main thread. */
    fun download(context: Context, onProgress: (Int) -> Unit): String? =
        fetch(context, MODEL_URL, dir(context), listOf("am/final.mdl", "conf/model.conf"), "model_sha256", onProgress)

    /** The same, for any Vosk archive (the speaker model too): `markers` are the files that must be in it. */
    internal fun fetch(context: Context, url: String, target: File, markers: List<String>, hashKey: String, onProgress: (Int) -> Unit): String? {
        val root = File(context.filesDir, "vosk")
        val temp = File(root, target.name + ".tmp")
        try {
            temp.deleteRecursively()
            if (!temp.mkdirs()) return "dossier impossible à créer"
            val connection = URL(url).openConnection() as HttpURLConnection
            connection.connectTimeout = 20_000
            connection.readTimeout = 30_000
            if (connection.responseCode != 200) return "le site du modèle répond ${connection.responseCode}"
            val total = connection.contentLengthLong
            val digest = MessageDigest.getInstance("SHA-256")
            var received = 0L
            var shown = -1
            val counted = object : FilterInputStream(connection.inputStream) {
                private fun tick(n: Long) {
                    received += n
                    if (total > 0) {
                        val percent = (received * 100 / total).toInt()
                        if (percent != shown) { shown = percent; onProgress(percent) }
                    }
                }
                override fun read(): Int { val b = super.read(); if (b >= 0) tick(1); return b }
                override fun read(buffer: ByteArray, offset: Int, length: Int): Int { val n = super.read(buffer, offset, length); if (n > 0) tick(n.toLong()); return n }
            }
            val base = temp.canonicalFile
            var written = 0L
            ZipInputStream(DigestInputStream(counted, digest)).use { zip ->
                var entry = zip.nextEntry
                while (entry != null) {
                    // The archive has one folder at its top (vosk-model-small-fr-0.22/): what is inside is what is kept.
                    val name = entry.name.substringAfter('/', "")
                    if (name.isNotEmpty()) {
                        val out = File(temp, name).canonicalFile
                        if (!out.path.startsWith(base.path + File.separator)) return "chemin refusé dans l'archive"
                        if (entry.isDirectory) {
                            out.mkdirs()
                        } else {
                            out.parentFile?.mkdirs()
                            out.outputStream().use { file ->
                                val buffer = ByteArray(64 * 1024)
                                while (true) {
                                    val n = zip.read(buffer)
                                    if (n < 0) break
                                    written += n
                                    if (written > MAX_BYTES) return "archive trop grosse"
                                    file.write(buffer, 0, n)
                                }
                            }
                        }
                    }
                    zip.closeEntry()
                    entry = zip.nextEntry
                }
            }
            if (markers.any { !File(temp, it).isFile }) return "l'archive n'a pas la forme d'un modèle Vosk"
            val hash = digest.digest().joinToString("") { "%02x".format(it) }
            target.deleteRecursively()
            target.parentFile?.mkdirs()
            if (!temp.renameTo(target)) return "modèle impossible à placer"
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(hashKey, hash).apply()
            return null
        } catch (err: Exception) {
            return err.message ?: err.javaClass.simpleName
        } finally {
            temp.deleteRecursively()
        }
    }
}

/** The small speaker model of Vosk (about 13 MB, Apache 2.0): it turns a voice into 128 numbers that can be compared. Downloaded once, only when « seulement ma voix » is turned on. */
object SpeakerModelStore {
    const val URL = "https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip"
    fun dir(context: Context): File = File(context.filesDir, "vosk/spk")
    fun isReady(context: Context): Boolean = File(dir(context), "final.ext.raw").isFile && File(dir(context), "mfcc.conf").isFile
    fun download(context: Context, onProgress: (Int) -> Unit): String? =
        VoskModelStore.fetch(context, URL, dir(context), listOf("final.ext.raw", "mfcc.conf"), "spk_sha256", onProgress)
}
