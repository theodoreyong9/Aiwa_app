"""The catalogue of the places a video shot can come from, with what each needs and does not do: the super agent and the settings read it, so the choice follows the keys the person really has."""


def catalogue(keys):
    """`keys`: {"pexels", "pixabay", "hf"} (booleans) and "fal" (bool). A list of {id, name, ready, needs, does, limit}."""
    k = lambda name: bool(keys.get(name))
    return [
        {"id": "blender", "name": "Blender et frames", "ready": True, "needs": "", "does": "schémas, plans 3D, paysages, titres et écrans, montage ffmpeg", "limit": "fait par une session, pas de prises de vue réelles"},
        {"id": "decors", "name": "Décors 3D (Poly Haven)", "ready": True, "needs": "", "does": "521 modèles 3D, 997 HDRI (ciels et lumières), 869 textures, tous CC0 : le décor d'un plan rendu dans Blender (`asset-research`, à chercher puis à transformer)",
         "limit": "une caméra qui filme le décor, pas de déplacement libre dans une scène ; une base, jamais une scène finie"},
        {"id": "archives", "name": "Archives du domaine public (NASA, Commons, Internet Archive)", "ready": True, "needs": "", "does": "environ 800 séquences réelles référencées (espace, nature, histoire), licence et crédit notés (`asset-research`, footage)", "limit": "qualité et durée très variables ; crédit à mettre"},
        {"id": "webfx", "name": "Effets web (animations HTML)", "ready": True, "needs": "", "does": "animations de pages (GSAP, Lottie, WebGL…) rendues en frames par le moteur HTML du kit ; `design-research` répertorie des sites primés et leurs techniques", "limit": "un effet se réécrit, il ne se copie pas ; le lien design-research vers vidéo n'est pas vérifié"},
        {"id": "stock", "name": "Pexels / Pixabay", "ready": k("pexels") or k("pixabay"), "needs": "clé Pexels ou Pixabay (gratuite)", "does": "séquences réelles libres de droits (paysages, villes, foules)", "limit": "ce qui existe déjà ; licence et auteur notés avec chaque clip"},
        {"id": "hf", "name": "Hugging Face (Wan 2.2, LTX-Video)", "ready": True, "needs": "clé Hugging Face (gratuite) pour un quota plus large",
         "does": "plan généré depuis un texte ou une image, sans référence d'identité", "limit": "sans clé quelques minutes de calcul par jour ; l'identité ou un produit ne tiennent pas d'un plan à l'autre"},
        {"id": "fal", "name": "fal.ai (Kling)", "ready": k("fal"), "needs": "clé fal.ai et crédits", "does": "plans avec ton visage et/ou ton produit fidèles (images de référence), voix, bouche", "limit": "payant ; jamais le visage d'une autre personne"},
        {"id": "photos", "name": "Photos animées", "ready": True, "needs": "", "does": "zoom et parallaxe sur une image fixe (ffmpeg)", "limit": "pas de mouvement réel"},
    ]


def line(keys):
    """One line for the super agent: what is ready and what is missing."""
    items = catalogue(keys)
    ready = ", ".join(i["name"] for i in items if i["ready"])
    missing = "; ".join(f"{i['name']} ({i['needs']})" for i in items if not i["ready"])
    return "Sources vidéo prêtes : " + ready + "." + (" Il manque : " + missing + "." if missing else "")
