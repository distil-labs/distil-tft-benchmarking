import argparse
import json
import re
from pathlib import Path

CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(text: str) -> str:
    return CONTROL_CHAR_RE.sub("", text)


def clean_messages(messages: list[dict]) -> list[dict]:
    cleaned = []
    for msg in messages:
        new_msg = {"role": msg["role"]}
        if "content" in msg and msg["content"] is not None:
            new_msg["content"] = clean(msg["content"])
        if "tool_calls" in msg:
            new_msg["content"] = ""
            new_msg["tool_calls"] = []
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                args = fn["arguments"]
                if isinstance(args, str):
                    args_obj = json.loads(args)
                else:
                    args_obj = args
                new_msg["tool_calls"].append(
                    {
                        "type": "function",
                        "function": {
                            "name": fn["name"],
                            "arguments": args_obj,
                        },
                    }
                )
        cleaned.append(new_msg)
    return cleaned


def main(input_path: str, output_path: str) -> None:
    in_path = Path(input_path)
    out_path = Path(output_path)
    n_in, n_out = 0, 0
    with in_path.open() as fin, out_path.open("w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            n_in += 1
            record = json.loads(line)
            inner = json.loads(record["context"])
            messages = clean_messages(inner["messages"])
            assert messages, f"empty messages on record {n_in}"
            out_line = json.dumps({"messages": messages}, ensure_ascii=True)
            assert "\u2028" not in out_line and "\u2029" not in out_line
            fout.write(out_line + "\n")
            n_out += 1
    print(f"converted {n_in} traces -> {n_out} lines written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(input_path=args.input, output_path=args.output)
