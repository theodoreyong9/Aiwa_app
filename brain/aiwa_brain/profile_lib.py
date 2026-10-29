"""The profile: a folder `Profile/` of ONE repository the person chose in the settings. It is a production like the others (documents, media, page): the super agent hears « on travaille sur mon profil », the session
writes the page there (`Profile/index.html`, as complex as wanted: a video or a GIF behind, the files in front, the ways to reach her), and GitHub Pages publishes it. Aiwa writes nothing itself: it only remembers which
repository and tells the sessions what the folder is for. Nothing is published: the app reads `Profile/index.html` from the repository as it is (a public one), and shows it."""
import json
import re

from .paths import DATA

PROFILE_FILE = DATA / "profile.json"
FOLDER = "Profile"
REPO_RE = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")


def load():
    try:
        data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def repo():
    value = load().get("repo")
    return value if isinstance(value, str) and REPO_RE.fullmatch(value) else None


def set_repo(value):
    """Remembers the repository of the profile; False when it is not « owner/name »."""
    value = " ".join(str(value or "").split())
    if not REPO_RE.fullmatch(value):
        return False
    data = load()
    data["repo"] = value
    PROFILE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return True


def note():
    """What the person wrote for the super agents she meets in a chamber (never shown to the other person)."""
    value = load().get("chamber_note")
    return value if isinstance(value, str) else ""


def set_note(value):
    data = load()
    data["chamber_note"] = " ".join(str(value or "").split())[:400]
    PROFILE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


SKILL_URL = "https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/profile/SKILL.md"
READ_MAX = 2_000_000        # bytes of the page the brain reads to check it (a limit of reading, not of making)


UI_FILE = "aiwa-ui.json"
# What the application's own look may name as an action (keep in step with AgentScreens.TOKENS and the keys of the bar in the Android app).
UI_KEYS = "match, chambre, cafe, zone, mur, widget, rang"
UI_SCREENS = ("files_docs, files_image, files_video, files_app, files_page, files, build, scenario, cast, voir, voir_near, voir_link, voir_qr, voir_fav, chambre, settings, update, question, claude, add, "
              "listen, wallet, report, home, github, health, claude_login, keys, style, wall")


def instruction(repo_name=None):
    """What a session is told about the profile folder (and, when a repository is chosen, which one it is). The how-to is the profile skill; here only what must never be missed."""
    text = (
        f"Profil : le dossier `{FOLDER}/` d'un dépôt est la page de la personne, la VITRINE d'Aiwa, et aussi son ACCUEIL dans l'application. "
        f"Quand elle dit qu'on travaille sur son profil, tu écris `{FOLDER}/index.html` (médias à côté) en suivant le skill {SKILL_URL} : lis-le avant de t'y mettre. "
        "Ce qui ne se négocie pas : son nom en titre (`<h1>`), un `<title>`, la balise viewport, un fond qui vit, des liens, aucune ressource en `http://`, et jamais de défilement bloqué. "
        "Les boutons d'Aiwa ne s'écrivent pas : tu poses des EMPLACEMENTS (`data-aiwa-button=\"widget\"`, `data-aiwa-slot=\"build\"`, `data-aiwa-scenarios`) et l'application y met les vrais boutons. "
        "La page affichée est celle de la branche par défaut : pousse ou fusionne là. "
        f"L'APPLICATION se personnalise aussi par un fichier : `{FOLDER}/{UI_FILE}` décrit la barre du bas de l'application (et elle seule : le widget n'est jamais touché), par exemple "
        '`{"v":1,"bar":[{"action":"zone","icon":"📍","label":"Autour","tone":"violet"},{"action":"url:https://…","icon":"🎬","label":"Film"}]}`. '
        f"Huit touches au plus, dans l'ordre voulu ; `label` : 14 caractères au plus ; `icon` : un emoji ; `tone` : violet, blue, gold, green, white ou #RRGGBB ; `action` : {UI_KEYS}, "
        f"un écran parmi {UI_SCREENS}, ou `url:https://…`. Une touche absente de la liste disparaît ; sans fichier valide, la barre reste celle de l'application. Le changement apparaît dans les secondes qui suivent ton commit."
    )
    if repo_name:
        text += f" Son dépôt du profil est {repo_name} : c'est là, et seulement là, que va ce dossier ; tu travailles dans ce dépôt quand elle parle de son profil."
    return text


def check(html, media=None):
    """What a profile must have, and nothing more (no limit of weight, of script or of network: a profile does what a site does): its problems as plain sentences; an empty list when it is good."""
    problems = []
    low = html.lower()
    if "<title>" not in low:
        problems.append("Il manque le <title>.")
    if 'name="viewport"' not in low and "name='viewport'" not in low:
        problems.append("Il manque la balise viewport : la page ne se lira pas bien sur un téléphone.")
    if re.search(r"""(?:src|href|url)\s*[=(]\s*["']?http://""", low):
        problems.append("Une ressource est en http:// : le navigateur du téléphone la bloque, mets https ou un chemin relatif.")
    if "<h1" not in low:
        problems.append("Il manque le nom en titre (<h1>).")
    if not re.search(r"""href\s*=\s*["'](?:https://|mailto:|tel:)""", low):
        problems.append("Aucun lien : au moins les fichiers publics et un moyen de te joindre.")
    if "<video" not in low and "background" not in low and "<canvas" not in low:
        problems.append("Pas de fond : une vidéo, un canvas, un GIF ou une image derrière le texte.")
    return problems
