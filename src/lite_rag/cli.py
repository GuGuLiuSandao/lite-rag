from __future__ import annotations

import argparse
import sys

from .config import LiteRAGConfig, load_environment
from .store import LiteRAGStore
from .utils import dump_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lite-rag")
    subparsers = parser.add_subparsers(dest="command", required=True)

    kb_parser = subparsers.add_parser("kb")
    kb_subparsers = kb_parser.add_subparsers(dest="kb_command", required=True)

    kb_create = kb_subparsers.add_parser("create")
    kb_create.add_argument("--name", required=True)
    kb_create.add_argument("--description")

    kb_list = kb_subparsers.add_parser("list")
    kb_list.add_argument("--name")

    kb_get = kb_subparsers.add_parser("get")
    kb_get.add_argument("--kb", required=True)

    kb_update = kb_subparsers.add_parser("update")
    kb_update.add_argument("--kb", required=True)
    kb_update.add_argument("--name")
    kb_update.add_argument("--description")

    kb_delete = kb_subparsers.add_parser("delete")
    kb_delete.add_argument("--kb", required=True)

    file_parser = subparsers.add_parser("file")
    file_subparsers = file_parser.add_subparsers(dest="file_command", required=True)

    file_add = file_subparsers.add_parser("add")
    file_add.add_argument("--kb", required=True)
    file_add.add_argument("--path", required=True)
    file_add.add_argument("--title")

    file_list = file_subparsers.add_parser("list")
    file_list.add_argument("--kb")

    file_get = file_subparsers.add_parser("get")
    file_get.add_argument("--file-id", required=True)

    file_update = file_subparsers.add_parser("update")
    file_update.add_argument("--file-id", required=True)
    file_update.add_argument("--path")
    file_update.add_argument("--title")

    file_delete = file_subparsers.add_parser("delete")
    file_delete.add_argument("--file-id", required=True)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--kb")
    search_parser.add_argument("--file-ids", nargs="*", help="Restrict to these document IDs; an empty list matches nothing")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--mode", choices=["vector", "fts", "hybrid"])
    search_parser.add_argument("--recall-top-k", type=int, default=20)
    search_parser.add_argument("--final-top-k", type=int, default=5)

    return parser


def run(args: argparse.Namespace) -> object:
    config = LiteRAGConfig.from_env()
    store = LiteRAGStore(config)

    if args.command == "kb":
        if args.kb_command == "create":
            return store.create_kb(name=args.name, description=args.description)
        if args.kb_command == "list":
            items = store.list_kbs()
            if args.name:
                return [item for item in items if item["name"] == args.name]
            return items
        if args.kb_command == "get":
            return store.get_kb(args.kb)
        if args.kb_command == "update":
            return store.update_kb(args.kb, name=args.name, description=args.description)
        if args.kb_command == "delete":
            return store.delete_kb(args.kb)

    if args.command == "file":
        if args.file_command == "add":
            return store.add_file(kb_ref=args.kb, source_path=args.path, title=args.title)
        if args.file_command == "list":
            return store.list_files(kb_ref=args.kb)
        if args.file_command == "get":
            return store.get_file(args.file_id)
        if args.file_command == "update":
            return store.update_file(args.file_id, source_path=args.path, title=args.title)
        if args.file_command == "delete":
            return store.delete_file(args.file_id)

    if args.command == "search":
        return store.search(
            query=args.query,
            kb_ref=args.kb,
            file_ids=args.file_ids,
            mode=args.mode,
            recall_top_k=args.recall_top_k,
            final_top_k=args.final_top_k,
        )

    raise ValueError("Unsupported command")


def main() -> None:
    load_environment()
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(dump_json({"ok": False, "error": str(exc)}))
        raise SystemExit(1) from exc

    print(dump_json({"ok": True, "result": result}))


if __name__ == "__main__":
    main()
