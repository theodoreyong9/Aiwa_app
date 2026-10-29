package com.aiwa.app.files

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.Link
import com.aiwa.app.widget.AiwaWidget
import com.aiwa.app.widget.FilesScope
import com.aiwa.client.Files
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** Reads how many productions there are of each kind in the scope of the Files page (so that the widget shows which kinds have something), now and then. GitHub is asked in the background, never by the widget. */
object FilesWatch {
    @Volatile private var lastAt = 0L
    @Volatile private var lastScope: String? = "?"
    @Volatile private var lastAnnouncedScope: String? = "?"

    /** Called every round of the keep-alive service: the counts are read again every two minutes, or at once when the scope changed. */
    fun tick(context: Context, announcer: com.aiwa.app.brain.KeepAliveService? = null) {
        val snap = Aiwa.state.value
        if (snap.link != Link.UP) return
        val scope = FilesScope.repo(context, snap.status?.repo)
        if (scope == lastScope && System.currentTimeMillis() - lastAt < 120_000L) return
        read(context, scope, announcer)
    }

    fun refreshNow(context: Context) { lastAt = 0L; CoroutineScope(Dispatchers.IO).launch { read(context.applicationContext, FilesScope.repo(context, Aiwa.state.value.status?.repo)) } }

    private fun read(context: Context, scope: String?, announcer: com.aiwa.app.brain.KeepAliveService? = null) {
        lastAt = System.currentTimeMillis()
        lastScope = scope
        val files = Aiwa.brain.files(scope) ?: return
        val counts = Files.KINDS.associateWith { files.items[it]?.size ?: 0 }
        val before = Aiwa.state.value.fileCounts
        // a production that was not there at the last look (and not at the first look of all): said aloud, and left as a notification
        if (before.isNotEmpty() && scope == lastAnnouncedScope && counts.values.sum() > before.values.sum()) {
            files.items.values.flatten().maxByOrNull { it.ts }?.let { announcer?.announceNew(it.title, it.kind) }
        }
        lastAnnouncedScope = scope
        if (counts != before) {
            Aiwa.update { it.copy(fileCounts = counts) }
            AiwaWidget.render(context)
        }
    }
}
