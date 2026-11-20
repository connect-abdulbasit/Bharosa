"""TODO(Ali): run classifier, matching and decide on ai/data/ and write eval_results.json.

Output must satisfy contracts.schemas.EvalResults. Cost model: wrong approval = 10,
wrong rejection = 5, human review = 1.
"""
import json
import sys


def main() -> int:
    # TODO(Ali): load ai/data/*.jsonl, run AI functions, compute metrics + total_cost.
    json.dump({"todo": "TODO(Ali)"}, open("eval_results.json", "w"))
    print("eval not implemented yet (TODO(Ali))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
