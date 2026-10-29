package com.aiwa.app.studio

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.util.Base64
import android.widget.CheckBox
import android.widget.EditText
import androidx.activity.result.contract.ActivityResultContracts
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.settings.KeysActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.ByteArrayOutputStream

/** A photo read from the phone, reduced (1280 px at most, JPEG) so that it travels light. */
internal fun shrinkJpeg(context: Context, uri: Uri): ByteArray? = try {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
    var sample = 1
    while (bounds.outWidth / sample > 2560 || bounds.outHeight / sample > 2560) sample *= 2
    val bitmap = context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample }) }
    if (bitmap == null) null else {
        val scale = minOf(1f, 1280f / maxOf(bitmap.width, bitmap.height))
        val small = if (scale < 1f) Bitmap.createScaledBitmap(bitmap, (bitmap.width * scale).toInt(), (bitmap.height * scale).toInt(), true) else bitmap
        ByteArrayOutputStream().also { small.compress(Bitmap.CompressFormat.JPEG, 88, it) }.toByteArray()
    }
} catch (err: Exception) { null }

/**
 * « Film de moi » (and the film of a product): a short film made through fal.ai with the person's OWN key. The photos, what she wants, the words she says (hers, as she writes them), the format; the quote
 * comes next, and nothing is paid before she confirms it. Four kinds: me, the product, both, or a replacement in her own video.
 */
class FilmActivity : FloatActivity() {
    override val title = "Film"
    private var status: JSONObject? = null
    private var loaded = false
    private var mode = "me"
    private var swapTarget = "product"
    private var photosMe: List<Uri> = emptyList()
    private var photosProduct: List<Uri> = emptyList()
    private var video: Uri? = null
    private var direction = ""
    private var says = ""
    private var aspect = "9:16"
    private val checked = mutableMapOf<String, Boolean>()
    private var busy = false
    private var progress = ""
    private var error: String? = null

    private val pickMe = registerForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris -> if (uris.isNotEmpty()) { photosMe = uris.take(if (mode == "both") 4 else 7); reload() } }
    private val pickProduct = registerForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris -> if (uris.isNotEmpty()) { photosProduct = uris.take(if (mode == "both") 3 else 7); reload() } }
    private val pickVideo = registerForActivityResult(ActivityResultContracts.GetContent()) { uri -> if (uri != null) { video = uri; reload() } }

    override fun onCreate(savedInstanceState: Bundle?) {
        mode = intent.getStringExtra(EXTRA_KIND)?.takeIf { it in listOf("me", "product", "both", "swap") } ?: "me"
        direction = intent.getStringExtra(EXTRA_DIRECTION).orEmpty()
        super.onCreate(savedInstanceState)
        CoroutineScope(Dispatchers.Main).launch {
            status = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.filmStatus() }
            loaded = true; reload()
        }
    }

    override fun onResume() {
        super.onResume()
        if (loaded && status?.optBoolean("key") != true) CoroutineScope(Dispatchers.Main).launch { status = withContext(Dispatchers.IO) { Aiwa.brain.filmStatus() }; reload() }
    }

    private fun field(hintText: String, value: String, lines: Int, onChange: (String) -> Unit) = EditText(this).apply {
        hint = hintText; setText(value); setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0")); minLines = lines
        inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE; gravity = android.view.Gravity.TOP; isEnabled = !busy
        addTextChangedListener(object : android.text.TextWatcher {
            override fun afterTextChanged(s: android.text.Editable?) { onChange(s?.toString().orEmpty().take(1500)) }
            override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) {}
            override fun onTextChanged(s: CharSequence?, st: Int, b: Int, c: Int) {}
        })
    }

    private fun prepare(allChecked: Boolean, mainPhotos: List<Uri>) {
        busy = true; error = null; progress = "Je prépare les photos…"; reload()
        val app = applicationContext
        CoroutineScope(Dispatchers.Main).launch {
            fun encode(uris: List<Uri>) = uris.mapNotNull { shrinkJpeg(app, it) }.map { Base64.encodeToString(it, Base64.NO_WRAP) }
            val main = withContext(Dispatchers.IO) { encode(mainPhotos) }
            val extra = if (mode == "both") withContext(Dispatchers.IO) { encode(photosProduct) } else emptyList()
            progress = "Je prépare le devis…"; reload()
            var out = withContext(Dispatchers.IO) { Aiwa.brain.filmPrepare(direction.trim(), says.trim(), aspect, main, allChecked, mode, extra, swapTarget) }
            var failure = out.error
            if (out.ok && mode == "swap") {
                progress = "J'envoie ta vidéo…"; reload()
                val uri = video
                val id = out.json.optString("id")
                val sent = withContext(Dispatchers.IO) {
                    val length = try { app.contentResolver.openAssetFileDescriptor(uri!!, "r")?.use { it.length } ?: -1L } catch (err: Exception) { -1L }
                    val input = try { app.contentResolver.openInputStream(uri!!) } catch (err: Exception) { null }
                    if (input == null) null else Aiwa.brain.filmSource(id, input, length)
                }
                if (sent == null) failure = "je n'arrive pas à lire cette vidéo" else if (!sent.ok) { failure = sent.error; out = sent }
            }
            busy = false; progress = ""
            if (out.ok && failure == null) { startActivity(Intent(this@FilmActivity, FilmQuoteActivity::class.java).putExtra(FilmQuoteActivity.EXTRA_JOB, out.json.optString("id"))); finish() }
            else { error = failure ?: "refusé"; reload() }
        }
    }

    override fun fill() {
        val st = status
        when {
            st == null -> { note(if (loaded) "Le cerveau ne répond pas (ou il est trop ancien)." else "…"); return }
            !st.optBoolean("key") -> {
                note("Il manque ta clé fal.ai (Réglages, Clés et plafonds).", Palette.RED)
                entry("Mettre ma clé") { startActivity(Intent(this, KeysActivity::class.java)) }
                return
            }
        }
        val swap = mode == "swap"
        val needMe = mode == "me" || mode == "both" || (swap && swapTarget == "person")
        val needProduct = mode == "product" || mode == "both" || (swap && swapTarget == "product")
        val canSpeak = mode == "me" || mode == "both"
        val voiceOver = mode == "product"
        for ((id, label) in listOf("me" to "Moi", "product" to "Produit", "both" to "Moi + produit", "swap" to "Remplacer dans ma vidéo")) {
            entry((if (mode == id) "● " else "○ ") + label, tone = if (mode == id) Palette.CARD else Palette.CARD) { if (!busy) { mode = id; reload() } }
        }
        note(when (mode) {
            "me" -> "Un film inventé où tu apparais : tes photos, ce que tu veux voir, tes paroles."
            "product" -> "Un film inventé de ton produit : ses photos sous plusieurs angles, ce que tu veux montrer, une voix off."
            "both" -> "Un film avec toi ET ton produit, en une seule fois : économique, mais moins fidèle. Ton visage ou le logo peuvent se déformer."
            else -> "Ta propre vidéo, où seul un élément change : le produit ou la personne est remplacé par ce que montrent tes photos."
        } + " Le devis vient avant toute dépense.")
        if (swap) entry("Remplacer : " + (if (swapTarget == "product") "le produit" else "la personne"), "Touche pour changer") { swapTarget = if (swapTarget == "product") "person" else "product"; reload() }
        if (swap) entry(if (video == null) "Choisir ma vidéo (30 s au plus)" else "Vidéo choisie — changer") { if (!busy) pickVideo.launch("video/*") }
        if (needMe) entry(if (photosMe.isEmpty()) (if (swap) "Choisir mes photos (le visage qui remplace)" else "Choisir mes photos") else "${photosMe.size} photo(s) de moi — changer") { if (!busy) pickMe.launch("image/*") }
        if (needProduct) entry(if (photosProduct.isEmpty()) (if (swap) "Choisir les photos du produit qui remplace" else "Choisir les photos du produit") else "${photosProduct.size} photo(s) du produit — changer") { if (!busy) pickProduct.launch("image/*") }
        add(field(if (swap) "Ce qu'il faut remplacer (facultatif)" else if (mode == "product") "Ce que je veux montrer du produit" else "Ce que je veux dans le film", direction, if (swap) 1 else 3) { direction = it })
        if (canSpeak || voiceOver) add(field(if (voiceOver) "Voix off (facultatif, telle que je l'écris)" else "Mes paroles (facultatif, telles que je les dis)", says, 2) { says = it })
        if (canSpeak && says.isNotBlank() && st?.optBoolean("voice") != true) {
            note("Pour parler, enregistre d'abord ta voix.", Palette.RED)
            entry("Enregistrer ma voix") { startActivity(Intent(this, VoiceSampleActivity::class.java)) }
        }
        if (!swap) entry("Format : $aspect") { aspect = when (aspect) { "9:16" -> "16:9"; "16:9" -> "1:1"; else -> "9:16" }; reload() }
        val required = buildList {
            if (needMe) add("me" to "C'est moi sur les photos" + (if (canSpeak) ", et c'est ma voix (ou celle de quelqu'un qui est d'accord)" else "") + ".")
            if (needProduct) add("product" to "Le produit est à moi, ou j'ai le droit de l'utiliser.")
            if (swap) add("video" to "La vidéo est à moi, ou j'ai le droit de l'utiliser.")
            if (swap && swapTarget == "person") add("agree" to "La personne remplacée dans la vidéo est d'accord (ou c'est moi).")
        }
        for ((key, text) in required) add(CheckBox(this).apply { this.text = text; setTextColor(Palette.TEXT); isChecked = checked[key] == true; setOnCheckedChangeListener { _, on -> checked[key] = on; } })
        val mainPhotos = if (mode == "product" || (swap && swapTarget == "product")) photosProduct else photosMe
        note("Le film sera marqué « généré par IA ». Relis chaque plan : un logo ou un texte peut être déformé.")
        error?.let { note(it, Palette.RED) }
        entry(if (busy) progress.ifBlank { "Un instant…" } else "Préparer le devis") {
            val allChecked = required.all { checked[it.first] == true }
            val ready = mainPhotos.isNotEmpty() && (mode != "both" || photosProduct.isNotEmpty()) && (!swap || video != null) && (swap || direction.isNotBlank()) && allChecked
            if (busy) return@entry
            if (!ready) { error = "Il manque une photo, ce que tu veux, ou une case à cocher."; reload() } else prepare(allChecked, mainPhotos)
        }
    }

    companion object {
        const val EXTRA_DIRECTION = "direction"
        const val EXTRA_KIND = "kind"
    }
}
