package com.aiwa.app.home

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.widget.ViewPager2
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.chamber.ChamberActions
import com.aiwa.app.common.dp
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.web.WebActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray

/**
 * A profile (the file `Profile/index.html` of a repository, read from GitHub as it is) in full screen, and the others of the same list one swipe away (the list comes from « Voir »: the people near, the
 * favourites, a link). The page shows ITS design and everything it says; it runs no script of its own. At the bottom, the bar of the VISITOR, which is hers and not the page's: Match (the score for her,
 * made by her own super agent from the two pages: nothing is sent to the other person), Chambre (to enter the room of the person), Café (a direct send of AIWA from her wallet, when she turned it on in
 * the settings and the person gave her signed card in « Voir »), and Widget (the buttons of Aiwa over the page).
 */
class ProfileActivity : ComponentActivity() {
    private val pages = HashMap<Int, WebView>()
    private lateinit var pager: ViewPager2
    private lateinit var urls: List<String>
    private lateinit var pubs: List<String>
    private lateinit var chip: TextView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        urls = try { JSONArray(intent.getStringExtra(EXTRA_URLS) ?: "[]").let { a -> (0 until a.length()).map { a.getString(it) } } } catch (err: Exception) { emptyList() }.filter { ProfileView.valid(it) }.take(60)
        if (urls.isEmpty()) { finish(); return }
        val start = intent.getIntExtra(EXTRA_INDEX, 0).coerceIn(0, urls.size - 1)
        pubs = try { JSONArray(intent.getStringExtra(EXTRA_PUBS) ?: "[]").let { a -> urls.indices.map { a.optString(it) } } } catch (err: Exception) { urls.map { "" } }
        val root = FrameLayout(this).apply { setBackgroundColor(Color.parseColor("#10132E")) }
        pager = ViewPager2(this).apply { offscreenPageLimit = 1; adapter = Pages() }
        root.addView(pager, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        chip = TextView(this).apply {
            setTextColor(Color.WHITE); textSize = 13f; visibility = android.view.View.GONE; setPadding(dp(12), dp(6), dp(12), dp(6))
            background = GradientDrawable().apply { setColor(Color.parseColor("#99000000")); cornerRadius = dp(14).toFloat() }
        }
        root.addView(chip, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP or Gravity.CENTER_HORIZONTAL).apply { topMargin = dp(8) })
        val bar = ProfileBar.build(this, listOf(
            "Match" to { match() },
            "Chambre" to { ChamberActions.visit(this, urls[pager.currentItem]) },
            "☕" to { coffee() },
            "Widget" to { pages[pager.currentItem]?.let { HomeRuntime.openPanel(it) } },
        ))
        root.addView(bar, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
        setContentView(root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        pager.setCurrentItem(start, false)
        pager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() { override fun onPageSelected(position: Int) { chip.visibility = android.view.View.GONE } })
    }

    /** The score of the profile on the screen for the person who looks, made by her own super agent (the brain keeps it): « Pro 72 · Perso 40 ». */
    private fun match() {
        val repo = urls[pager.currentItem]
        chip.text = "Je lis les deux pages…"; chip.visibility = android.view.View.VISIBLE
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.match(repo) }
            if (out.ok) chip.text = "Pro ${out.json.optInt("pro")} · Perso ${out.json.optInt("perso")}"
            else { chip.visibility = android.view.View.GONE; AlertDialog.Builder(this@ProfileActivity).setTitle("Match").setMessage(out.error ?: "Pas de note.").setPositiveButton("Ok", null).show() }
        }
    }

    /** The wallet page with the card « Offrir un café » (two taps to send): the profile says nothing, the key comes from the signed card the person gave out in « Voir ». */
    private fun coffee() {
        val i = pager.currentItem
        val pub = pubs.getOrNull(i).orEmpty()
        when {
            !CoffeeSettings.on(this) -> toastOnMain(this, "Le café est éteint : allume-le dans les Réglages (Profil).")
            pub.isEmpty() -> toastOnMain(this, "Cette personne n'a pas donné sa carte dans « Voir » : pas de café.")
            else -> WebActivity.wallet(this, pub, urls[i])
        }
    }

    override fun onDestroy() { pages.values.forEach { HomeRuntime.release(it); it.destroy() }; pages.clear(); super.onDestroy() }

    private inner class Pages : RecyclerView.Adapter<RecyclerView.ViewHolder>() {
        override fun getItemCount() = urls.size

        @SuppressLint("SetJavaScriptEnabled")
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
            val web = WebView(parent.context).apply {
                layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                setBackgroundColor(Color.parseColor("#10132E"))
                settings.javaScriptEnabled = true       // only for the runtime of the application (evaluateJavascript, not bound by the page's rules): the page's own scripts are forbidden by a policy put first in it
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                settings.mediaPlaybackRequiresUserGesture = false      // the video behind a profile starts by itself (muted)
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = HomeRuntime.openExternal(view.context, request)
                    override fun onPageFinished(view: WebView, url: String?) { HomeRuntime.inject(view) }
                }
            }
            return object : RecyclerView.ViewHolder(web) {}
        }

        override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
            val web = holder.itemView as WebView
            pages[position] = web
            HomeRuntime.attach(web, false) { urls[position] }
            ProfileView.load(web, urls[position])
        }
    }

    companion object {
        const val EXTRA_URLS = "urls"
        const val EXTRA_INDEX = "index"
        const val EXTRA_PUBS = "pubs"
        fun open(context: Context, repos: List<String>, index: Int = 0, pubs: List<String> = emptyList()) =
            context.startActivity(Intent(context, ProfileActivity::class.java).putExtra(EXTRA_URLS, JSONArray(repos).toString()).putExtra(EXTRA_PUBS, JSONArray(pubs).toString()).putExtra(EXTRA_INDEX, index).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
