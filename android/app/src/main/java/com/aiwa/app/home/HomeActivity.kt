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
        startActivity(ProfileActivity.homeIntent(this).addFlags(Intent.FLAG_ACTIVITY_NO_ANIMATION))
        finish()
    }
}
