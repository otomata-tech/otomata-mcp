"""La PORTE D'ENTRÉE du socle : le texte d'instructions serveur (champ `instructions`
du `InitializeResult`). Le consommateur le compose avec ses instructions métier ;
peut aussi être réécrit par identité via un middleware on_initialize (cf. README)."""

SERVER_INSTRUCTIONS = """\
Ce serveur expose son savoir-faire EN TOOLS (pas de resource ni de prompt) — donc tout accès est tracé.

1. Appelle `readme_agent()` EN PREMIER : il renvoie la doctrine de base (contrat, conventions) ET l'index des instructions disponibles.
2. Charge une instruction au besoin : `list_instructions(kind?)` pour l'index, puis `get_instruction(kind, slug)` pour le corps.
3. Encadre toute procédure : `run_start(label, doctrine?)` … `run_finish(run_id, outcome)` — les appels intermédiaires sont corrélés (run_id) et journalisés.
4. Écrire une instruction (`set_instruction`) est réservé aux admins et REFUSÉ si le contenu cite un nom de personne/client.
"""
