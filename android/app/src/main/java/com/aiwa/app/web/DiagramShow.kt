package com.aiwa.app.web

import android.content.Context
import android.content.Intent
import com.aiwa.client.Status

/** The diagram of the super agent (Mermaid, drawn by a page of the web app): it opens by itself when a new one arrives and the option is on; once open, the page asks for the text and draws each new one. */
object DiagramShow {
    @Volatile var visible = false
    private var lastId = 0L

    fun maybeOpen(context: Context, status: Status?) {
        if (status == null || !status.diagramOn || status.diagramCode.isEmpty() || status.diagramId == lastId) return
        lastId = status.diagramId
        if (visible) return          // the page on screen draws it by itself
        try {
            context.startActivity(Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, WebActivity.PAGE_DIAGRAM).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP))
        } catch (err: Exception) {
            // refused in the background: the cell « Schéma » of the widget opens the last one
        }
    }
}
