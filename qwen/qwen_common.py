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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# run target: which model, and which output tree it writes to
# ---------------------------------------------------------------------------
# The defaults reproduce the original Qwen3.6 run exactly: model
# Qwen/Qwen3.6-35B-A3B writing under results/qwen36/.  A second model is run by
# naming it and giving it its own tag, e.g.
#     --model Qwen/Qwen3.5-9B --run-tag qwen35_9b   ->  results/qwen35_9b/
# The run tag only selects a directory; it never reaches a prompt or a label.
DEFAULT_MODEL = "Qwen/Qwen3.6-35B-A3B"
DEFAULT_RUN_TAG = "qwen36"
RUN_TAG_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def check_run_tag(run_tag):
    if not RUN_TAG_OK.match(run_tag or ""):
        raise SystemExit("--run-tag must match %s (got %r)"
                         % (RUN_TAG_OK.pattern, run_tag))
    return run_tag


def out_root(run_tag):
    return os.path.join(ROOT, "results", check_run_tag(run_tag))


def raw_dir(run_tag, cond):
    return os.path.join(out_root(run_tag), "%s_raw" % cond.lower())


def result_path(run_tag, cond, instance_id):
    return os.path.join(raw_dir(run_tag, cond), "%d.json" % instance_id)


def model_label(model_id):
    """'Qwen/Qwen3.6-35B-A3B' -> 'qwen3.6-35b-a3b' (the label used for scoring).

    Chosen so the default model reproduces the label the pipeline already used.
    """
    return str(model_id).rsplit("/", 1)[-1].lower()


def add_target_args(ap, reads_only=False):
    """--model / --run-tag, defined once and shared by every entry point.

    reads_only=True is for tools that do not call the model (the collector).
    There --model is optional: when given it is cross-checked against the model
    id already recorded in the raw files, and when omitted the label is derived
    from those files, so the collector never has to be told which model ran.
    """
    if reads_only:
        ap.add_argument("--model", default=None,
                        help="optional: cross-check that the raw files were "
                             "produced by this model, and use it for the "
                             "scoring label (default: derive from the raw files)")
    else:
        ap.add_argument("--model", default=DEFAULT_MODEL,
                        help="model id sent to the server and recorded in every "
                             "result (default: %s)" % DEFAULT_MODEL)
    ap.add_argument("--run-tag", type=check_run_tag, default=DEFAULT_RUN_TAG,
                    help="output tree results/<run-tag>/ (default: %s)"
                         % DEFAULT_RUN_TAG)

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


def _request(base_url, payload, timeout):
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json",
                 # vLLM ignores the key but the OpenAI schema wants the header
                 "Authorization": "Bearer " + os.environ.get("VLLM_API_KEY", "EMPTY")},
        method="POST")
    return url, req


def _stream_completion(base_url, payload, timeout):
    """Consume the SSE stream and rebuild the non-streaming response shape.

    A gateway that proxies the model can time out and answer 502 while the
    model is still in a long thinking phase, because nothing crosses the
    connection until the whole completion is ready.  Streaming keeps the
    connection fed, so this is the only way to get a long generation through
    one.  The reassembled object is returned in the same shape the
    non-streaming path produces, and carries reassembled_from_stream so a
    reader of the stored result can tell how it was obtained.
    """
    url, req = _request(base_url, payload, timeout)
    content, reasoning = [], []
    usage, finish, ident, model, chunks = None, None, None, None, 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    ch = json.loads(data)
                except ValueError:
                    raise ApiError("stream chunk was not JSON: %r" % data[:300])
                chunks += 1
                ident = ch.get("id") or ident
                model = ch.get("model") or model
                if ch.get("usage"):
                    usage = ch["usage"]
                for c in ch.get("choices") or []:
                    d = c.get("delta") or {}
                    if d.get("content"):
                        content.append(d["content"])
                    # servers differ: vLLM emits reasoning_content, the SPIKE
                    # gateway emits reasoning. Take whichever arrives.
                    if d.get("reasoning"):
                        reasoning.append(d["reasoning"])
                    if d.get("reasoning_content"):
                        reasoning.append(d["reasoning_content"])
                    if c.get("finish_reason"):
                        finish = c["finish_reason"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        raise ApiError("HTTP %s from %s: %s" % (e.code, url, detail))
    except ApiError:
        raise
    except Exception as e:                                   # noqa: BLE001
        raise ApiError("%s: %s" % (type(e).__name__, e))

    message = {"role": "assistant", "content": "".join(content)}
    if reasoning:
        message["reasoning"] = "".join(reasoning)
    return {"id": ident, "object": "chat.completion", "model": model,
            "choices": [{"index": 0, "message": message,
                         "finish_reason": finish}],
            "usage": usage,
            "reassembled_from_stream": True,
            "stream_chunks": chunks}


def chat_completion(base_url, payload, timeout=1800):
    """POST /chat/completions and return the parsed response dict."""
    if payload.get("stream"):
        return _stream_completion(base_url, payload, timeout)
    url, req = _request(base_url, payload, timeout)
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
        # Streaming changes nothing about what the model computes; it only
        # keeps the connection fed so a proxying gateway does not time out
        # mid-generation. The reassembled response has the same shape.
        "stream": bool(gen.get("stream")),
    }
    if payload["stream"]:
        payload["stream_options"] = {"include_usage": True}
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
