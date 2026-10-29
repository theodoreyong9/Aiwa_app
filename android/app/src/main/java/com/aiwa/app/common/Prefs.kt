package com.aiwa.app.common

import android.content.Context

/** A small file of preferences. Every read and write is guarded: a preference that cannot be read is its default, never a crash in a widget. */
class Prefs(context: Context, name: String) {
    private val store = context.applicationContext.getSharedPreferences(name, Context.MODE_PRIVATE)

    fun string(key: String, default: String? = null): String? = try { store.getString(key, default) } catch (err: Exception) { default }
    fun bool(key: String, default: Boolean = false): Boolean = try { store.getBoolean(key, default) } catch (err: Exception) { default }
    fun int(key: String, default: Int = 0): Int = try { store.getInt(key, default) } catch (err: Exception) { default }
    fun long(key: String, default: Long = 0L): Long = try { store.getLong(key, default) } catch (err: Exception) { default }

    fun put(key: String, value: String?) { try { store.edit().apply { if (value == null) remove(key) else putString(key, value) }.apply() } catch (err: Exception) { } }
    fun put(key: String, value: Boolean) { try { store.edit().putBoolean(key, value).apply() } catch (err: Exception) { } }
    fun put(key: String, value: Int) { try { store.edit().putInt(key, value).apply() } catch (err: Exception) { } }
    fun put(key: String, value: Long) { try { store.edit().putLong(key, value).apply() } catch (err: Exception) { } }
    fun remove(key: String) { try { store.edit().remove(key).apply() } catch (err: Exception) { } }
}
