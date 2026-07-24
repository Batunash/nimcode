import os
import math
import logging
from collections import Counter
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class LightweightRAG:
    """A zero-dependency, lightweight semantic/keyword search index using TF-IDF/BM25 approximation."""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.documents: Dict[str, str] = {}  # filepath -> content
        self.doc_freqs: Dict[str, int] = {}  # word -> number of docs containing word
        self.doc_lengths: Dict[str, int] = {} # filepath -> number of words
        self.avg_doc_length = 0
        self.is_indexed = False
        
        self.ignore_dirs = {'.git', '.nimcode', '__pycache__', 'node_modules', 'venv', 'env', 'dist', 'build'}
        self.ignore_exts = {'.pyc', '.exe', '.dll', '.so', '.dylib', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.pdf', '.zip', '.tar', '.gz'}

    def _tokenize(self, text: str) -> List[str]:
        # Simple alphanumeric tokenization
        import re
        return [w.lower() for w in re.findall(r'\b\w+\b', text) if len(w) > 2]

    def build_index(self):
        """Scans the workspace and builds the in-memory index."""
        logger.info(f"Building RAG index for {self.workspace_root}...")
        self.documents.clear()
        self.doc_freqs.clear()
        self.doc_lengths.clear()
        
        total_length = 0
        
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.ignore_exts:
                    continue
                    
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.workspace_root)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        self.documents[rel_path] = content
                        
                        tokens = self._tokenize(content)
                        self.doc_lengths[rel_path] = len(tokens)
                        total_length += len(tokens)
                        
                        # Update document frequencies (unique words per doc)
                        unique_tokens = set(tokens)
                        for token in unique_tokens:
                            self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
                            
                except UnicodeDecodeError:
                    # Likely a binary file we missed
                    pass
                except Exception as e:
                    logger.debug(f"Failed to read {filepath}: {e}")
                    
        if self.documents:
            self.avg_doc_length = total_length / len(self.documents)
            
        self.is_indexed = True
        logger.info(f"RAG index built: {len(self.documents)} documents indexed.")

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float, str]]:
        """Searches the index using a simplified BM25 scoring algorithm."""
        if not self.is_indexed:
            self.build_index()
            
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
            
        scores = {}
        N = len(self.documents)
        k1 = 1.5
        b = 0.75
        
        for rel_path, content in self.documents.items():
            doc_tokens = self._tokenize(content)
            doc_counts = Counter(doc_tokens)
            doc_len = self.doc_lengths[rel_path]
            
            score = 0.0
            for q_token in query_tokens:
                if q_token not in doc_counts:
                    continue
                    
                # IDF
                df = self.doc_freqs.get(q_token, 0)
                idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
                
                # TF (BM25)
                tf = doc_counts[q_token]
                tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / max(1, self.avg_doc_length))))
                
                score += idf * tf_norm
                
            if score > 0:
                scores[rel_path] = score
                
        # Sort and return top K
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for path, score in sorted_docs:
            content = self.documents[path]
            # Extract a snippet around the first matching term if possible, or just return first 500 chars
            snippet = content[:500] + "..." if len(content) > 500 else content
            results.append((path, score, snippet))
            
        return results
