package com.aiwa.app.voice

import android.os.Bundle
import androidx.activity.ComponentActivity
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.web.DiagramShow
import com.aiwa.app.web.WebActivity
import com.aiwa.app.widget.AiwaWidget
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** The « Schéma » cell: turns on or off the drawing of diagrams by the super agent while it speaks. When it is on and one has been drawn, a touch opens it again. A no-UI trampoline. */
class DiagramToggleActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = applicationContext
        val status = Aiwa.state.value.status
        val on = status?.diagramOn == true
        if (on && status?.diagramCode?.isNotEmpty() == true && !DiagramShow.visible) {
            startActivity(android.content.Intent(this, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, WebActivity.PAGE_DIAGRAM))
            finish()
            return
        }
        CoroutineScope(Dispatchers.IO).launch {
            val out = Aiwa.brain.setDiagram(!on)
            BrainSync.refresh()
            AiwaWidget.render(app, force = true)
            toastOnMain(app, if (!out.ok) "Schéma : le cerveau n'a pas répondu." else if (!on) "Schémas activés : le super agent en dessine quand ça aide à expliquer." else "Schémas désactivés.")
        }
        finish()
    }
}
