# _lessons_texts — Document Root for the Agentic RAG Agent

This directory is the knowledge base searched by the **Season 2, Lesson 01** agent
(`module_02_01`).

## How to populate

Place your AI_Devs 4 course material files here. The agent expects Markdown (`.md`)
or plain-text (`.txt`) files. The spec names them `S01*.md` — e.g.:

```
_lessons_texts/
  S01E01.md
  S01E02.md
  S01E03.md
  ...
```

## Agent behaviour

The agent will:
1. `list_directory` to discover the file tree.
2. `search_text` with Polish keywords to find relevant lines.
3. `read_file_fragment` to read only the specific line ranges that matter.
4. Synthesise an answer in English with explicit source citations.

## Security

All tool calls are sandboxed to this directory. Any path that resolves outside
`_lessons_texts/` is rejected with a `PermissionError`.

## Override

To use a different directory, set the `LESSONS_TEXTS_DIR` environment variable
to an absolute path, or update `LESSONS_TEXTS_DIR` in `operation_center/settings.py`.
