# Le cerveau

Un petit serveur HTTP local (127.0.0.1:8787) qui tient l'état d'Aiwa et pilote Claude. Il tourne dans Termux (Ubuntu via proot).

```
python3 -m aiwa_brain        # depuis ce dossier
python3 -m unittest discover -s tests -t .
```

Un module par domaine (voir `ARCHITECTURE.md`) ; `server.py` ne fait que router, `state.py` tient tout l'état partagé, `config.py` toutes les constantes.
Les fichiers de la personne restent dans son dossier personnel, sous les mêmes noms qu'avant (`~/.aiwa_state.json`, `~/.aiwa_cloud_sessions.json`…) : un téléphone qui a déjà Aiwa garde ses sessions.

Les modules `*_lib.py` sont purs (données en entrée, texte ou données en sortie) : les textes du super agent, des scénarios, de la chambre, du profil et le mode volée s'y lisent et s'y testent sans réseau.
