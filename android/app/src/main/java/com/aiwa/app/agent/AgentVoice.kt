package com.aiwa.app.agent

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.voice.Speaker
import com.aiwa.client.AgentView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * What the super agent has to say reaches the person whoever asked for it: a turn of the conversation, the report button, a message of the other agent in the chamber, a scenario's double.
 * One voice at a time (a lock), and each word is said once (the brain keeps the id of the last one said).
 */
object AgentVoice {
    private val lock = Mutex()
    @Volatile private var spokenId: String? = null

    /** The agent as the brain says it right now (asked again, not the copy of a few seconds ago). */
    suspend fun fresh(): AgentView? = withContext(Dispatchers.IO) { BrainSync.refresh(); Aiwa.state.value.status?.agent }

    /** Says the words of the agent that were not said yet. True when something was said. */
    suspend fun speakSay(context: Context, agent: AgentView? = Aiwa.state.value.status?.agent): Boolean {
        val say = agent?.say ?: return false
        if (say.id == spokenId) return false
        return lock.withLock {
            if (say.id == spokenId) return@withLock false
            spokenId = say.id
            Speaker.resetInterrupt()
            Speaker.speakNaturalStreamed(context, say.text)
            withContext(Dispatchers.IO) { Aiwa.brain.agentSpoken(say.id) }
            true
        }
    }

    /** Whether the agent proposes something that waits for the person's word. */
    fun waiting(agent: AgentView?): Boolean = agent != null && (agent.proposal != null || (agent.command != null && !agent.command!!.auto))

    /** Waits (at most `timeoutMs`) for the answer of the turn that was just asked: the brain says it is no longer busy. */
    suspend fun awaitAnswer(timeoutMs: Long = 120_000L): AgentView? {
        val deadline = System.currentTimeMillis() + timeoutMs
        var last: AgentView? = null
        while (System.currentTimeMillis() < deadline) {
            val agent = fresh()
            last = agent
            if (agent != null && !agent.busy) return agent
            kotlinx.coroutines.delay(700)
        }
        return last
    }
}
