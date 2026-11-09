"""Film 13, the English version of the page of the screens: every French text of ui13.html is replaced (and each replacement must be found, or the script stops). Writes ui13_en.html."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); s = open(os.path.join(HERE, 'ui13.html')).read()
PAIRS = [
 ("'L’IA'", "'AI'"), ("'accélère'", "'speeds up'"), ("'votre travail'", "'your work'"), ("'Et si'", "'What if'"), ("'vos objectifs'", "'your goals'"), ("'étaient'", "'were'"), ("'alignés'", "'aligned'"),
 ("'Et s’il s’agissait,'", "'What if it was,'"), ("'pour la première fois,'", "'for the first time,'"), ("'d’imposer'", "'about setting'"), ("'vos règles'", "'your rules'"), ("VOS RÈGLES.", "YOUR RULES."),
 ("' ?'", "'?'"),
 ("Des pages web et des profils sociaux qui s’adaptent automatiquement au visiteur.", "Web pages and social profiles that adapt to the visitor, automatically."),
 ("Un agent qui vous propose des cibles automatiquement, pour toutes vos créations.", "An agent that suggests targets automatically, for all your creations."),
 ("Et qui découvre vos compatibilités personnelles et professionnelles, autour de vous.", "And that discovers your personal and professional compatibilities, around you."),
 ("02 · CIBLES", "02 · TARGETS"), ("03 · COMPATIBILITÉS", "03 · COMPATIBILITIES"),
 ("'UN AMI'", "'A FRIEND'"), ("'UN RECRUTEUR'", "'A RECRUITER'"), ("MÊME PROFIL", "SAME PROFILE"), ("⚡ deux pages<br>", "⚡ two pages<br>"), (">automatiquement</span>", ">automatically</span>"),
 ("Salut Marie !", "Hey Marie!"), ("Ça fait trop longtemps. J’ai gardé ça pour toi.", "It’s been too long. I kept this for you."), ("Notre playlist · été", "Our playlist · summer"), ("12 titres", "12 tracks"),
 ("['Lisbonne',", "['Lisbon',"), ("['Anniv’',", "['Birthday',"), ("On se voit ce week-end ? 🍻", "See you this weekend? 🍻"),
 ("IA, voix et produits qui se montrent d’eux-mêmes.", "AI, voice and products that sell themselves."), ("'produits livrés'", "'products shipped'"), ("'utilisateurs'", "'users'"), ("['3 ans','d’IA appliquée']", "['3 yrs','of applied AI']"),
 (">Présentation</div>", ">Presentation</div>"), ("0:45 · en deux minutes", "0:45 · in two minutes"), ("Télécharger mon CV", "Download my CV"), ("Prendre rendez-vous", "Book a call"),
 ("Le film d’Aiwa", "The Aiwa film"),
 ("CRÉÉE PAR AIWA ✓ · 0:42", "CREATED BY AIWA ✓ · 0:42"), ("'#produit','#voix','#IA','#lancement','#créateurs'", "'#product','#voice','#AI','#launch','#creators'"), ("AIWA LIT LA CRÉATION", "AIWA READS THE CREATION"),
 ("Message prêt · ", "Message ready · "), ("Lancement.mp4", "Launch.mp4"), (">Lancement</div>", ">Launch</div>"), ("VOTRE UNIVERS · VOTRE VOLONTÉ", "YOUR UNIVERSE · YOUR WILL"),
 ("'Recrutement · Maison Lumen'", "'Recruiting · Maison Lumen'"), ("'Direction artistique'", "'Art direction'"), ("'Fondateur'", "'Founder'"), ("'Responsable produit'", "'Product lead'"), ("'Développeuse · IA locale'", "'Developer · local AI'"), ("'Rédaction'", "'Editorial'"),
 ("'page « Équipe » du site'", "'site “Team” page'"), ("'offre publiée le 3 nov.'", "'job post · Nov 3'"), ("'post public'", "'public post'"), ("'page « Carrières »'", "'site “Careers” page'"), ("'profil Swipe'", "'Swipe profile'"),
 ("Bonjour Camille, votre manière de relier design et code…", "Hi Camille, the way you link design and code…"), ("Votre offre cherche quelqu’un qui montre ses produits…", "Your job post wants someone who shows their products…"),
 ("Votre dernier post parle d’outils créatifs. Voici…", "Your last post is about creative tools. Here is…"), ("Je construis un assistant à la voix : voici la vidéo…", "I’m building a voice assistant: here is the video…"),
 ("Salut Inès, on construit la même chose, autrement…", "Hi Inès, we are building the same thing, differently…"), ("Une vidéo de 42 secondes pour votre prochaine édition…", "A 42-second video for your next edition…"),
 ("${n} cibles<span", "${n} targets<span"), (" · chacune avec sa source et son message", " · each with its source and its message"), ("➤ Envoyer à tous", "➤ Send to all"), ("12 envoyées", "12 sent"),
 ("AUTOUR DE TOI · 2 KM", "AROUND YOU · 2 KM"), ("'Réalisateur'", "'Director'"), ("'Designer produit'", "'Product designer'"), ("PERSO </span>", "PERSONAL </span>"), ("POURQUOI ${p[0]", "WHY ${p[0]"),
 ("'Même vision du produit','Vous vous complétez : design ↔ code','Disponible cette semaine'", "'Same product vision','You complement each other: design ↔ code','Available this week'"), ("Proposer une chambre", "Propose a room"),
 ("'Ton univers.'", "'Your universe.'"), ("'Ta volonté.'", "'Your will.'"),
 ("MUSIQUE · ", "MUSIC · "),
]
for fr, en in PAIRS:
    if fr not in s: print('NOT FOUND:', fr); sys.exit(1)
    s = s.replace(fr, en)
# the real profile page is French: its text is translated inside the frames
EN_PATCH = """d.documentElement.style.cursor='none';
  const bar=d.querySelectorAll('.bar span');if(bar.length>1){bar[0].textContent='Aiwa · desk';bar[1].textContent='2026 · online'}
  const sy=d.querySelector('.say');if(sy)sy.innerHTML='I build <b>Aiwa</b>: an assistant that lives on the phone, talks to Claude, makes sites, videos, pages and apps by voice, builds agents, builds itself and develops an identity and an intimacy, through your loops.';
  const dk=d.querySelectorAll('.dock .cell');[['Source','the Aiwa repository'],['Yellow paper','how it works'],['Value','the ontology of value']].forEach((c,j)=>{if(dk[j]){dk[j].querySelector('b').textContent=c[0];dk[j].querySelector('span').textContent=c[1]}});"""
K = "d.documentElement.style.cursor='none';"
if s.count(K) != 1: print('NOT FOUND: cursor marker', s.count(K)); sys.exit(1)
s = s.replace(K, EN_PATCH)
open(os.path.join(HERE, 'ui13_en.html'), 'w').write(s); print('ui13_en.html', len(s))
