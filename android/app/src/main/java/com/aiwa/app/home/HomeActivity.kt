package com.aiwa.app.home

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity

/**
 * The door of the application (the icon, the widget): the home is the pager of ProfileActivity (her own profile first, then the profiles of her zone), so this only goes there.
 */
class HomeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        askRights()
        startActivity(ProfileActivity.homeIntent(this).addFlags(Intent.FLAG_ACTIVITY_NO_ANIMATION))
        finish()
    }

    /** At the start of the application: the rights Aiwa needs are asked together, one after the other (not more than once every six hours while something is missing). */
    private fun askRights() {
        val missing = !com.aiwa.app.brain.hasTermuxPermission(this) || !android.provider.Settings.canDrawOverlays(this) || !com.aiwa.app.brain.Battery.isExempt(this) ||
            androidx.core.content.ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED ||
            (android.os.Build.VERSION.SDK_INT >= 33 && androidx.core.content.ContextCompat.checkSelfPermission(this, "android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED)
        if (!missing) return
        val prefs = getSharedPreferences("aiwa_setup", MODE_PRIVATE)
        if (System.currentTimeMillis() - prefs.getLong("last_start_ask", 0L) < 6 * 3600 * 1000L) return
        prefs.edit().putLong("last_start_ask", System.currentTimeMillis()).apply()
        startActivity(Intent(this, com.aiwa.app.brain.SetupActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NO_ANIMATION))
    }
}
