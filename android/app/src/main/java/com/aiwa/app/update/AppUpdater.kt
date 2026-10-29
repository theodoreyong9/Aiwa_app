package com.aiwa.app.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.APP_RELEASE_API
import com.aiwa.client.isUpToDate
import com.aiwa.client.looksLikeApk
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * The app updates itself the way Android allows: it finds the latest build (the rolling release the CI publishes), downloads it and opens the
 * system installer, where one tap on « Installer » is the person's consent. Android never lets an app install another one silently. The build is
 * signed with the fixed debug key, so it installs over the present one and keeps its data.
 */
object AppUpdater {
    private fun get(url: String, accept: String? = null): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000; readTimeout = 60_000; instanceFollowRedirects = true
            if (accept != null) setRequestProperty("Accept", accept)
        }

    /**
     * The latest build read from github.com's own page of the rolling release (its commit and the address of the APK), NOT from the API: that page is not in the API's limit of 60 questions
     * an hour without a token, which, once used up, kept the update button from ever appearing. Null when the page does not answer (the API is then tried).
     */
    private fun latestFromWeb(): Pair<String, String>? = try {
        val page = get("https://github.com/theodoreyong9/Aiwa_app/releases/tag/android-latest").inputStream.bufferedReader().use { it.readText() }
        val sha = Regex("/commit/([0-9a-f]{40})").find(page)?.groupValues?.get(1)
        // GitHub no longer writes the list of files into this page (it loads it apart), so the link to the APK is no longer looked for in it: the address of the rolling release never changes,
        // and what proves that the release exists is its page and the commit it points to. (Looking for the link made this return null every time, and the phone fell back on the API and its limit.)
        if (sha == null) null
        else sha to "https://github.com/theodoreyong9/Aiwa_app/releases/download/android-latest/Aiwa_app.apk"
    } catch (e: Exception) { null }

    fun installedVersion(app: Context): String? = try { app.packageManager.getPackageInfo(app.packageName, 0).versionName } catch (e: Exception) { null }

    /** The installer for a downloaded build. INSTALL_PACKAGE, not VIEW: see below. */
    fun installIntent(app: Context, file: File): Intent {
        val uri = FileProvider.getUriForFile(app, "${app.packageName}.updates", file)
        return Intent(Intent.ACTION_INSTALL_PACKAGE).setDataAndType(uri, "application/vnd.android.package-archive")
            .putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }

    /** The downloaded build that is not the installed one (named Aiwa_app_<commit>.apk), or null. No network. */
    fun readyFile(app: Context): File? {
        val installed = installedVersion(app)?.substringAfterLast('.') ?: return null
        return File(app.cacheDir, "update").listFiles()
            ?.firstOrNull { it.name.matches(Regex("Aiwa_app_[0-9a-f]{7}\\.apk")) && it.length() > 1_000_000 && it.name.removePrefix("Aiwa_app_").removeSuffix(".apk") != installed }
    }

    /**
     * In the background, without a word: when a newer build exists it is downloaded (once per build) and returned, ready for the installer.
     * Null when the app is up to date or when anything fails (the next round tries again). The permission to install is asked at the tap, not here.
     */
    fun prepareQuietly(app: Context): File? = try {
        // A conditional request (the ETag of the last answer): GitHub answers 304 when nothing changed, which does not count in its limit of requests, so this can be asked every few minutes.
        val prefs = app.getSharedPreferences("aiwa_update", Context.MODE_PRIVATE)
        val web = latestFromWeb()
        val sha: String
        val apkUrl: String
        if (web != null) {
            sha = web.first; apkUrl = web.second
        } else {
            val connection = get(APP_RELEASE_API, "application/vnd.github+json")
            prefs.getString("etag", null)?.let { if (prefs.getString("sha", null) != null) connection.setRequestProperty("If-None-Match", it) }
            if (connection.responseCode == 304) {
                sha = prefs.getString("sha", null) ?: error("no kept release")
                apkUrl = prefs.getString("url", null) ?: error("no kept release")
            } else {
                val release = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                sha = release.getString("target_commitish")
                apkUrl = release.getJSONArray("assets").getJSONObject(0).getString("browser_download_url")
                prefs.edit().putString("etag", connection.getHeaderField("ETag")).putString("sha", sha).putString("url", apkUrl).apply()
            }
        }
        if (isUpToDate(installedVersion(app), sha)) null
        else {
            val dir = File(app.cacheDir, "update").apply { mkdirs() }
            val target = File(dir, "Aiwa_app_${sha.take(7)}.apk")
            if (!target.exists()) {
                dir.listFiles()?.forEach { it.delete() }
                val part = File(dir, "download.part")
                get(apkUrl).inputStream.use { input -> part.outputStream().use { input.copyTo(it) } }
                val head = part.inputStream().use { st -> ByteArray(2).also { st.read(it) } }
                if (!looksLikeApk(head, part.length())) { part.delete(); null } else { part.renameTo(target); target }
            } else target
        }
    } catch (e: Exception) { null }

    /** Looks for the latest build, downloads it and opens the installer; says each step with a toast. */
    fun update(context: Context) {
        val app = context.applicationContext
        CoroutineScope(Dispatchers.Main).launch {
            try {
                toastOnMain(app, "Recherche de la dernière version d'Aiwa…")
                val (sha, apkUrl) = withContext(Dispatchers.IO) {
                    latestFromWeb() ?: run {
                    val release = JSONObject(get(APP_RELEASE_API, "application/vnd.github+json").inputStream.bufferedReader().use { it.readText() })
                    val asset = release.getJSONArray("assets").getJSONObject(0)
                    release.getString("target_commitish") to asset.getString("browser_download_url")
                    }
                }
                if (isUpToDate(installedVersion(app), sha)) {
                    toastOnMain(app, "Aiwa est déjà à jour (${installedVersion(app)}).")
                    return@launch
                }
                if (!app.packageManager.canRequestPackageInstalls()) {
                    // Asked once: the setting where Aiwa may install apps. The person comes back and presses the entry again.
                    toastOnMain(app, "Autorise Aiwa à installer des applications, puis reviens toucher « Mise à jour prête » sur le widget.")
                    app.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${app.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    return@launch
                }
                toastOnMain(app, "Téléchargement de la nouvelle version (environ 30 Mo)…")
                val file = withContext(Dispatchers.IO) {
                    val dir = File(app.cacheDir, "update").apply { deleteRecursively(); mkdirs() }
                    val target = File(dir, "Aiwa_app.apk")
                    val connection = get(apkUrl)
                    connection.inputStream.use { input -> target.outputStream().use { input.copyTo(it) } }
                    val head = target.inputStream().use { s -> ByteArray(2).also { s.read(it) } }
                    check(looksLikeApk(head, target.length())) { "le fichier téléchargé n'est pas un APK" }
                    target
                }
                // INSTALL_PACKAGE, not VIEW: only the system's installer answers it. A plain VIEW of a file also matches the applications that take any file
                // (Termux offers to « save the file in ~/downloads »), which is not an installation.
                app.startActivity(installIntent(app, file))
            } catch (e: Exception) {
                toastOnMain(app, "Mise à jour impossible : ${e.message ?: e.javaClass.simpleName}")
            }
        }
    }
}
