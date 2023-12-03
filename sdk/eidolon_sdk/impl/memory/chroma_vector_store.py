from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse, parse_qs

import chromadb
from chromadb import Include, QueryResult
from chromadb.api.models.Collection import Collection
from pydantic import BaseModel, Field, field_validator

from eidolon_sdk.vector_store.vector_store import QueryItem, VectorStore
from eidolon_sdk.reference_model import Specable
from eidolon_sdk.util.str_utils import replace_env_var_in_string


class ChromaVectorStoreConfig(BaseModel):
    url: str = Field(description="The url of the chroma database. " +
                                 "Use http(s)://$HOST:$PORT?header1=value1&header2=value2 to pass headers to the database." +
                                 "Use file://$PATH to use a local file database.")

    # noinspection PyMethodParameters,HttpUrlsUsage
    @field_validator("url")
    def validate_url(cls, url):
        if url.startswith("file://"):
            if len(url) < 8:
                raise ValueError("file:// must be followed by a path")

            path = url[7:]
            if len(path) == 0:
                raise ValueError("file:// must be followed by a path")

            # validate path is a file on disk
            value = replace_env_var_in_string(path)
            # Convert the string to a Path object
            path = Path(value).resolve()

            # Check if the path is absolute
            if not path.is_absolute():
                raise ValueError(f"The root_dir must be an absolute path. Received: {path}->{value}")

            return
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("url must start with file://, http://, or https://")


class ChromaVectorStore(VectorStore, Specable[ChromaVectorStoreConfig]):
    spec: ChromaVectorStoreConfig
    client: chromadb.Client

    def __init__(self, spec: ChromaVectorStoreConfig):
        self.spec = spec
        self.client = None

    def start(self):
        self.connect()

    def connect(self):
        url = urlparse(self.spec.url)
        if url.scheme == "file":
            path = url.path
            self.client = chromadb.PersistentClient(path)
        else:
            host = url.hostname
            port = url.port or "8000"
            ssl = url.scheme == "https"
            if url.query and len(url.query) > 0:
                headers = parse_qs(url.query)
            else:
                headers = None
            self.client = chromadb.HttpClient(host=host, port=port, ssl=ssl, headers=headers)

    def stop(self):
        pass

    def _get_collection(self, name: str) -> Collection:
        if not self.client.heartbeat():
            self.connect()

        return self.client.get_or_create_collection(name=name)

    async def add(self, collection: str,
                  docs: List[(str, List[float], dict)],
                  **add_kwargs: Any):
        collection = self._get_collection(name=collection)
        doc_ids = [doc_id for doc_id, _, _ in docs]
        embeddings = [embedding for _, embedding, _ in docs]
        metadata = [md for _, _, md in docs]
        collection.upsert(embeddings=embeddings, ids=doc_ids, metadatas=metadata, **add_kwargs)

    async def delete(self, collection: str, doc_ids: List[str], **delete_kwargs: Any):
        collection = self._get_collection(name=collection)
        collection.delete(ids=doc_ids, **delete_kwargs)

    async def query(self, collection: str, query: List[float], num_results: int, metadata_where: Dict[str, str], include_embeddings: bool = False) -> List[QueryItem]:
        collection = self._get_collection(name=collection)
        thingsToInclude: Include = ["metadatas", "distances"]
        if include_embeddings:
            thingsToInclude.append("embeddings")

        results: QueryResult = collection.query(
            query_embeddings=[query],
            n_results=num_results,
            where=metadata_where,
            include=thingsToInclude
        )

        ret = []
        for doc_id, i in enumerate(results["ids"][0]):
            embedding = results["embeddings"][0][doc_id] if include_embeddings else None
            ret.append(QueryItem(
                id=i,
                distance=results["distances"][0][doc_id],
                embedding=embedding,
                metadata=results["metadatas"][0][doc_id]
            ))

        return ret
