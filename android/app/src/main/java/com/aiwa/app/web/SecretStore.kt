package com.aiwa.app.web
import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * The few secrets the wallet keeps (its 12 words): encrypted with an AES key that
 * lives in the Android Keystore and never leaves it, and written to this app's private preferences. The page asks for them
 * through the host channel and cannot read the files themselves; an app running in the sandbox of a page cannot even ask.
 *
 * The preferences are excluded from the app's backup (res/xml/data_extraction_rules.xml): a Keystore key does not move to
 * another phone, so a copy of the ciphertext there would be worth nothing. On a new phone the 12 words are typed once.
 */
class SecretStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun key(): SecretKey {
        val keystore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keystore.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return generator.generateKey()
    }

    /** The secret, or null when there is none — or when it can no longer be read (the Keystore key was lost): then it is dropped. */
    fun get(name: String): String? {
        val stored = prefs.getString(name, null) ?: return null
        return try {
            val (iv, body) = stored.split(":").map { Base64.decode(it, Base64.NO_WRAP) }
            val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv)) }
            String(cipher.doFinal(body), Charsets.UTF_8)
        } catch (err: Exception) {
            prefs.edit().remove(name).commit()
            null
        }
    }

    /** Kept before this returns: the page spends nothing with a wallet whose words are not yet safe. */
    fun set(name: String, value: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
        val sealed = Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(cipher.doFinal(value.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
        if (!prefs.edit().putString(name, sealed).commit()) throw IllegalStateException("the phone refused to keep it")
    }

    fun delete(name: String) {
        prefs.edit().remove(name).commit()
    }

    private companion object {
        const val PREFS = "aiwa_secrets"
        const val ALIAS = "aiwa-store-secrets"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
