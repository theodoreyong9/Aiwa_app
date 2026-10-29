package com.aiwa.app.chamber

import android.os.Bundle
import androidx.activity.ComponentActivity
import com.aiwa.app.brain.wakeAiwa

/** A cell of the Chambre page pressed on the widget: a window without a face, because one of them asks a question (Create) and a dialog needs a window. It closes once the question is answered. */
class ChamberPressActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        val id = intent.getStringExtra(EXTRA_ID).orEmpty()
        val asks = id == "roomcreate"
        ChamberActions.press(applicationContext, id, this) { finish() }
        if (!asks) finish()
    }

    companion object { const val EXTRA_ID = "id" }
}
