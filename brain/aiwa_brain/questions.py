"""A question put to the super agent: it answers in words to be spoken, from everything it knows."""
import json
import re
import subprocess
import threading
import time

from . import agent, config, github, relay, state


ANSWER_SYSTEM = (
    "Tu es le super agent d'Aiwa. Tu PARLES à la personne, à voix haute, comme un ami posé et chaleureux au téléphone : jamais comme un texte écrit. "
    "Français parlé : phrases courtes, contractions naturelles (« t'as », « y'a », « c'est »), petits liens (« alors », « du coup », « en fait »), parfois une relance brève. "
    "Commence par une première phrase très courte qui répond au plus vite, puis complète en deux à quatre phrases au plus. "
    "Écris POUR L'OREILLE : aucune liste, aucun symbole, aucune parenthèse, aucune mise en forme, aucune abréviation ni sigle à épeler ; les nombres en toutes lettres ; "
    "la ponctuation fait les pauses (virgules, points). Appuie-toi sur le contexte fourni (le dépôt de la personne, sa dernière demande, la conversation en cours) et enchaîne naturellement, sans te répéter ni te présenter ; "
    "si tu ne sais pas, dis-le simplement, n'invente rien. Tu ne fais rien, tu réponds seulement."
)


def conversation_text(now=None):
    """The talk so far as lines for the prompt, or ''."""
    now = now or time.time()
    with state.lock:
        if state.conversation and now - state.conversation[-1][0] > config.CONVERSATION_QUIET:
            state.conversation.clear()
        return "\n".join(f"{who} : {text}" for _, who, text in state.conversation[-8:])


def conversation_add(question, answer):
    with state.lock:
        state.conversation.append((time.time(), "Personne", question))
        state.conversation.append((time.time(), "Toi", answer))
        del state.conversation[:-16]


def _answer_context():
    """What the answer may lean on: the point of the super agent (sessions, repositories, productions, scenarios, chamber, what is waiting) and the README of the repository in use."""
    parts = [agent.point()[0]]
    with state.lock:
        repo = state.current_repo
    if repo and github.REPO_RE.fullmatch(repo):
        raw = relay.raw_get(f"{config.RAW_BASE}/{repo}/HEAD/README.md?t={int(time.time())}", 30000)
        if raw:
            parts.append(f"README du dépôt {repo} :\n" + raw.decode("utf-8", "replace")[:6000])
    if state.last_request["text"]:
        parts.append("Dernière demande de la personne à une session : " + state.last_request["text"])
    return "\n\n".join(parts)


def answer_question(question):
    """The super agent answers a QUESTION by itself, in words to be spoken: with the person's own key when there is one, else with the Claude of the phone (`claude -p`, print mode,
    the person's own login, nothing sent to a session). {"ok", "text" | "error"}."""
    q = " ".join(str(question or "").split())[:600]
    if not q:
        return {"ok": False, "error": "question vide"}
    state.style.observe(q)
    context = _answer_context()
    talk = conversation_text()
    if talk:
        context = (context + "\n\n" if context else "") + "La conversation jusqu'ici (continue-la naturellement, sans la répéter) :\n" + talk
    if state.llm.state == "ready":
        text = state.llm.ask(ANSWER_SYSTEM + ("\n\n" + state.style.note() if state.style.note() else "") + ("\n\n" + context if context else ""), [{"role": "user", "content": q}], max_tokens=400)
        if text:
            answer = " ".join(str(text).split())[:900]
            conversation_add(q, answer)
            return {"ok": True, "text": answer}
    prompt = ANSWER_SYSTEM + ("\n\n" + state.style.note() if state.style.note() else "") + ("\n\n" + context if context else "") + "\n\nQuestion : " + q
    last_error = "pas de réponse"
    for extra in (["--model", "haiku"], []):
        try:
            done = subprocess.run(["claude", "-p", "--output-format", "text", *extra], input=prompt, capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.SubprocessError) as err:
            last_error = str(err)
            continue
        out = github.clean(done.stdout or "").strip()
        if done.returncode == 0 and out:
            answer = " ".join(out.split())[:900]
            conversation_add(q, answer)
            return {"ok": True, "text": answer}
        last_error = github.clean((done.stderr or "") + (done.stdout or "")).strip()[-300:] or f"code {done.returncode}"
    return {"ok": False, "error": last_error}


_SENTENCE_END = re.compile(r"(.+?[.!?…])(?:\s+|$)", re.S)


def _sentences_from(buffer, final=False):
    """(complete sentences, what is left): the answer is cut where a sentence ends, so that the voice can start on the first one."""
    out, rest = [], buffer
    while True:
        m = _SENTENCE_END.match(rest)
        if not m or (not final and m.end() == len(rest) and not rest.rstrip().endswith(("." , "!", "?", "…")) ):
            break
        if not final and m.end() == len(rest) and not rest[-1:].isspace():
            break      # the end of the text so far may be mid-sentence ("3." of "3.5"): wait for more
        out.append(" ".join(m.group(1).split()))
        rest = rest[m.end():]
    if final and rest.strip():
        out.append(" ".join(rest.split()))
        rest = ""
    return out, rest


def answer_stream(question, emit):
    """Like answer_question, but each sentence is handed to `emit` as soon as it is written (the Claude of the phone streams its text). Returns True if something was said."""
    q = " ".join(str(question or "").split())[:600]
    if not q:
        return False
    if state.llm.state != "ready":
        state.style.observe(q)      # with the key, answer_question below observes it
    context = _answer_context()
    talk = conversation_text()
    if talk:
        context = (context + "\n\n" if context else "") + "La conversation jusqu'ici (continue-la naturellement, sans la répéter) :\n" + talk
    if state.llm.state == "ready":
        result = answer_question(q)
        if not result.get("ok"):
            return False
        for sentence in _sentences_from(result["text"], final=True)[0]:
            emit(sentence)
        return True
    prompt = ANSWER_SYSTEM + ("\n\n" + state.style.note() if state.style.note() else "") + ("\n\n" + context if context else "") + "\n\nQuestion : " + q
    try:
        proc = subprocess.Popen(["claude", "-p", "--model", "haiku", "--output-format", "stream-json", "--include-partial-messages", "--verbose"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except (OSError, subprocess.SubprocessError):
        return False
    killer = threading.Timer(90, proc.kill)
    killer.start()
    said, buffer, whole = [], "", ""
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            delta = ((event.get("event") or {}).get("delta") or {}) if event.get("type") == "stream_event" else {}
            piece = delta.get("text") if delta.get("type") == "text_delta" else None
            if piece:
                buffer += piece
                whole += piece
                ready, buffer = _sentences_from(buffer)
                for sentence in ready:
                    said.append(sentence)
                    emit(sentence)
            elif event.get("type") == "result" and not whole and isinstance(event.get("result"), str):
                buffer = whole = event["result"]
        ready, buffer = _sentences_from(buffer, final=True)
        for sentence in ready:
            said.append(sentence)
            emit(sentence)
    except (OSError, ValueError):
        pass
    finally:
        killer.cancel()
        try:
            proc.kill()
        except OSError:
            pass
    if said:
        conversation_add(q, " ".join(said)[:900])
    return bool(said)