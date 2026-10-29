package com.aiwa.app.widget

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.CornerPathEffect
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PointF
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.text.TextPaint
import android.text.TextUtils
import androidx.core.content.ContextCompat

/**
 * The whole widget drawn as ONE picture per tab (Canvas), with the freedom of a drawing: the card, a strip of slanted tabs whose open one is a raised piece of glass, and under it a mosaic of cells
 * that touch (no empty gaps: the seams are slanted hairlines), each cell a piece of glass with its own light (a glow inside when it is active). The pictures are laid under invisible touch zones of the same
 * proportions (see FastWidget and res/layout/fast_widget.xml). Nothing here knows what a button does: it only draws what it is given.
 */
object WidgetArt {
    /** One cell: its icon, its word, its colour (grey, green, red, orange, violet, blue) and whether it answers a tap (an unavailable one is drawn dim). */
    class Btn(val icon: Int, val label: String, val tone: String = "grey", val enabled: Boolean = true, val iconOnly: Boolean = false)

    /** One cell of the strip of the tabs (its colour shows only when it is the open one, unless `always`). `icon` 0 = a word only (the question, the update). */
    class Tab(val icon: Int, val label: String, val tone: String = "grey", val weight: Float = 1f, val always: Boolean = false, val dot: Boolean = false)

    // top, bottom, edge, glow (0 = none)
    private fun colours(tone: String): IntArray = translucent(solid(tone))

    /** The coloured tones are see-through (the photo and the light show through them); the grey one already is. */
    private fun translucent(c: IntArray): IntArray {
        if (c[3] == 0) return c
        c[0] = withAlpha(c[0], 0xA0); c[1] = withAlpha(c[1], 0x78)
        return c
    }

    private fun solid(tone: String): IntArray = when (tone) {
        "green" -> intArrayOf(0xFF3FA37E.toInt(), 0xFF22664A.toInt(), 0xFF8FE3BE.toInt(), 0xCC52D6A0.toInt())
        "red" -> intArrayOf(0xFFE5605B.toInt(), 0xFFA8302D.toInt(), 0xFFFFA39F.toInt(), 0xCCF27A75.toInt())
        "orange" -> intArrayOf(0xFFE09A7C.toInt(), 0xFFB5603F.toInt(), 0xFFFFCDB6.toInt(), 0x66E09A7C.toInt())
        "violet" -> intArrayOf(0xFFA77BD6.toInt(), 0xFF6F4A9E.toInt(), 0xFFDCC3FA.toInt(), 0x66A77BD6.toInt())
        "yellow" -> intArrayOf(0xFFE8C14A.toInt(), 0xFFA9831C.toInt(), 0xFFFFEBA6.toInt(), 0x88F2CF5E.toInt())
        "blue" -> intArrayOf(0xFF6B9BF5.toInt(), 0xFF2F5DB8.toInt(), 0xFFC4D3FF.toInt(), 0x883A6ECD.toInt())
        else -> intArrayOf(0x30FFFFFF, 0x0DFFFFFF, 0x66FFFFFF, 0x00000000)       // glass: the card shows through
    }

    private var grainTile: Bitmap? = null

    /** A 96 px tile of fine noise (white and black specks of very low opacity), made once. */
    private fun grain(): Bitmap = grainTile ?: Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888).also { b ->
        val rnd = java.util.Random(7)
        val px = IntArray(96 * 96) { if (rnd.nextBoolean()) (rnd.nextInt(14) shl 24) or 0xFFFFFF else (rnd.nextInt(18) shl 24) }
        b.setPixels(px, 0, 96, 0, 0, 96, 96)
        grainTile = b
    }

    private var photoRes = 0
    private var photoBitmap: Bitmap? = null

    /** The photo of a drawable (0 = none), decoded once and kept. */
    private fun photo(context: Context, res: Int): Bitmap? {
        if (res == 0) return null
        if (res != photoRes) {
            photoBitmap = try { android.graphics.BitmapFactory.decodeResource(context.resources, res) } catch (err: Throwable) { null }
            photoRes = res
        }
        return photoBitmap
    }

    private fun withAlpha(color: Int, alpha: Int): Int = (color and 0x00FFFFFF) or (alpha.coerceIn(0, 255) shl 24)

    private fun paint(): Paint = Paint(Paint.ANTI_ALIAS_FLAG)

    /** The picture of the widget for the open tab `active` (an index of `tabs`), with the rows of cells of its page. */
    fun full(context: Context, widthPx: Int, heightPx: Int, alert: Boolean, background: Int, tabs: List<Tab>, active: Int, rows: List<List<Pair<Btn, Float>>>): Bitmap {
        val unit = widthPx / 330f                      // one « dp » of the drawing: the picture is designed on a card 330 wide
        val bmp = Bitmap.createBitmap(widthPx, heightPx, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)
        val w = widthPx.toFloat(); val h = heightPx.toFloat()
        val radius = 26f * unit
        val tabH = h * 7f / 22f
        val skew = tabH * 0.26f
        val total = tabs.sumOf { it.weight.toDouble() }.toFloat()
        // the tabs: slanted pieces (a closed one is lower than the open one); the card is the body under them PLUS the tabs, nothing around: the rest of the picture stays transparent
        val tabShapes = ArrayList<Pair<List<PointF>, Float>>()
        val inset = w * 0.07f                         // the strip of the tabs and the last row are narrower than the middle row: the silhouette of the widget has steps
        val span = w - 2 * inset
        var tx = inset
        tabs.forEachIndexed { i, tab ->
            val x0 = tx; val x1 = tx + span * tab.weight / total; tx = x1
            val top = if (i == active) 0f else tabH * 0.22f
            val sk = skew * (tabH - top) / tabH
            tabShapes += listOf(PointF(x0, tabH + 1.5f * unit), PointF(x0 + sk, top), PointF(if (i == tabs.size - 1) x1 - sk else x1 + sk, top), PointF(x1, tabH + 1.5f * unit)) to top
        }
        val midBottom = tabH + (h - tabH) * (if (rows.size == 2) 10f / 15f else 1f)
        val card = Path().apply {
            if (rows.size == 2) {
                addRoundRect(RectF(0f, tabH, w, midBottom), 9f * unit, 9f * unit, Path.Direction.CW)
                op(Path().apply { addRoundRect(RectF(inset, midBottom - 4f * unit, w - inset, h), floatArrayOf(0f, 0f, 0f, 0f, radius, radius, radius, radius), Path.Direction.CW) }, Path.Op.UNION)
            } else addRoundRect(RectF(0f, tabH, w, h), floatArrayOf(8f * unit, 8f * unit, 8f * unit, 8f * unit, radius, radius, radius, radius), Path.Direction.CW)
        }
        tabShapes.forEach { (poly, _) -> card.op(Path().apply { moveTo(poly[0].x, poly[0].y); for (p in poly.drop(1)) lineTo(p.x, p.y); close() }, Path.Op.UNION) }
        canvas.save(); canvas.clipPath(card)
        // the card: a diagonal gradient, a sheen on top
        val bg = paint().apply { shader = LinearGradient(w, 0f, 0f, h, if (alert) 0xFF5B2140.toInt() else 0xFF1D2F66.toInt(), if (alert) 0xFF2A1650.toInt() else 0xFF6A2C8A.toInt(), Shader.TileMode.CLAMP) }
        canvas.drawRect(0f, 0f, w, h, bg)
        // a photo behind the glass (cut to fill the card), darkened and tinted by the card's own colours so that the words stay readable and the alert still shows
        photo(context, background)?.let { p ->
            val scale = maxOf(w / p.width, h / p.height)
            val sw = w / scale; val sh = h / scale
            val src = android.graphics.Rect(((p.width - sw) / 2f).toInt(), ((p.height - sh) / 2f).toInt(), ((p.width + sw) / 2f).toInt(), ((p.height + sh) / 2f).toInt())
            canvas.drawBitmap(p, src, RectF(0f, 0f, w, h), paint().apply { isFilterBitmap = true })
            canvas.drawRect(0f, 0f, w, h, paint().apply { shader = LinearGradient(w, 0f, 0f, h, withAlpha(if (alert) 0xFF5B2140.toInt() else 0xFF1D2F66.toInt(), 150), withAlpha(if (alert) 0xFF2A1650.toInt() else 0xFF2A1450.toInt(), 190), Shader.TileMode.CLAMP) })
        }
        // the body under the tabs: lighter glass
        canvas.drawRect(0f, tabH, w, h, paint().apply { shader = LinearGradient(0f, tabH, 0f, h, 0x22FFFFFF, 0x0AFFFFFF, Shader.TileMode.CLAMP) })
        // the tabs: the open one is raised glass that joins the body
        var x = inset
        tabs.forEachIndexed { i, tab ->
            val x0 = x; val x1 = x + span * tab.weight / total; x = x1
            val first = i == 0; val last = i == tabs.size - 1
            val isOpen = i == active
            val (poly, top) = tabShapes[i]
            val tone = if (isOpen || tab.always) tab.tone else "grey"      // a tab is coloured only when it is open (or when it calls for attention)
            cell(canvas, poly, tone, true, 6f * unit, unit, raised = isOpen, seam = !isOpen)
            val cx = (x0 + x1) / 2f + skew / 2f - (if (last) skew else 0f)
            content(context, canvas, RectF(cx - (x1 - x0) / 2f, top, cx + (x1 - x0) / 2f, tabH), tab.icon, "", true, unit, if (isOpen) 255 else 215)
            if (tab.dot) { val dr = 3.2f * unit; canvas.drawCircle(cx + 12f * unit, top + (tabH - top) / 2f - 9f * unit, dr, paint().apply { color = 0xCC52D6A0.toInt() }) }
        }
        // the body: rows of cells that touch; the seams are slanted
        // the first row of the body (the middle of the widget) is the thickest; the tabs and the last row are thinner
        val shares = if (rows.size == 2) listOf(10f, 5f) else List(rows.size) { 1f }
        val sumShares = shares.sum()
        var rowTop = tabH
        rows.forEachIndexed { r, row ->
            val rowH = (h - tabH) * shares[r] / sumShares
            val s2 = rowH * 0.22f
            val tot = row.sumOf { it.second.toDouble() }.toFloat()
            val top = rowTop; val bottom = top + rowH; rowTop = bottom
            val narrow = rows.size == 2 && r == 1
            val xa = if (narrow) inset else 0f; val xb = if (narrow) w - inset else w
            var cx0 = xa
            row.forEachIndexed { c, (btn, weight) ->
                val x0 = cx0; val x1 = cx0 + (xb - xa) * weight / tot; cx0 = x1
                val firstC = c == 0; val lastC = c == row.size - 1
                val poly = listOf(PointF(x0, bottom + 1.5f * unit), PointF(if (firstC) x0 else x0 + s2, top - 0.5f * unit), PointF(if (lastC) x1 else x1 + s2, top - 0.5f * unit), PointF(x1, bottom + 1.5f * unit))
                cell(canvas, poly, btn.tone, btn.enabled, 6f * unit, unit, raised = false, seam = true)
                val shift = (if (firstC) 0f else s2 / 2f) / 2f + (if (lastC) 0f else s2 / 2f) / 2f
                content(context, canvas, RectF(x0 + shift, top, x1 + shift, bottom), btn.icon, if (btn.iconOnly) "" else btn.label, btn.enabled, unit, 255, big = r == 0)
            }
        }
        // over everything: a band of light across the card (the glass catches a light), and a fine grain (matte glass, no flat gradients)
        canvas.drawRect(0f, 0f, w, h, paint().apply { shader = LinearGradient(0f, 0f, w * 0.7f, h * 1.6f, intArrayOf(0x00FFFFFF, 0x22FFFFFF, 0x00FFFFFF), floatArrayOf(0.15f, 0.3f, 0.45f), Shader.TileMode.CLAMP) })
        canvas.drawRect(0f, 0f, w, h, paint().apply { shader = android.graphics.BitmapShader(grain(), Shader.TileMode.REPEAT, Shader.TileMode.REPEAT) })
        canvas.restore()
        return bmp
    }

    /** One piece of glass (a polygon with rounded corners): its body, a glow inside, the sheen, the shade, the seam. */
    private fun cell(canvas: Canvas, poly: List<PointF>, tone: String, enabled: Boolean, round: Float, unit: Float, raised: Boolean, seam: Boolean) {
        val c = colours(tone)
        val path = Path().apply { moveTo(poly[0].x, poly[0].y); for (p in poly.drop(1)) lineTo(p.x, p.y); close() }
        val b = RectF(); path.computeBounds(b, true)
        val alpha = if (enabled) 255 else 120
        val body = paint().apply { shader = LinearGradient(0f, b.top, 0f, b.bottom, withAlpha(c[0], (c[0] ushr 24) * alpha / 255), withAlpha(c[1], (c[1] ushr 24) * alpha / 255), Shader.TileMode.CLAMP); pathEffect = CornerPathEffect(round) }
        canvas.drawPath(path, body)
        canvas.save(); canvas.clipPath(path)
        if (c[3] != 0 && enabled) {          // the glow, inside the piece, from its lower middle
            canvas.drawRect(b, paint().apply { shader = RadialGradient(b.centerX(), b.bottom, maxOf(b.width(), b.height()) * 0.8f, c[3], 0x00000000, Shader.TileMode.CLAMP) })
        }
        canvas.drawRect(b, paint().apply { shader = LinearGradient(0f, b.top, 0f, b.centerY() + b.height() * 0.1f, withAlpha(0xFFFFFFFF.toInt(), if (raised) 120 else if (enabled) 62 else 24), 0x00FFFFFF, Shader.TileMode.CLAMP) })
        canvas.drawRect(b, paint().apply { shader = LinearGradient(0f, b.centerY(), 0f, b.bottom, 0x00000000, 0x33000000, Shader.TileMode.CLAMP) })
        canvas.restore()
        if (seam || raised) {
            val edge = paint().apply { style = Paint.Style.STROKE; strokeWidth = (if (raised) 1.4f else 1.0f) * unit; pathEffect = CornerPathEffect(round)
                shader = LinearGradient(0f, b.top, 0f, b.bottom, withAlpha(c[2], if (raised) 235 else if (enabled) 120 else 50), withAlpha(c[2], if (raised) 90 else 40), Shader.TileMode.CLAMP) }
            canvas.drawPath(path, edge)
        }
    }

    /** The icon above the word (or beside it when the piece is low) in the middle of `box`. */
    private fun content(context: Context, canvas: Canvas, box: RectF, iconRes: Int, label: String, enabled: Boolean, unit: Float, alpha0: Int, big: Boolean = false) {
        if (big) { bigContent(context, canvas, box, iconRes, label, enabled, unit); return }
        val alpha = if (enabled) alpha0 else 120
        val text = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL); textSize = 11f * unit; letterSpacing = 0.02f; color = withAlpha(0xFFF4F4FF.toInt(), alpha)
        }
        val avail = box.width() - 16f * unit
        val word = TextUtils.ellipsize(label, text, avail.coerceAtLeast(10f), TextUtils.TruncateAt.END).toString()
        val textW = text.measureText(word)
        val textH = text.descent() - text.ascent()
        val icon = if (iconRes != 0) ContextCompat.getDrawable(context, iconRes)?.mutate() else null
        val size = minOf(20f * unit, box.height() * 0.62f).toInt()
        if (icon != null && label.isEmpty()) {          // the icon alone, a little larger
            val big = minOf(24f * unit, box.height() * 0.7f).toInt()
            icon.setBounds((box.centerX() - big / 2f).toInt(), (box.centerY() - big / 2f).toInt(), (box.centerX() + big / 2f).toInt(), (box.centerY() + big / 2f).toInt()); icon.alpha = alpha; icon.draw(canvas)
            return
        }
        if (icon == null) { canvas.drawText(word, box.centerX() - textW / 2f, box.centerY() - (text.ascent() + text.descent()) / 2f, text); return }
        if (box.height() < 40f * unit) {
            val total = size + 5f * unit + textW; val left = box.centerX() - total / 2f
            icon.setBounds(left.toInt(), (box.centerY() - size / 2f).toInt(), left.toInt() + size, (box.centerY() + size / 2f).toInt()); icon.alpha = alpha; icon.draw(canvas)
            canvas.drawText(word, left + size + 5f * unit, box.centerY() - (text.ascent() + text.descent()) / 2f, text)
        } else {
            val block = size + 1.5f * unit + textH; val top = box.centerY() - block / 2f
            icon.setBounds((box.centerX() - size / 2f).toInt(), top.toInt(), (box.centerX() + size / 2f).toInt(), top.toInt() + size); icon.alpha = alpha; icon.draw(canvas)
            canvas.drawText(word, box.centerX() - textW / 2f, top + size + 1.5f * unit - text.ascent(), text)
        }
    }

    /** The cells of the middle row: a large icon on the left, leaning like the cell, and the word beside it (leaning too). */
    private fun bigContent(context: Context, canvas: Canvas, box: RectF, iconRes: Int, label: String, enabled: Boolean, unit: Float) {
        val alpha = if (enabled) 255 else 120
        val text = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL); textSize = 13f * unit; color = withAlpha(0xFFF4F4FF.toInt(), alpha)
        }
        val icon = if (iconRes != 0) ContextCompat.getDrawable(context, iconRes)?.mutate() else null
        val size = minOf(box.height() * 0.66f, 40f * unit).toInt()
        val pad = 12f * unit
        canvas.save()
        canvas.translate(0f, box.centerY()); canvas.skew(-0.22f, 0f); canvas.translate(0f, -box.centerY())     // the lean of the cell
        if (icon != null) {
            val word = if (label.isEmpty()) "" else TextUtils.ellipsize(label, text, (box.width() - pad * 2 - size - 6f * unit).coerceAtLeast(10f), TextUtils.TruncateAt.END).toString()
            val textW = text.measureText(word)
            val total = size + (if (word.isEmpty()) 0f else 8f * unit + textW)
            val left = if (word.isEmpty()) box.centerX() - size / 2f else (box.left + pad).coerceAtMost(box.centerX() - total / 2f).coerceAtLeast(box.left + 6f * unit)
            icon.setBounds(left.toInt(), (box.centerY() - size / 2f).toInt(), left.toInt() + size, (box.centerY() + size / 2f).toInt()); icon.alpha = alpha; icon.draw(canvas)
            if (word.isNotEmpty()) canvas.drawText(word, left + size + 8f * unit, box.centerY() - (text.ascent() + text.descent()) / 2f, text)
        } else {
            val word = TextUtils.ellipsize(label, text, (box.width() - pad * 2).coerceAtLeast(10f), TextUtils.TruncateAt.END).toString()
            canvas.drawText(word, box.centerX() - text.measureText(word) / 2f, box.centerY() - (text.ascent() + text.descent()) / 2f, text)
        }
        canvas.restore()
    }
}
