from pathlib import Path
from django.conf import settings
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Module-level singleton — built once per Django worker process.
_vectorstore = None


def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )


def _build_vectorstore() -> FAISS:
    kb_dir = settings.KNOWLEDGE_BASE_DIR
    md_files = list(kb_dir.glob("**/*.md"))
    if not md_files:
        raise RuntimeError(
            f"No .md files found in {kb_dir}. "
            "Add at least one Markdown file to the knowledge_base/ directory."
        )

    docs = []
    for path in md_files:
        docs.extend(TextLoader(str(path), encoding="utf-8").load())

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    return FAISS.from_documents(chunks, _get_embeddings())


def _get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _build_vectorstore()
    return _vectorstore


def answer_question(question: str) -> dict:
    """Return the answer and retrieved source snippets."""
    vectorstore = _get_vectorstore()
    retriever   = vectorstore.as_retriever(search_kwargs={"k": 3})

    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )

    prompt = ChatPromptTemplate.from_template(
        "You are an assistant for question-answering tasks. "
        "Use ONLY the context below to answer. "
        "If the answer is not in the context, say 'I don't know based on the provided documents.'\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}\n\n"
        "Answer:"
    )

    def _format_docs(docs):
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    chain = (
        {"context": retriever | _format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    answer   = chain.invoke(question)
    sources  = retriever.invoke(question)
    snippets = [doc.page_content[:200] for doc in sources]
    return {"answer": answer, "snippets": snippets}
