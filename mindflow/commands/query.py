"""
`query` command
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional, Tuple

import sys
import numpy as np

from mindflow.db.objects.document import Document, DocumentReference
from mindflow.db.objects.model import Model
from mindflow.resolving.resolve import resolve_all

from mindflow.utils.response import handle_response_text


def query(document_paths: List[str], query: str, completion_model: bool, embedding_model: Model) -> str:
    """
    This function is used to ask a custom question about files, folders, and websites.
    """
    document_references: List[DocumentReference] = resolve_all(document_paths)
    response = completion_model.prompt(
        query,
        select_content(query, document_references, embedding_model),
    )
    handle_response_text(response)


def select_content(query: str, document_references: List[DocumentReference], embedding_model: Model) -> str:
    """
    This function is used to generate a prompt based on a question or summarization task
    """
    embedding_ranked_document_chunks: List[
        Tuple(DocumentChunk, float)
    ] = rank_document_chunks_by_embedding(query, document_references, embedding_model)
    if len(embedding_ranked_document_chunks) == 0:
        print(
            "No index for requested hashes. Please generate index for passed content."
        )
        sys.exit(1)

    selected_content = trim_content(embedding_ranked_document_chunks)

    return selected_content

class DocumentChunk:
    """
    This class is used to store the chunks of a document.
    """

    def __init__(
        self, path: str, start: int, end: int, embedding: Optional[np.ndarray] = None
    ):
        self.path = path
        self.start = start
        self.end = end
        self.embedding = embedding

    @classmethod
    def from_search_tree(
        cls,
        document: Document,
        embedding_model: Model,
    ) -> Tuple[List["DocumentChunk"], List[np.ndarray]]:
        """
        This function is used to split the document into chunks.
        """

        stack = [document.search_tree]
        chunks: List["DocumentChunk"] = [
            cls(
                document.path,
                document.search_tree["start"],
                document.search_tree["end"],
            )
        ]
        embeddings: List[np.ndarray] = [embedding_model.embed(document.search_tree["summary"])]
        rolling_summary: List[str] = []
        while stack:
            node = stack.pop()
            rolling_summary.append(node["summary"])
            if node["leaves"]:
                for leaf in node["leaves"]:
                    stack.append(leaf)
                    chunks.append(cls(document.path, leaf["start"], leaf["end"]))
                    rolling_summary_embedding = embedding_model.embed(
                        "\n\n".join(rolling_summary) + "\n\n" + leaf["summary"],
                    )
                    embeddings.append(rolling_summary_embedding)
            rolling_summary.pop()

        return chunks, embeddings


def trim_content(ranked_document_chunks: List[DocumentChunk], token_limit: int) -> str:
    """
    This function is used to select the most relevant content for the prompt.
    """
    selected_content: str = ""
    char_limit: int = token_limit * 3

    for document_chunk in ranked_document_chunks:
        if document_chunk:
            with open(document_chunk.path, "r", encoding="utf-8") as file:
                file.seek(document_chunk.start)
                text = file.read(document_chunk.end - document_chunk.start)
                if len(selected_content + text) > char_limit:
                    selected_content += text[: char_limit - len(selected_content)]
                    break
                selected_content += text

    return selected_content


def rank_document_chunks_by_embedding(query: str, document_references: List[DocumentReference], embedding_model: Model) -> List[DocumentChunk]:
    """
    This function is used to select the most relevant content for the prompt.
    """
    prompt_embeddings = np.array(embedding_model.embed(query)).reshape(1, -1)

    ranked_document_chunks = []
    for i in range(0, len(document_references), 100):
        document_ids = [
            document.id for document in document_references[i : i + 100]
        ]
        documents: List[Optional[Document]] = Document.load_bulk(document_ids)
        documents = [document for document in documents if document]
        if documents == []:
            continue
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [
                executor.submit(DocumentChunk.from_search_tree, document)
                for document in documents 
            ]
            for future in as_completed(futures):
                document_chunks, document_chunk_embeddings = future.result()
                similarities = cosine_similarity(
                    prompt_embeddings, document_chunk_embeddings
                )[0]
                ranked_document_chunks.extend(list(zip(document_chunks, similarities)))

    ranked_document_chunks.sort(key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in ranked_document_chunks]
