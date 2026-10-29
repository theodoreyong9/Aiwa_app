package com.aiwa.app.files

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.shareText
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.Production
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** What a tap on a production, on « Partager » or on « Supprimer » does. The files live in releases of the repositories: nothing is stored on the phone but a copy in the cache while it is opened. */
object FileActions {
    private const val MAX_DOWNLOAD = 200L * 1024 * 1024

    /** Opens a production the way its kind wants: a video in the player, a page in the app's own window, an image in a viewer, a document in the app that reads it, an app in the installer. */
    fun open(context: Context, item: Production) {
        val app = context.applicationContext
        when (item.kind) {
            "video" -> context.startActivity(Intent(context, VideoPlayerActivity::class.java).putExtra(VideoPlayerActivity.EXTRA_URL, item.url).putExtra(VideoPlayerActivity.EXTRA_TITLE, item.title).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            "page" -> context.startActivity(Intent(context, PageActivity::class.java).putExtra(PageActivity.EXTRA_REPO, item.repo).putExtra(PageActivity.EXTRA_TAG, item.tag).putExtra(PageActivity.EXTRA_TITLE, item.title).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            "image" -> context.startActivity(Intent(context, ImageActivity::class.java).putExtra(ImageActivity.EXTRA_URL, item.url).putExtra(ImageActivity.EXTRA_TITLE, item.title).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            "app" -> if (item.file.endsWith(".html", true)) {
                context.startActivity(Intent(context, PageActivity::class.java).putExtra(PageActivity.EXTRA_REPO, item.repo).putExtra(PageActivity.EXTRA_TAG, item.tag).putExtra(PageActivity.EXTRA_TITLE, item.title).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            } else if (item.file.endsWith(".apk", true)) install(app, item) else openFile(app, item)
            else -> openFile(app, item)
        }
    }

    /** Downloads the file into the cache and hands it to the app that reads this kind of file; without one, the browser gets the address. */
    private fun openFile(app: Context, item: Production) {
        toastOnMain(app, "Je télécharge « ${item.title} »…")
        CoroutineScope(Dispatchers.Main).launch {
            val file = withContext(Dispatchers.IO) { download(app, item) }
            if (file == null) { if (!openUrl(app, item.url)) toastOnMain(app, "Impossible d'ouvrir « ${item.title} »."); return@launch }
            val uri = FileProvider.getUriForFile(app, "${app.packageName}.updates", file)
            val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(file.extension.lowercase()) ?: "*/*"
            try {
                app.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION))
            } catch (err: Exception) {
                if (!openUrl(app, item.url)) toastOnMain(app, "Aucune application pour ouvrir « ${item.file} ».")
            }
        }
    }

    /** An app delivered as an APK: downloaded, then the system's installer (Android asks the person's consent). */
    private fun install(app: Context, item: Production) {
        if (!app.packageManager.canRequestPackageInstalls()) {
            toastOnMain(app, "Autorise Aiwa à installer des applications, puis touche de nouveau cette app.")
            app.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${app.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        toastOnMain(app, "Je télécharge « ${item.title} »…")
        CoroutineScope(Dispatchers.Main).launch {
            val file = withContext(Dispatchers.IO) { download(app, item) }
            if (file == null) { toastOnMain(app, "Le téléchargement a échoué."); return@launch }
            val uri = FileProvider.getUriForFile(app, "${app.packageName}.updates", file)
            app.startActivity(Intent(Intent.ACTION_INSTALL_PACKAGE).setDataAndType(uri, "application/vnd.android.package-archive").putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION))
        }
    }

    private fun download(app: Context, item: Production): File? = try {
        val dir = File(app.cacheDir, "share").apply { mkdirs() }
        val target = File(dir, item.file.replace(Regex("[^A-Za-z0-9._-]"), "_"))
        val connection = (URL(item.url).openConnection() as HttpURLConnection).apply { connectTimeout = 15_000; readTimeout = 60_000; instanceFollowRedirects = true }
        if (connection.contentLengthLong > MAX_DOWNLOAD) null
        else { connection.inputStream.use { input -> target.outputStream().use { input.copyTo(it) } }; target }
    } catch (err: Exception) { null }

    /** Shares the address of the file (the person chooses with whom). */
    fun share(context: Context, item: Production) {
        val app = context.applicationContext
        CoroutineScope(Dispatchers.Main).launch {
            val info = withContext(Dispatchers.IO) { Aiwa.brain.fileShare(item.repo, item.tag, item.file) }
            if (info == null) toastOnMain(app, "Cette production n'existe plus.") else shareText(app, info.title, info.title + "\n" + info.url)
        }
    }

    /** Deletes the release that holds the file (after the person said yes). The brain says why when it cannot (no GitHub token). */
    fun delete(context: Context, item: Production, done: () -> Unit) {
        val app = context.applicationContext
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.fileDelete(item.repo, item.tag) }
            toastOnMain(app, if (out.ok) "« ${item.title} » est supprimé." else (out.error ?: "Impossible de supprimer."))
            if (out.ok) { FilesWatch.refreshNow(app); done() }
        }
    }
}
