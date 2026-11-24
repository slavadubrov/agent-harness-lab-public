"""Replay the archived support campaign using only the public evaluation library."""

import json
from pathlib import Path

from harness_evals import comparable, compare, comparison, failures, load, summarize, table

from loop.grading import usecase

SAVED = Path(__file__).resolve().parents[1] / "reports" / "part-5" / "support"


def main() -> None:
    uc = usecase()
    config = json.loads((SAVED / "campaign.json").read_text())
    rows = [json.loads(line) for line in (SAVED / "ledger.jsonl").read_text().splitlines() if line]
    result = json.loads((SAVED / "result.json").read_text())
    final_id = result["final"]
    groups = {}
    print(f"Support campaign {config['usecase_version']} regraded with {uc.version}.")

    batches: list[tuple[str, str, Path]] = []
    for row in rows:
        cid = row["id"]
        if row.get("dev") is not None or row["parent"] is None:
            batches.append((cid, "dev", SAVED / "candidates" / cid / "dev"))
        if row.get("val") is not None or row["parent"] is None:
            batches.append((cid, "val", SAVED / "candidates" / cid / "val"))
    batches.append(("000", "noise", SAVED / "candidates" / "000" / "val-again"))
    test_ids = ["000"] if final_id == "000" else ["000", final_id]
    batches.extend((cid, "test", SAVED / "test" / cid) for cid in test_ids)

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

    noise = compare(
        uc, groups["000", "val"], groups["000", "noise"], step=True, level=config["level"]
    )
    print(f"\nSame starting harness\n{comparison(noise)}")

    for row in rows[1:]:
        cid, parent = row["id"], row["parent"]
        label = f"Candidate {int(cid)} against parent {parent}"
        if row["decision"] in ("invalid", "error"):
            print(f"\n{label}\nRecorded {row['decision']}: {'; '.join(row['reasons'])}")
            continue
        if (cid, "val") not in groups:
            before = summaries[parent, "dev"]["success"]
            after = summaries[cid, "dev"]["success"]
            print(f"\n{label}\nScreened on development ({before:.3f} to {after:.3f}).")
            continue
        if config["screen"]:
            before = summaries[parent, "dev"]["success"]
            after = summaries[cid, "dev"]["success"]
            if after <= before:
                print(f"\n{label}\nScreened on development ({before:.3f} to {after:.3f}).")
                continue
        decision = compare(
            uc, groups[parent, "val"], groups[cid, "val"], step=True, level=config["level"]
        )
        print(f"\n{label}\n{comparison(decision)}")

    if final_id != "000":
        test_decision = compare(
            uc, groups["000", "test"], groups[final_id, "test"], step=True, level=config["level"]
        )
        print(f"\nTest\n{comparison(test_decision)}")

    print(f"\nTest runs passed by request type (start, {final_id})")
    for tag in sorted({t.tags[0] for t in uc.split("test")}):
        ids = {t.id for t in uc.split("test") if t.tags[0] == tag}
        counts = []
        for cid in test_ids:
            selected = [g for g in groups[cid, "test"] if g.episode.task_id in ids]
            counts.append(f"{sum(g.passed for g in selected)}/{len(selected)}")
        print(f"{tag}: {', '.join(counts)}")
    print(f"\nDevelopment tasks still failing in the recorded final harness ({final_id}):")
    print("\n".join(sorted(failures(groups[final_id, "dev"]))) or "(none)")


if __name__ == "__main__":
    main()
