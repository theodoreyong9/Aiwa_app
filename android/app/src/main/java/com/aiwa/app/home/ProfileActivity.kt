package com.aiwa.app.home

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ArrayAdapter
import android.widget.FrameLayout
import android.widget.ListView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.widget.ViewPager2
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.voice.ListenSettings
import com.aiwa.app.voice.VoiceService
import com.aiwa.app.widget.WidgetPin
import com.aiwa.app.chamber.ChamberActions
import com.aiwa.app.common.dp
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.voir.FavoriteRepos
import com.aiwa.app.voir.SwipeData
import com.aiwa.app.web.WebActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
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
    private lateinit var pubs: MutableList<String>
    private lateinit var chip: TextView
    private lateinit var bar: ProfileBar.Bar
    private val scores = HashMap<String, String>()      // repository -> « Pro 72 · Perso 41 »

    // « Swipe »: the person is always navigating. Level 0 is her own zone (what this phone saw, the nearest first); each « Swipe » on a profile puts her in the place of that profile (the list IT saw),
    // and the levels left behind are kept so that « Précédent » comes back to them.
    private class Level(val urls: List<String>, val pubs: MutableList<String>, val index: Int)
    private val stack = ArrayList<Level>()
    // The HOME of the application is this same pager: her own profile is the first page (her page, scripts allowed, followed live), the profiles of her zone come after it.
    private var ownFirst = false
    private var ownWatch: ProfileWatch? = null
    private var ownWatched: String? = null
    private lateinit var collector: com.aiwa.app.voir.ZoneCollector
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if (granted) VoiceService.ensureStarted(applicationContext) }
    private var zoneTicker: Runnable? = null
    private var zoneDeck = false            // level 0 is the zone of this phone

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ownFirst = intent.getBooleanExtra(EXTRA_HOME, false)
        zoneDeck = intent.getBooleanExtra(EXTRA_ZONE, false)
        val favoritesDeck = intent.getBooleanExtra(EXTRA_FAVORITES, false)
        if (ownFirst) wakeAiwa(applicationContext)
        val own = ProfileSettings.repo(this)
        urls = when {
            ownFirst -> listOf(own.orEmpty()) + SwipeData.observed(this, 7).filter { ProfileView.valid(it) && !it.equals(own, ignoreCase = true) }
            zoneDeck -> SwipeData.observed(this, 7).filter { ProfileView.valid(it) }
            favoritesDeck -> FavoriteRepos.all(this).filter { ProfileView.valid(it) }
            else -> try { JSONArray(intent.getStringExtra(EXTRA_URLS) ?: "[]").let { a -> (0 until a.length()).map { a.getString(it) } } } catch (err: Exception) { emptyList() }.filter { ProfileView.valid(it) }
        }
        if (urls.isEmpty()) {
            if (zoneDeck) toastOnMain(this, "Aiwa regarde autour de toi : reviens dans un moment, la liste se remplit toute seule.")
            else if (favoritesDeck) toastOnMain(this, "Aucun favori : touche ☆ Favoris sur un profil pour le garder.")
            finish(); return
        }
        val start = if (zoneDeck || favoritesDeck || ownFirst) 0 else intent.getIntExtra(EXTRA_INDEX, 0).coerceIn(0, urls.size - 1)
        pubs = if (zoneDeck || favoritesDeck || ownFirst) urls.map { "" }.toMutableList() else try { JSONArray(intent.getStringExtra(EXTRA_PUBS) ?: "[]").let { a -> urls.indices.map { a.optString(it) }.toMutableList() } } catch (err: Exception) { urls.map { "" }.toMutableList() }
        val root = FrameLayout(this).apply { setBackgroundColor(Color.parseColor("#10132E")) }
        pager = ViewPager2(this).apply { offscreenPageLimit = 1; adapter = Pages() }
        root.addView(pager, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT).apply { bottomMargin = ProfileBar.height(this@ProfileActivity) })
        chip = TextView(this).apply {
            setTextColor(Color.WHITE); textSize = 13f; visibility = android.view.View.GONE; setPadding(dp(12), dp(6), dp(12), dp(6))
            background = GradientDrawable().apply { setColor(Color.parseColor("#99000000")); cornerRadius = dp(14).toFloat() }
        }
        root.addView(chip, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP or Gravity.CENTER_HORIZONTAL).apply { topMargin = dp(8) })
        this.root = root
        collector = com.aiwa.app.voir.ZoneCollector(this, root)
        applyBar(BarConfig.last)
        setContentView(root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        pager.setCurrentItem(start, false)
        pager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() { override fun onPageSelected(position: Int) { chip.visibility = android.view.View.GONE; applyBar(BarConfig.last); if (position % 6 == 0) noteAround() } })
        built = true
        updateChrome()
        refreshKeys()
        BarConfig.load(ProfileSettings.repo(this), null, builtinKeys().keys) { entries -> runOnUiThread { if (!isFinishing && !isDestroyed) applyBar(entries) } }
        // the profiles of the zone are noted in the background by small groups, nothing is ranked on its own: « Rang » shows what is known
        noteAround()
    }

    // The levels are not shown: a Like goes into the list of the profile, and a swipe toward the previous one from the FIRST profile of a level goes back to the level before.
    private val backGesture by lazy {
        android.view.GestureDetector(this, object : android.view.GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: android.view.MotionEvent?, e2: android.view.MotionEvent, velocityX: Float, velocityY: Float): Boolean {
                val dx = e2.x - (e1?.x ?: e2.x); val dy = e2.y - (e1?.y ?: e2.y)
                if (stack.isNotEmpty() && pager.currentItem == 0 && dx > dp(80) && Math.abs(dx) > Math.abs(dy) * 1.5f) back()
                return false
            }
        })
    }

    override fun dispatchTouchEvent(ev: android.view.MotionEvent): Boolean {
        if (::pager.isInitialized) backGesture.onTouchEvent(ev)
        return super.dispatchTouchEvent(ev)
    }

    private lateinit var root: FrameLayout
    private var barView: android.view.View? = null
    private var built = false      // the window is complete: the keys may ask about the profile on the screen

    /** The keys the application has on a visited profile: the person's own file (her profile repository) may reorder, restyle or leave out any of them, and add others. Without a file: Favoris, Swipe, Précédent (in the place of someone), Give, Match, Widget, Rang. */
    private fun builtinKeys() = linkedMapOf(
        "favoris" to ProfileBar.Spec("☆", "Favoris", ProfileBar.GOLD) { if (isOwn()) startActivity(favoritesIntent(this)) else toggleFavorite() },
        "swipe" to ProfileBar.Spec("⤴", "Jump", ProfileBar.VIOLET) { swipeIn() },
        "precedent" to ProfileBar.Spec("↩", "Précédent", ProfileBar.WHITE) { back() },
        "give" to ProfileBar.Spec("🤲", "Give", ProfileBar.GREEN) { give() },
        "match" to ProfileBar.Spec("🤝", "Match", ProfileBar.VIOLET) { match(force = true) },
        "chambre" to ProfileBar.Spec("🚪", "Chambre", ProfileBar.BLUE) { startActivity(Intent(this, com.aiwa.app.chamber.ChamberActivity::class.java).putExtra(com.aiwa.app.chamber.ChamberActivity.EXTRA_REPO, urls[pager.currentItem])) },
        "cafe" to ProfileBar.Spec("☕", "Café", ProfileBar.GOLD) { coffee() },
        "zone" to ProfileBar.Spec("⤴", "Jump", ProfileBar.VIOLET) { swipeIn() },
        "mur" to ProfileBar.Spec("🏆", "Mur", ProfileBar.GREEN) { wall() },
        "widget" to ProfileBar.Spec("✦", "Widget", ProfileBar.WHITE) { pages[pager.currentItem]?.let { HomeRuntime.openPanel(it) } },
    ).also { table -> if (urls.size > 1) table["rang"] = ProfileBar.Spec("🏅", "Rang", ProfileBar.GOLD) { ranking() } }

    /** The page on the screen is the person's own: the first of the home, while no profile of the zone is entered. */
    private fun isOwn(i: Int = pager.currentItem) = ownFirst && stack.isEmpty() && i == 0

    private fun defaultKeys() = if (isOwn()) listOf("favoris", "give", "widget") else listOfNotNull("favoris", "swipe", "give", "match", "widget", if (urls.size > 1) "rang" else null)

    private fun applyBar(entries: List<com.aiwa.client.BarEntry>?) {
        val (specs, ids) = BarConfig.resolve(this, entries, builtinKeys(), defaultKeys())
        barView?.let { root.removeView(it) }
        bar = ProfileBar.build(this, specs, ids)
        barView = bar.view
        root.addView(bar.view, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
        if (built) refreshKeys()
    }

    /** The star: the profile on the screen is kept (or let go) among the favourites. */
    private fun toggleFavorite() {
        if (isOwn()) return
        val repo = urls[pager.currentItem]
        val on = FavoriteRepos.toggle(this, repo)
        toastOnMain(this, if (on) "$repo est dans tes favoris." else "$repo n'est plus dans tes favoris.")
        refreshKeys()
    }

    /** Give: the room, the coffee and the wall of the person, in one window. */
    private fun give() {
        val i = pager.currentItem
        if (isOwn(i)) { startActivity(Intent(this, GiveActivity::class.java)); return }
        startActivity(Intent(this, GiveActivity::class.java).putExtra(GiveActivity.EXTRA_REPO, urls[i]).putExtra(GiveActivity.EXTRA_PUB, pubs.getOrNull(i).orEmpty()))
    }

    /** « Swipe » on a profile: the person takes its place and navigates the list it left in its own repository (what this phone was told when it met it is the second choice); the levels left behind are kept. */
    private fun swipeIn() {
        val i = pager.currentItem
        val repo = urls[i]
        if (repo.equals(ProfileSettings.repo(this), ignoreCase = true)) return      // on her own profile there is nothing to jump to
        toastOnMain(this, "Je lis la liste de ${repo.substringBefore('/')}…")
        CoroutineScope(Dispatchers.Main).launch {
            val fromRepo = withContext(Dispatchers.IO) { try { Aiwa.brain.profileSeen(repo) } catch (err: Exception) { emptyList() } }
            val list = (fromRepo.ifEmpty { SwipeData.listFor(this@ProfileActivity, repo) }).filter { ProfileView.valid(it) && it != repo }
            if (list.isEmpty()) { toastOnMain(this@ProfileActivity, "Cette personne n'a pas de liste : elle n'a rien croisé, ou elle n'utilise pas Aiwa."); return@launch }
            if (urls.getOrNull(pager.currentItem) != repo) return@launch      // she moved on while it was read
            stack.add(Level(urls, pubs, pager.currentItem))
            setDeck(list, MutableList(list.size) { "" }, 0)
            updateChrome()
        }
    }

    /** « Précédent »: back to the level before. */
    private fun back() {
        if (stack.isEmpty()) return
        val level = stack.removeAt(stack.size - 1)
        setDeck(level.urls, level.pubs, level.index)
        updateChrome()
    }

    /** A new list of profiles in the pager (a level entered or left). */
    private fun setDeck(newUrls: List<String>, newPubs: MutableList<String>, index: Int) {
        urls = newUrls; pubs = newPubs
        val old = pages.values.toList()
        pages.clear()
        pager.adapter = Pages()
        pager.setCurrentItem(index.coerceIn(0, urls.size - 1), false)
        old.forEach { HomeRuntime.release(it); it.destroy() }
        noteAround()
    }

    /** What changes with the level: where the person stands, and the keys (Précédent only when there is a level behind). */
    private fun updateChrome() {
        applyBar(BarConfig.last)
    }

    /** The profiles are noted progressively: the one on the screen and the next ones first, a few at a time (each note is a question to the person's own model), never the whole list at once. */
    private fun noteAround() {
        val from = pager.currentItem.coerceIn(0, (urls.size - 1).coerceAtLeast(0))
        val window = urls.drop(from).take(12)
        if (window.isNotEmpty()) CoroutineScope(Dispatchers.IO).launch { try { Aiwa.brain.matchBatch(window) } catch (err: Exception) { } }
    }

    /** The ranking known so far, as a list that grows while the profiles are noted; a touch on a line goes to that profile. */
    private fun ranking() {
        val head = TextView(this).apply { setPadding(dp(20), dp(8), dp(20), dp(4)); text = "…" }
        val rows = mutableListOf<String>()
        val repos = mutableListOf<String>()
        val adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, rows)
        val list = ListView(this).apply { this.adapter = adapter }
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; addView(head); addView(list) }
        val dialog = AlertDialog.Builder(this).setTitle("Classement de la zone").setView(box).setNegativeButton("Fermer", null).create()
        list.setOnItemClickListener { _, _, position, _ ->
            val at = urls.indexOf(repos.getOrNull(position))
            if (at >= 0) { pager.currentItem = at; dialog.dismiss() }
        }
        dialog.show()
        val job = CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { try { Aiwa.brain.matchBatch(urls) } catch (err: Exception) { } }
            while (isActive) {
                val out = withContext(Dispatchers.IO) { try { Aiwa.brain.matchRanking() } catch (err: Exception) { null } }
                val items = out?.json?.optJSONArray("items")
                if (out != null && items != null) {
                    rows.clear(); repos.clear()
                    for (i in 0 until items.length()) {
                        val item = items.getJSONObject(i)
                        repos.add(item.optString("repo"))
                        rows.add("${i + 1}. ${item.optString("repo")} : Pro ${item.optInt("pro")} · Perso ${item.optInt("perso")}")
                    }
                    adapter.notifyDataSetChanged()
                    val done = out.json.optInt("done"); val total = out.json.optInt("total")
                    head.text = if (out.json.optBoolean("running")) "$done profils notés sur $total, la liste se complète…" else if (done == 0) "Aucun profil noté (il faut ta clé Anthropic et des profils lisibles)." else "$done profils notés sur $total."
                }
                delay(2000)
            }
        }
        dialog.setOnDismissListener { job.cancel() }
    }

    /** The score of the profile on the screen for the person who looks, made by her own super agent (the brain keeps it): it is written on the Match key itself, « Pro 72 · Perso 41 ». */
    private fun match(force: Boolean = false) {
        if (isOwn()) return
        val repo = urls[pager.currentItem]
        val key = bar.named["match"] ?: return
        scores[repo]?.let { key.label(it); if (!force) return }
        key.label("…")
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.match(repo) }
            if (out.ok) { scores[repo] = "Pro ${out.json.optInt("pro")} · Perso ${out.json.optInt("perso")}" }
            if (urls.getOrNull(pager.currentItem) == repo) {
                key.label(scores[repo] ?: "Match")
                if (!out.ok && force) AlertDialog.Builder(this@ProfileActivity).setTitle("Match").setMessage(out.error ?: "Pas de note.").setPositiveButton("Ok", null).show()
            }
        }
    }

    /** What the keys say for the profile on the screen: the score (asked at once), the coffee and the wall only when her card is known (and the coffee turned on). */
    private fun refreshKeys() {
        val i = pager.currentItem
        if (isOwn(i)) return
        val pub = pubs.getOrNull(i).orEmpty()
        bar.named["match"]?.label(scores[urls[i]] ?: "Match")
        bar.named["swipe"]?.available(!urls[i].equals(ProfileSettings.repo(this), ignoreCase = true))
        bar.named["favoris"]?.label(if (FavoriteRepos.has(this, urls[i])) "★ Favori" else "☆ Favoris")
        bar.named["cafe"]?.available(CoffeeSettings.walletConnected(this) && pub.isNotEmpty())
        bar.named["mur"]?.available(pub.isNotEmpty())
        if (pub.isEmpty()) findPub(i)
        match()
    }

    /** Her key, if she left it in her profile (`Profile/aiwa.json`): the coffee and the wall then know where to go, even when she gave no card in « Voir ». */
    private fun findPub(i: Int) {
        val repo = urls[i]
        CoroutineScope(Dispatchers.Main).launch {
            val found = withContext(Dispatchers.IO) { Aiwa.brain.profilePub(repo) } ?: return@launch
            if (pubs.getOrNull(i).isNullOrEmpty()) { pubs[i] = found; if (pager.currentItem == i) refreshKeys() }
        }
    }

    /** What the person of this profile received: her wall, read for the identity of her signed card. */
    private fun wall() {
        val pub = pubs.getOrNull(pager.currentItem).orEmpty()
        if (pub.isEmpty()) toastOnMain(this, "Cette personne n'a pas donné sa carte dans « Voir » : pas de mur.") else WebActivity.wall(this, pub)
    }

    /** The wallet page with the card « Offrir un café » (two taps to send): the profile says nothing, the key comes from the signed card the person gave out in « Voir ». */
    private fun coffee() {
        val i = pager.currentItem
        val pub = pubs.getOrNull(i).orEmpty()
        when {
            !CoffeeSettings.walletConnected(this) -> toastOnMain(this, "Le wallet n'est pas connecté : connecte-le (widget, Wallet) pour offrir un café.")
            pub.isEmpty() -> toastOnMain(this, "Cette personne n'a pas donné sa carte dans « Voir » : pas de café.")
            else -> WebActivity.wallet(this, pub, urls[i])
        }
    }

    override fun onResume() {
        super.onResume()
        if (!ownFirst) return
        CoffeeSettings.publishPub(this)
        startOwnWatch()
        startEar()
        collector.start()
        startZoneTicker()
        // The widget is asked for at every opening while there is none (the system's window, one tap on « Ajouter »), once the screen is really in front and has settled.
        window.decorView.postDelayed({ if (!isFinishing && !isDestroyed) WidgetPin.offerOnce(this) }, 800)
        // Claude first (essential), then GitHub: see Onboarding
        window.decorView.postDelayed({ if (!isFinishing && !isDestroyed) Onboarding.next(this) }, 1500)
    }

    override fun onPause() {
        ownWatch?.stop(); ownWatch = null
        if (ownFirst) { collector.pause(); zoneTicker?.let { root.removeCallbacks(it) } }
        super.onPause()
    }

    /** Her own page follows her `Profile/` on GitHub: a new commit replaces it on the screen within seconds (a change asked of the super agent shows at once). */
    private fun startOwnWatch() {
        val repo = ProfileSettings.repo(this)
        if (!ProfileView.valid(repo)) { ownWatch?.stop(); ownWatch = null; return }
        if (ownWatch != null && ownWatched == repo) return
        ownWatch?.stop()
        ownWatched = repo
        ownWatch = ProfileWatch(repo!!) { sha ->
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                pages[0]?.takeIf { isOwnPageBound() }?.let { ProfileView.load(it, repo, own = true, sha = sha) }
                BarConfig.load(repo, sha, builtinKeys().keys) { entries -> runOnUiThread { if (!isFinishing && !isDestroyed) applyBar(entries) } }
            }
        }.also { it.start() }
    }

    private fun isOwnPageBound() = ownFirst && stack.isEmpty()

    private fun startEar() {
        if (!ListenSettings.enabled(this)) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) { VoiceService.ensureStarted(applicationContext); return }
        val prefs = getSharedPreferences("aiwa_hints", MODE_PRIVATE)
        if (!prefs.getBoolean("mic_asked", false)) { prefs.edit().putBoolean("mic_asked", true).apply(); micPermission.launch(Manifest.permission.RECORD_AUDIO) }
    }

    /** What the zone notes by itself is added at the end of the home, without touching the pages already there (her own page keeps playing). */
    private fun startZoneTicker() {
        zoneTicker?.let { root.removeCallbacks(it) }
        val tick = object : Runnable {
            override fun run() {
                appendZone()
                root.postDelayed(this, 20_000)
            }
        }
        zoneTicker = tick
        root.postDelayed(tick, 6_000)
    }

    private fun appendZone() {
        if (!isOwnPageBound()) return
        val own = ProfileSettings.repo(this)
        val fresh = SwipeData.observed(this, 7).filter { ProfileView.valid(it) && !it.equals(own, ignoreCase = true) && it !in urls }
        if (fresh.isEmpty()) return
        val from = urls.size
        urls = urls + fresh
        pubs.addAll(fresh.map { "" })
        pager.adapter?.notifyItemRangeInserted(from, fresh.size)
    }

    override fun onDestroy() {
        if (::collector.isInitialized) collector.destroy()
        zoneTicker?.let { root.removeCallbacks(it) }
        pages.values.forEach { HomeRuntime.release(it); it.destroy() }; pages.clear(); super.onDestroy()
    }

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
            if (ownFirst && stack.isEmpty() && position == 0) {
                HomeRuntime.attach(web, true) { ProfileSettings.repo(this@ProfileActivity) }
                ProfileView.load(web, ProfileSettings.repo(this@ProfileActivity), own = true)
            } else {
                HomeRuntime.attach(web, false) { urls[position] }
                ProfileView.load(web, urls[position])
            }
        }
    }

    companion object {
        const val EXTRA_URLS = "urls"
        const val EXTRA_INDEX = "index"
        const val EXTRA_PUBS = "pubs"
        const val EXTRA_HOME = "home"           // the home of the application: her own profile first, then her zone
        fun homeIntent(context: Context): Intent = Intent(context, ProfileActivity::class.java).putExtra(EXTRA_HOME, true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        const val EXTRA_FAVORITES = "favorites"     // the deck is the favourites
        fun favoritesIntent(context: Context): Intent = Intent(context, ProfileActivity::class.java).putExtra(EXTRA_FAVORITES, true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        const val EXTRA_ZONE = "zone"       // level 0 = the zone of this phone (what it saw, the nearest first)
        fun zoneIntent(context: Context): Intent = Intent(context, ProfileActivity::class.java).putExtra(EXTRA_ZONE, true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        fun open(context: Context, repos: List<String>, index: Int = 0, pubs: List<String> = emptyList()) =
            context.startActivity(Intent(context, ProfileActivity::class.java).putExtra(EXTRA_URLS, JSONArray(repos).toString()).putExtra(EXTRA_PUBS, JSONArray(pubs).toString()).putExtra(EXTRA_INDEX, index).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
