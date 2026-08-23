"""Shared helpers for the Qwen3.6 Paper50 runs: transport, field extraction, hashing.

Deliberately dependency-free - urllib from the standard library, no `openai`
package - so the same file works on a Snellius compute node with no pip install
and so the returned message object can be inspected as a plain dict rather than
through a client wrapper that may rename fields between versions.

Nothing here reads or writes anything belonging to the Sonnet experiment.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.request

# vLLM exposes the thinking trace under a field whose name has changed across
# releases.  Rather than assume one, probe in order and record which was used.
REASONING_KEYS = ("reasoning_content", "reasoning", "thinking",
                  "reasoning_text", "thought")
THINK_TAG = re.compile(r"<think>(.*?)</think>\s*", re.S)


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_prompt(path):
    """Read a frozen prompt file byte-for-byte (no newline translation)."""
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def load_index(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class ApiError(RuntimeError):
    pass


def chat_completion(base_url, payload, timeout=1800):
    """POST /chat/completions and return the parsed response dict."""
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json",
                 # vLLM ignores the key but the OpenAI schema wants the header
                 "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "EMPTY")},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        raise ApiError("HTTP %s from %s: %s" % (e.code, url, detail))
    except Exception as e:                                   # noqa: BLE001
        raise ApiError("%s: %s" % (type(e).__name__, e))
    try:
        return json.loads(raw)
    except ValueError:
        raise ApiError("response was not JSON: %r" % raw[:500])


def split_message(message):
    """-> (reasoning, content, reasoning_source).

    Priority: an explicit reasoning field from the server's reasoning parser.
    Fallback: a <think>...</think> block still embedded in content, which means
    the server was started without --reasoning-parser.  In that case the two are
    still separated here and the source is recorded, never concatenated.
    """
    if not isinstance(message, dict):
        return None, None, "message_not_a_dict"
    for key in REASONING_KEYS:
        val = message.get(key)
        if isinstance(val, str) and val.strip():
            return val, message.get("content"), key
    content = message.get("content")
    if isinstance(content, str):
        m = THINK_TAG.search(content)
        if m:
            return (m.group(1),
                    THINK_TAG.sub("", content, count=1),
                    "parsed_from_<think>_tag_in_content")
    return None, content, "absent"


def message_field_names(message):
    """Every key the server actually returned, so the run can be audited."""
    return sorted(message.keys()) if isinstance(message, dict) else []


def build_payload(model, system_prompt, user_prompt, gen):
    """The exact request body.  Every generation parameter is explicit."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": gen["temperature"],
        "top_p": gen["top_p"],
        "max_tokens": gen["max_tokens"],
        "stream": False,
    }
    if gen.get("seed") is not None:
        payload["seed"] = gen["seed"]
    if gen.get("presence_penalty") is not None:
        payload["presence_penalty"] = gen["presence_penalty"]
    # Thinking is ON by default for Qwen3 served with --reasoning-parser qwen3.
    # enable_thinking=False is never sent.  The kwarg is only added when asked
    # for explicitly, because a server whose chat template does not accept it
    # will reject the whole request.
    if gen.get("send_enable_thinking_kwarg"):
        payload["chat_template_kwargs"] = {"enable_thinking": True}
    return payload


def result_record(instance_id, condition, model, index_entry, prompt_path,
                  system_prompt_path, prompt_text, system_text, payload,
                  response, started_utc, finished_utc, gen):
    """The structured per-instance file.  Nothing is truncated."""
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    reasoning, content, source = split_message(message)
    finish_reason = choice.get("finish_reason")
    return {
        "instance_id": instance_id,
        "condition": condition,
        "model": model,
        "reasoning": reasoning,
        "content": content,
        "finish_reason": finish_reason,
        "truncated": finish_reason == "length",
        "reasoning_source": source,
        "message_fields_returned": message_field_names(message),
        "gold_answer": index_entry.get("gold_answer"),
        "ticker": index_entry.get("ticker"),
        "prompt_file": prompt_path,
        "prompt_sha256": sha256_text(prompt_text),
        "system_prompt_file": system_prompt_path,
        "system_prompt_sha256": sha256_text(system_text),
        "generation": dict(gen),
        "usage": response.get("usage"),
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "api_response": response,
    }
