package com.aiwa.app.brain

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings
import com.aiwa.app.common.Prefs

/**
 * Without the exemption from the battery's optimisation, Android may stop Aiwa's background service (the widget stops following Claude, the updates and the brain's restarts stop with it).
 * One tap on the settings line shows Android's own question « Autoriser Aiwa à fonctionner en arrière-plan ? ».
 */
object Battery {
    fun isExempt(context: Context): Boolean = context.getSystemService(PowerManager::class.java)?.isIgnoringBatteryOptimizations(context.packageName) ?: true
    fun requestIntent(context: Context): Intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    fun noteAsked(context: Context) { val p = Prefs(context, "aiwa_battery"); p.put("asks", p.int("asks") + 1) }
}
