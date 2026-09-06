"""Upload an export_to_docent.py dump into a Docent collection.

The dump is already one JSON object per agent run, so this only has to convert
each into the SDK's objects and send it. The one decision that matters is the
assistant message: its content stays a list of blocks, so the reasoning trace
remains a first-class reasoning block instead of being concatenated into the
answer. The whole point of this collection is to cluster on how a run reasoned,
and flattening would make "how it got there" indistinguishable from "what it
finally said".

Usage
  python ingest_docent.py --data <dump.json> --name tsrbench-160-qwen36-full
  python ingest_docent.py --data <dump.json> --collection-id <id>   # add to existing
  python ingest_docent.py --data <dump.json> --check-only           # convert, do not upload
"""
import argparse
import io
import json
import os


def load(path):
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit("expected a JSON array of agent runs, got %s"
                         % type(data).__name__)
    return data


def to_agent_run(rec):
    from docent.data_models import AgentRun, Transcript
    from docent.data_models.chat import parse_chat_message
    msgs = [parse_chat_message(m) for m in rec["transcripts"][0]["messages"]]
    return AgentRun(transcripts=[Transcript(messages=msgs)],
                    metadata=rec["metadata"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True)
    ap.add_argument("--name", default="tsrbench-160-qwen36-full")
    ap.add_argument("--description", default=(
        "TSRBench-160 FULL condition. Qwen3.6-35B-A3B orders 6-8 GDELT news "
        "events chronologically from the events, a GoldsteinScale series, and "
        "the event timestamps given in a stated random order with no "
        "event-to-time mapping. Greedy decoding, frozen prompts verified "
        "against their build-time hashes."))
    ap.add_argument("--collection-id", default=None)
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--batch", type=int, default=100)
    args = ap.parse_args()

    records = load(args.data)
    print("source records: %d" % len(records))

    runs, failures = [], []
    for i, rec in enumerate(records):
        try:
            runs.append(to_agent_run(rec))
        except Exception as e:                                   # noqa: BLE001
            failures.append((i, rec.get("metadata", {}).get("instance_id"),
                             "%s: %s" % (type(e).__name__, e)))
    print("converted: %d   failed: %d" % (len(runs), len(failures)))
    for i, iid, err in failures[:10]:
        print("  record %d (instance %s): %s" % (i, iid, err))
    if failures:
        raise SystemExit("conversion failures; nothing uploaded")

    try:
        from docent.data_models.chat.checks import check_agent_runs
        report = check_agent_runs(runs)
        print("sanity check:")
        print(report if isinstance(report, str)
              else json.dumps(report, indent=2, default=str)[:4000])
    except ImportError as e:                                     # noqa: BLE001
        print("sanity check unavailable in this SDK build (%s)" % e)

    if args.check_only:
        print("check-only: nothing uploaded")
        return

    from docent import Docent
    client = Docent(api_key=os.environ.get("DOCENT_API_KEY"))
    cid = args.collection_id or client.create_collection(
        name=args.name, description=args.description)
    print("collection: %s" % cid)

    sent = 0
    for i in range(0, len(runs), args.batch):
        chunk = runs[i:i + args.batch]
        client.add_agent_runs(cid, chunk)
        sent += len(chunk)
        print("  uploaded %d/%d" % (sent, len(runs)))
    print("done. uploaded %d agent runs to collection %s" % (sent, cid))


if __name__ == "__main__":
    main()
