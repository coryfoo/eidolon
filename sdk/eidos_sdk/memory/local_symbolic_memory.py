from copy import deepcopy
from typing import Any, Union, List, Dict, AsyncIterable, Optional

from pymongo.errors import DuplicateKeyError

from eidos_sdk.memory.agent_memory import SymbolicMemory


class LocalSymbolicMemory(SymbolicMemory):
    db = {}

    def start(self):
        LocalSymbolicMemory.db = {}

    def stop(self):
        LocalSymbolicMemory.db = {}

    async def count(self, symbol_collection: str, query: dict[str, Any]) -> int:
        if symbol_collection not in self.db:
            return 0
        return sum(1 for doc in self.db[symbol_collection] if all(item in doc.items() for item in query.items()))

    def _matches_query(self, doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if key not in doc:
                return False
            if isinstance(value, dict):
                if not self._matches_query(doc[key], value):
                    return False
            elif doc[key] != value:
                return False
        return True

    def _apply_projection(self, doc: dict, projection: dict) -> dict:
        return {field: doc[field] for field in doc if field in projection and projection[field] == 1}

    def find(
        self,
        symbol_collection: str,
        query: dict[str, Any],
        projection: Union[List[str], Dict[str, int]] = None,
        sort: dict = None,
        skip: int = None,
    ) -> AsyncIterable[dict[str, Any]]:
        if symbol_collection not in self.db:
            return
        for doc in self.db[symbol_collection]:
            if self._matches_query(doc, query):
                yield deepcopy(self._apply_projection(doc, projection) if projection else doc)

    async def find_one(self, symbol_collection: str, query: dict[str, Any]) -> Optional[dict[str, Any]]:
        if symbol_collection not in self.db:
            return None
        for doc in self.db[symbol_collection]:
            if self._matches_query(doc, query):
                return deepcopy(doc)
        return None

    async def insert_one(self, symbol_collection: str, document: dict[str, Any]) -> None:
        if symbol_collection not in self.db:
            self.db[symbol_collection] = []
        if any(doc.get("_id") == document.get("_id") for doc in self.db[symbol_collection]):
            raise DuplicateKeyError(f"Duplicate key error: _id {document.get('_id')} already exists.")
        self.db[symbol_collection].append(deepcopy(document))

    async def insert(self, symbol_collection: str, documents: list[dict[str, Any]]) -> None:
        if symbol_collection not in self.db:
            self.db[symbol_collection] = []
        for document in documents:
            if any(doc.get("_id") == document.get("_id") for doc in self.db[symbol_collection]):
                raise DuplicateKeyError(f"Duplicate key error: _id {document.get('_id')} already exists.")
        self.db[symbol_collection].extend(deepcopy(documents))

    async def upsert_one(self, symbol_collection: str, document: dict[str, Any], query: dict[str, Any]) -> None:
        if symbol_collection not in self.db:
            self.db[symbol_collection] = []
        for i, doc in enumerate(self.db[symbol_collection]):
            if self._matches_query(doc, query):
                self.db[symbol_collection][i] = deepcopy(document)
                return
        if any(doc.get("_id") == document.get("_id") for doc in self.db[symbol_collection]):
            raise DuplicateKeyError(f"Duplicate key error: _id {document.get('_id')} already exists.")
        self.db[symbol_collection].append(deepcopy(document))

    async def update_many(self, symbol_collection: str, query: dict[str, Any], document: dict[str, Any]) -> None:
        if symbol_collection not in self.db:
            return
        for doc in self.db[symbol_collection]:
            if self._matches_query(doc, query):
                doc.update(deepcopy(document))

    async def delete(self, symbol_collection, query):
        if symbol_collection not in self.db:
            return
        self.db[symbol_collection] = [
            doc for doc in self.db[symbol_collection] if not all(item in doc.items() for item in query.items())
        ]
