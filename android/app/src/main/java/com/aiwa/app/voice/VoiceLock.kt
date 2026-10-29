package com.aiwa.app.voice

import android.content.Context
import kotlin.math.sqrt

/**
 * « Seulement ma voix » for the wake word: the voice print of the owner (128 numbers made by Vosk's speaker model from a few seconds of her voice) is kept on the phone, and a wake word said
 * by a voice too far from it does not wake the phone. Off by default. Only the wake words (« mon agent », « mon super agent » and the ones chosen) are checked: « stop » and « éteins » always work.
 * HONEST LIMIT: a wake word lasts about a second, which is short for recognising a voice; it is a filter against other voices, never a security.
 */
object VoiceLock {
    private const val PREFS = "aiwa_listen"
    private const val DEFAULT_DISTANCE = 0.55

    fun enabled(context: Context): Boolean = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("only_my_voice", false)
    fun setEnabled(context: Context, on: Boolean) { context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("only_my_voice", on).apply() }

    fun print(context: Context): DoubleArray? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("voice_print", null)?.split(',')?.mapNotNull { it.toDoubleOrNull() }?.toDoubleArray()?.takeIf { it.size >= 64 }

    fun savePrint(context: Context, print: DoubleArray) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("voice_print", print.joinToString(",")).apply()
    }

    fun clear(context: Context) { context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove("voice_print").putBoolean("only_my_voice", false).apply() }

    fun maxDistance(context: Context): Double = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getFloat("voice_max", DEFAULT_DISTANCE.toFloat()).toDouble()

    /** Cosine distance: 0 for the same direction, up to 2; a voice is « the same » under about 0.5. */
    fun distance(a: DoubleArray, b: DoubleArray): Double {
        val n = minOf(a.size, b.size)
        var dot = 0.0; var na = 0.0; var nb = 0.0
        for (i in 0 until n) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i] }
        return if (na == 0.0 || nb == 0.0) 2.0 else 1.0 - dot / (sqrt(na) * sqrt(nb))
    }

    /** The mean of several prints (each normalised first, so that a loud sentence does not weigh more). */
    fun average(prints: List<DoubleArray>): DoubleArray? {
        if (prints.isEmpty()) return null
        val size = prints.minOf { it.size }
        val sum = DoubleArray(size)
        for (p in prints) {
            val norm = sqrt(p.take(size).sumOf { it * it }).takeIf { it > 0 } ?: continue
            for (i in 0 until size) sum[i] += p[i] / norm
        }
        return sum.map { it / prints.size }.toDoubleArray()
    }
}
