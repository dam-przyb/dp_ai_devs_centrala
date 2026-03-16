# AI Devs Course Knowledge Base

## About This Application
This is Damian's Operation Center — a unified dashboard for running AI experiments.
It is built with Django, HTMX, and Tailwind CSS.

## LLM Interaction Basics
- A **prompt** is the instruction you send to an LLM.
- A **system message** sets the LLM's persona and constraints.
- **Temperature** controls randomness: 0 = deterministic, 1 = creative.
- **Context window** limits how much conversation history the model can "see".

## RAG — Retrieval-Augmented Generation
RAG improves LLM answers by fetching relevant documents before calling the model.
Steps:
1. Load and split documents into chunks.
2. Embed chunks and store in a vector database.
3. At query time, retrieve the most similar chunks.
4. Inject retrieved text into the prompt as context.

## Tool Use
LLMs can call external Python functions (tools) to fetch real-world data.
The model decides *when* to call a tool and *with what arguments*.
The result is fed back to the model to generate the final answer.

## Model Context Protocol (MCP)
MCP is a standard protocol for exposing tools to LLMs over stdio.
An MCP server exposes `list_tools` and `call_tool` endpoints.
