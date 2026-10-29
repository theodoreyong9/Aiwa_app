package com.aiwa.client

/*
 * What to tell someone whose brain does not answer: it runs in Termux, and the app can neither install Termux nor put the brain in it (one app cannot write into another).
 * So the one line of bootstrap.sh is pasted once, by the person. The app starts the brain when it is there; when it never comes up, the honest message is "it is not installed".
 */

/** The one line that installs (and later updates) the brain, run in Termux. */
const val BOOTSTRAP_COMMAND = "curl -fsSL https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/scripts/bootstrap.sh | bash"

/** Where Termux comes from: F-Droid or GitHub are its only official sources; the Play Store copy is an old unofficial one without RUN_COMMAND, which the widget needs. */
const val TERMUX_DOWNLOAD_URL = "https://f-droid.org/packages/com.termux/"

/** Starts asked of Termux, without the brain ever answering, after which it is called not installed (not just slow). */
const val STARTS_BEFORE_MISSING = 2

enum class Verdict {
    /** Termux itself is not on the phone. */
    TERMUX_MISSING,

    /** Termux is there and was asked to start the brain several times, in vain: it is not installed in it (or Termux refuses). */
    NOT_INSTALLED,

    /** Not answering yet: worth another try. */
    DOWN,
}

fun verdict(termuxInstalled: Boolean, startsWithoutAnswer: Int): Verdict = when {
    !termuxInstalled -> Verdict.TERMUX_MISSING
    startsWithoutAnswer >= STARTS_BEFORE_MISSING -> Verdict.NOT_INSTALLED
    else -> Verdict.DOWN
}

/** What the person is told (a toast); the widget's own line is shorter. */
fun problemMessage(verdict: Verdict): String = when (verdict) {
    Verdict.TERMUX_MISSING -> "Termux n'est pas installé. Installe-le depuis F-Droid, puis colle dans Termux la ligne d'installation d'Aiwa (touche l'état du widget : elle est copiée)."
    Verdict.NOT_INSTALLED -> "Le cerveau n'est pas installé dans Termux. Colle dans Termux la ligne d'installation d'Aiwa (touche l'état du widget : elle est copiée)."
    Verdict.DOWN -> "Le cerveau n'a pas démarré — lancement automatique en cours, réessaie dans 10-15 secondes."
}
