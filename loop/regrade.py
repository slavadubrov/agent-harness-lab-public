"""Replay the archived support campaign using only the public evaluation library."""

import json
from pathlib import Path

from harness_evals import comparable, compare, comparison, failures, load, summarize, table

from loop.grading import usecase

SAVED = Path(__file__).resolve().parents[1] / "reports" / "part-5" / "support"


def main() -> None:
    uc = usecase()
    config = json.loads((SAVED / "campaign.json").read_text())
    groups = {}
    print(f"Support campaign {config['usecase_version']} regraded with {uc.version}.")
    # These are the nine batches the recorded campaign actually ran. An absent file
    # must stop the regrade instead of removing tasks from a reported result.
    batches = [
        (cid, split, SAVED / "candidates" / cid / split)
        for cid in ("000", "001", "002")
        for split in ("dev", "val")
    ]
    batches.append(("000", "noise", SAVED / "candidates" / "000" / "val-again"))
    batches.extend((cid, "test", SAVED / "test" / cid) for cid in ("000", "002"))
    for cid, group, folder in batches:
        split = "val" if group == "noise" else group
        manifest = json.loads((folder / "manifest.json").read_text())
        comparable(
            manifest, config | {"split": split, "fingerprint": config["fingerprints"][split]}
        )
        if manifest["trials"] != config["trials"][split] or manifest["harnesses"] != [cid]:
            raise ValueError(f"{folder}: unexpected harness or trial count")
        episodes = load(folder / "episodes.jsonl")
        expected = {(cid, t.id, i) for t in uc.split(split) for i in range(config["trials"][split])}
        observed = {(e.harness, e.task_id, e.trial) for e in episodes}
        if len(episodes) != len(expected) or observed != expected:
            raise ValueError(f"{folder}: missing, duplicate or unexpected episode")
        groups[cid, group] = uc.grade(episodes)

    summaries = {key: summarize(grades, uc.metrics) for key, grades in groups.items()}
    print(table({f"{cid} {split}": summary for (cid, split), summary in summaries.items()}))
    for label, base, candidate in [
        ("Same starting harness", ("000", "val"), ("000", "noise")),
        ("First proposal against its recorded parent", ("000", "val"), ("001", "val")),
        ("Second proposal against its recorded parent", ("000", "val"), ("002", "val")),
        ("Test", ("000", "test"), ("002", "test")),
    ]:
        if candidate[1] == "val" and config["screen"]:
            before = summaries[base[0], "dev"]["success"]
            after = summaries[candidate[0], "dev"]["success"]
            if after <= before:
                print(f"\n{label}\nScreened on development ({before:.3f} to {after:.3f}).")
                continue
        decision = compare(uc, groups[base], groups[candidate], step=True, level=config["level"])
        print(f"\n{label}\n{comparison(decision)}")
    print("\nTest runs passed by request type (start, final)")
    for tag in sorted({t.tags[0] for t in uc.split("test")}):
        ids = {t.id for t in uc.split("test") if t.tags[0] == tag}
        counts = []
        for cid in ("000", "002"):
            selected = [g for g in groups[cid, "test"] if g.episode.task_id in ids]
            counts.append(f"{sum(g.passed for g in selected)}/{len(selected)}")
        print(f"{tag}: {', '.join(counts)}")
    print("\nDevelopment tasks still failing in the recorded final harness:")
    print("\n".join(sorted(failures(groups["002", "dev"]))))


if __name__ == "__main__":
    main()
