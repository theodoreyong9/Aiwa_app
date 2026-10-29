# Apps

Une application qui s'installe ou s'ouvre sur le téléphone.

- Le plus simple d'abord : une app web d'un seul fichier (voir `skills/page`) si elle n'a pas besoin d'Android.
- Pour une vraie application Android : un `.apk` signé (clé de debug acceptée), construit par la CI du dépôt ou localement, attaché à la release.
- Dis en une phrase ce que fait l'app et comment l'ouvrir ; l'installation demande l'autorisation « sources inconnues ».
- Teste ce qui peut l'être (compilation, tests) avant de publier ; dis honnêtement ce qui n'a pas pu être essayé.
- Publie selon `skills/release/SKILL.md` avec le tag `app-…`.
