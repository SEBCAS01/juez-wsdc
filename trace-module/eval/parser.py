import spacy
from typing import List


class SentenceParser:
    def __init__(self, model_name: str = "es_core_news_sm"):
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            print(f"Downloading spaCy model '{model_name}'...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", model_name])
            self.nlp = spacy.load(model_name)
    
    def parse(self, text: str) -> List[str]:
        if not text or not isinstance(text, str):
            return []
        return [sent.text.strip() for sent in self.nlp(text).sents if sent.text.strip()]
