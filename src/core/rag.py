"""
Birla Opus Chatbot - RAG (Retrieval Augmented Generation) Service
"""
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib
import json
import re

from config.settings import get_settings

settings = get_settings()


class SimpleRAGService:
    """
    Simple RAG service using keyword matching and TF-IDF-like scoring.
    For production, replace with vector database (pgvector, Qdrant, etc.)
    """

    def __init__(self, knowledge_base_path: str = None):
        self.knowledge_base_path = knowledge_base_path or settings.KNOWLEDGE_BASE_PATH
        self.documents: List[Dict] = []
        self.chunks: List[Dict] = []
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """Load and chunk all markdown files from knowledge base."""
        kb_path = Path(self.knowledge_base_path)

        if not kb_path.exists():
            print(f"Warning: Knowledge base path {kb_path} does not exist")
            return

        for md_file in kb_path.glob("*.md"):
            self._process_document(md_file)

        print(f"Loaded {len(self.documents)} documents with {len(self.chunks)} chunks")

    def _process_document(self, file_path: Path):
        """Process a markdown document into chunks."""
        content = file_path.read_text(encoding='utf-8')
        doc_id = hashlib.md5(str(file_path).encode()).hexdigest()[:8]

        # Store document metadata
        doc = {
            "id": doc_id,
            "filename": file_path.name,
            "title": self._extract_title(content),
            "path": str(file_path),
        }
        self.documents.append(doc)

        # Split into chunks by sections
        chunks = self._chunk_by_sections(content, doc_id, file_path.name)
        self.chunks.extend(chunks)

    def _extract_title(self, content: str) -> str:
        """Extract title from markdown content."""
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                return line[2:].strip()
        return "Untitled"

    def _chunk_by_sections(self, content: str, doc_id: str, filename: str) -> List[Dict]:
        """Split content into chunks by markdown sections."""
        chunks = []
        current_section = ""
        current_content = []
        chunk_id = 0

        lines = content.split('\n')

        for line in lines:
            # New section starts with ## or ###
            if line.startswith('## ') or line.startswith('### '):
                # Save previous chunk
                if current_content:
                    chunk_text = '\n'.join(current_content).strip()
                    if len(chunk_text) > 50:  # Minimum chunk size
                        chunks.append({
                            "id": f"{doc_id}_{chunk_id}",
                            "doc_id": doc_id,
                            "filename": filename,
                            "section": current_section,
                            "content": chunk_text,
                            "keywords": self._extract_keywords(chunk_text),
                        })
                        chunk_id += 1

                current_section = line.lstrip('#').strip()
                current_content = [line]
            else:
                current_content.append(line)

        # Don't forget last chunk
        if current_content:
            chunk_text = '\n'.join(current_content).strip()
            if len(chunk_text) > 50:
                chunks.append({
                    "id": f"{doc_id}_{chunk_id}",
                    "doc_id": doc_id,
                    "filename": filename,
                    "section": current_section,
                    "content": chunk_text,
                    "keywords": self._extract_keywords(chunk_text),
                })

        return chunks

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for matching."""
        text_lower = text.lower()

        # Product names
        products = [
            "opus one", "one", "pure elegance", "calista", "ever wash", "everwash",
            "true vision", "true look", "neo star", "neostar", "alldry", "all dry",
            "waterproofing", "primer", "putty", "texture", "emulsion", "enamel",
            "wood finish", "style", "color smart", "stain guard"
        ]

        # Business/process terms
        terms = [
            "interior", "exterior", "waterproof", "damp", "dampness", "leakage",
            "dealer", "contractor", "painter", "sales", "paintcraft",
            "price", "rate", "cost", "quote", "quotation", "estimate",
            "coverage", "sqft", "sq ft", "litre", "liter",
            "warranty", "application", "process", "surface", "prep",
            "color", "colour", "shade", "tinting",
            "scheme", "offer", "margin", "cashback", "loyalty", "birla opus id",
            "training", "complaint", "peeling", "bubble", "crack",
            "2bhk", "3bhk", "1bhk", "material", "payment", "advance"
        ]

        keywords = []

        for product in products:
            if product in text_lower:
                keywords.append(product)

        for term in terms:
            if term in text_lower:
                keywords.append(term)

        # Add numbers (prices, coverage, etc.)
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        for num in numbers[:5]:
            keywords.append(num)

        return list(set(keywords))

    def search(self, query: str, top_k: int = 5, user_type: str = None) -> List[Dict]:
        """
        Search for relevant chunks based on query.
        Returns list of (chunk, score) tuples.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Extract query keywords
        query_keywords = self._extract_keywords(query)

        scored_chunks = []

        for chunk in self.chunks:
            score = 0

            # Keyword matching (set intersection)
            chunk_keywords = set(chunk["keywords"])
            query_kw_set = set(query_keywords)
            keyword_overlap = len(query_kw_set & chunk_keywords)
            score += keyword_overlap * 3

            # Word matching in content
            content_lower = chunk["content"].lower()
            for word in query_words:
                if len(word) > 3 and word in content_lower:
                    score += 1

            # Section title matching
            if chunk["section"]:
                section_lower = chunk["section"].lower()
                for word in query_words:
                    if len(word) > 3 and word in section_lower:
                        score += 2

            # User type relevance boost
            if user_type:
                if user_type in content_lower or user_type in chunk["filename"].lower():
                    score += 2

            if score > 0:
                scored_chunks.append((chunk, score))

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Return top_k results
        results = []
        for chunk, score in scored_chunks[:top_k]:
            results.append({
                "content": chunk["content"],
                "section": chunk["section"],
                "filename": chunk["filename"],
                "score": score,
            })

        return results

    def get_context_for_query(self, query: str, user_type: str = None, max_tokens: int = 3000) -> Tuple[str, List[Dict]]:
        """
        Get relevant context for a query, formatted for LLM.
        Returns: (context_string, sources)
        """
        results = self.search(query, top_k=8, user_type=user_type)

        if not results:
            return "", []

        context_parts = []
        sources = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough estimate

        for result in results:
            content = result["content"]

            # Truncate if too long
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 200:
                    content = content[:remaining] + "..."
                else:
                    break

            context_parts.append(f"[Source: {result['filename']} - {result['section']}]\n{content}")
            sources.append({
                "filename": result["filename"],
                "section": result["section"],
                "relevance": result["score"]
            })
            total_chars += len(content)

        context = "\n\n---\n\n".join(context_parts)
        return context, sources


# Singleton instance
_rag_service: Optional[SimpleRAGService] = None


def get_rag_service() -> SimpleRAGService:
    """Get RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = SimpleRAGService()
    return _rag_service
